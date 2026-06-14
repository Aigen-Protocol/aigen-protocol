# Framework Integration Guide

This directory stages the **Framework Integration Guide** for the OABP / AIGEN
protocol.

* **`integration-guide.md`** — the guide itself.
  * **Target path on publish:** `docs/integration-guide.md`
  * **Category:** doc

## What it is

A guide for authors adding **OABP support to a new agent framework** (a binding /
"integration"). It codifies the **house pattern** observed across the existing
integrations so a new binding behaves identically to every other one.

It covers:

* the **six canonical tools** every binding must expose — `list_missions`,
  `get_mission`, `create_mission`, `submit_mission`, `get_stats`,
  `get_reputation` (named `oabp_<verb>_<noun>`) — plus the optional
  `oabp_a2a_send`;
* the **seven house conventions**: vendor/depend on the language SDK; trim
  results to model-friendly dicts; map errors to a structured `{"error": ...}`
  dict instead of raising; provide an injectable client + default `agent_id`;
  ship a `MockClient` with real verification semantics; ship one runnable
  example;
* a **build checklist** (10 items) a binding must satisfy;
* **reference skeletons** in both **Python** (`StructuredTool` + Pydantic
  `args_schema`) and **TypeScript** (zod `tool()`), plus the `MockClient`
  verification mirror;
* the **naming convention** (`oabp_<verb>_<noun>` tools, `@aigen/<framework>-oabp`
  packages) and the existing **langchain / crewai / langgraph** integrations as
  exemplars.

## Audience

Integration authors — not end users of the protocol. End-user docs live in the
quickstart / "build your first OABP agent" guides.

## License

MIT.
