/**
 * Minimal, faithful mirror of the Flowise component interfaces this package implements.
 *
 * In a real Flowise checkout these come from `flowise-components` (its `src/Interface.ts`):
 *   import { INode, INodeData, INodeParams, ICommonObject, INodeOptionsValue } from 'flowise-components'
 *
 * Bundling them locally lets `flowise-oabp` typecheck and ship **standalone** (no Flowise source
 * tree needed to compile). The shapes below match Flowise's published interfaces, so when the dist
 * is dropped into `packages/components/nodes` (or pointed at via `NODES_SOURCE_PATH`) the loader
 * picks the classes up unchanged — Flowise loads node classes structurally (it `new`s the default
 * export and reads `.label/.name/.type/.inputs/.baseClasses` and calls `.init()`), it does not
 * `instanceof`-check against its own `INode`.
 *
 * Only the members actually used by Tool nodes are declared; everything Flowise treats as optional
 * stays optional here.
 */

/** Flowise's catch-all object type (a string-keyed bag). */
export interface ICommonObject {
  [key: string]: unknown;
}

/** One selectable option for `asyncOptions` / `options` params, and for `loadMethods`. */
export interface INodeOptionsValue {
  label: string;
  name: string;
  description?: string;
  [key: string]: unknown;
}

/** A single configurable input/credential field rendered in the Flowise node UI. */
export interface INodeParams {
  label: string;
  name: string;
  /**
   * Flowise field type, e.g. 'string' | 'password' | 'number' | 'boolean' | 'options' |
   * 'json' | 'credential' | 'asyncOptions' …
   */
  type: string;
  default?: unknown;
  description?: string;
  optional?: boolean | ICommonObject;
  placeholder?: string;
  rows?: number;
  additionalParams?: boolean;
  /** For `type: 'options'`. */
  options?: Array<INodeOptionsValue>;
  /** For `type: 'asyncOptions'`: the method name on the node's `loadMethods`. */
  loadMethod?: string;
  /** For `type: 'credential'`: which credential names this input accepts. */
  credentialNames?: string[];
  [key: string]: unknown;
}

/** A registered Flowise credential type. */
export interface INodeCredential {
  label: string;
  name: string;
  version: number;
  description?: string;
  inputs?: INodeParams[];
}

/** The instantiated node + its UI-bound values, passed to `init()`/`run()` at execution time. */
export interface INodeData {
  id: string;
  label: string;
  name: string;
  type: string;
  /** Values entered for the node's `inputs`, keyed by input `name`. */
  inputs?: ICommonObject;
  /** The selected credential id (resolved to plaintext via `getCredentialData`). */
  credential?: string;
  outputs?: ICommonObject;
  instance?: unknown;
  [key: string]: unknown;
}

/** Methods that asynchronously populate `asyncOptions` dropdowns in the UI. */
export interface INodeOptionsLoadMethod {
  [methodName: string]: (
    nodeData: INodeData,
    options?: ICommonObject
  ) => Promise<INodeOptionsValue[]>;
}

/**
 * The Flowise node contract. A node module's default export is a class implementing this; Flowise
 * `new`s it once at load to read its metadata, then calls `init()` (and `run()` for non-tool nodes)
 * per execution.
 */
export interface INode {
  label: string;
  name: string;
  version: number;
  type: string;
  icon: string;
  category: string;
  baseClasses: string[];
  description?: string;
  /** Optional credential input descriptor (a `type: 'credential'` INodeParams). */
  credential?: INodeParams;
  inputs?: INodeParams[];
  outputs?: INodeParams[];
  /** `asyncOptions` resolvers. */
  loadMethods?: INodeOptionsLoadMethod;
  /**
   * Build and return the node's runtime value. For a **Tool** node this resolves to the
   * tool instance (e.g. a LangChain `DynamicStructuredTool`).
   */
  init(nodeData: INodeData, input: string, options?: ICommonObject): Promise<unknown>;
}

/**
 * Resolve a credential's decrypted fields. In Flowise this helper is imported from
 * `flowise-components` (`getCredentialData(nodeData.credential, options)`); here we declare the
 * signature and provide a no-op fallback so the nodes compile and run in tests. At runtime inside
 * Flowise, the real implementation is used because the node code calls the imported symbol — see
 * `src/utils.ts` for how production vs. standalone is bridged.
 */
export type GetCredentialDataFn = (
  credentialId: string | undefined,
  options: ICommonObject
) => Promise<ICommonObject>;
