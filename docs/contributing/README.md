# doc-contributing

Source for the OABP / AIGEN ecosystem **Contributing Guide**.

| | |
| --- | --- |
| **Category** | doc |
| **Artifact** | `contributing.md` |
| **Install target** | `<your-project-dir>/contributing.md` |
| **Protocol** | OABP / AIGEN — `https://cryptogenesis.duckdns.org` |

## What's here

- **`contributing.md`** — the contributor guide for the OABP ecosystem repo. It
  documents the real repository layout (`sdk-<lang>-client/`,
  `integration-<framework>-<kind>/`, `examples/`, `docs/`, `specs/`,
  `discovery/`), the house coding conventions every package follows
  (dependency-light SDKs, vendored SDK in integrations, trimmed dict tool
  results, injectable client + default `agent_id`, offline `MockClient` with real
  verification semantics, one runnable example per package), distinct
  **add-a-SDK / add-an-integration / add-an-example** checklists, the canonical
  `oabp_<verb>_<noun>` tool naming and package naming, how to register a
  contribution as an OABP **mission deliverable**, the offline-first testing
  rule, and the **CC0-spec / MIT-impl** licensing + code of conduct.

## Install

This is a plain Markdown document — no build step. Copy it into place:

```bash
mkdir -p <your-project-dir>
cp contributing.md <your-project-dir>/contributing.md
```

## License

The guide describes the repo's licensing policy: **specs are CC0**, **reference
implementations are MIT**. This document itself is released under **CC0 1.0**.
