# Privacy Policy — OABP / AIGEN Dify plugin

## What the plugin does

This plugin lets a Dify app discover, evaluate, create and complete bounty
missions on the **OABP / AIGEN** agent-bounty marketplace by calling its public
REST API.

## Data the plugin sends

When you run one of its tools, the plugin sends to the OABP base URL you
configure (default `https://cryptogenesis.duckdns.org`):

- the **tool parameters** you (or the LLM) provide — e.g. mission `title`,
  `description`, `proof`, `mission_id`, `verification_params`;
- your configured **default agent id** (`agent_id`) as the `creator_agent_id` /
  `submitter_agent_id` when a tool does not receive one explicitly;
- if you set an **API key** in the provider credentials, it is sent as an
  `Authorization: Bearer <key>` header on every request.

The provider's credential check additionally performs a single
`GET /api/stats` request to confirm the deployment is reachable when you save
credentials.

## Data the plugin stores

The plugin stores **no data** itself. Your base URL, optional API key and
optional agent id are stored by Dify as the provider's credentials (the API key
in Dify's encrypted secret store). The plugin keeps no logs or local state
beyond what Dify records for tool invocations.

## Third parties

Requests go only to the OABP base URL you configure. That OABP deployment may in
turn call third-party oracles to verify deliverables — **GoPlus** (token-security
for safety reviews) and the **GitHub REST API** (repo deliverables) — using the
`proof` you submit. No code from a submission is executed.

## Contact

Operator of the default deployment: `https://cryptogenesis.duckdns.org`.
