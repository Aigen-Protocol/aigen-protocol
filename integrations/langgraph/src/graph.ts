/**
 * build_graph / buildGraph — the compiled example graph.
 *
 *      START
 *        │
 *        ▼
 *   ┌──────────┐     ┌──────────┐     route: claimable @ cursor?
 *   │ discover │ ──▶ │ evaluate │ ──▶ ─────────────┬───────────────┐
 *   └──────────┘     └──────────┘                  │ worker        │ done
 *                                                  ▼               ▼
 *                                            ┌──────────┐         END
 *                                            │  worker  │
 *                                            └────┬─────┘
 *                                                 │  (loop: route again)
 *                                                 └────────────▶ route
 *
 * The graph discovers open OABP missions, evaluates which ones this agent can verifiably win,
 * then loops a worker over the claimable set (one submission per tick) until the cursor passes
 * the end of the list — at which point it routes to END.
 */

import { END, START, StateGraph } from "@langchain/langgraph";
import type { CompiledStateGraph } from "@langchain/langgraph";

import { OabpState } from "./state.js";
import type { OabpClient } from "./sdk.js";
import {
  discoverNode,
  evaluateNode,
  routeClaimable,
  workerNode,
  type NodeDeps,
} from "./nodes.js";

export interface BuildGraphOptions extends NodeDeps {
  /** Hard cap on worker iterations (LangGraph recursion limit). Defaults to 50. */
  recursionLimit?: number;
}

/**
 * Compile the discover → evaluate → worker* graph against an injected {@link OabpClient}.
 * The returned graph is a standard LangGraph `CompiledStateGraph`; call `.invoke(initialState)`
 * or `.stream(...)` on it.
 */
export function buildGraph(opts: BuildGraphOptions) {
  const deps: NodeDeps = { client: opts.client, buildProof: opts.buildProof };

  const builder = new StateGraph(OabpState)
    .addNode("discover", discoverNode(deps))
    .addNode("evaluate", evaluateNode())
    .addNode("worker", workerNode(deps))
    .addEdge(START, "discover")
    .addEdge("discover", "evaluate")
    // After evaluate, route to worker if there's something claimable, else END.
    .addConditionalEdges("evaluate", routeClaimable, { worker: "worker", done: END })
    // After each worker pass, route again — loops until cursor exhausts the claimable list.
    .addConditionalEdges("worker", routeClaimable, { worker: "worker", done: END });

  return builder.compile();
}

/** snake_case alias to match the spec's `build_graph()` name. */
export const build_graph = buildGraph;

export type OabpGraph = ReturnType<typeof buildGraph>;

/**
 * Convenience runner: build the graph, invoke one full pass, and return the final state.
 * `recursionLimit` bounds the worker loop.
 */
export async function runOnce(
  opts: BuildGraphOptions,
  init: Parameters<CompiledStateGraph<any, any, any>["invoke"]>[0] = {}
) {
  const graph = buildGraph(opts);
  return graph.invoke(init, { recursionLimit: opts.recursionLimit ?? 50 });
}
