# Changelog

## 1.0.0

Initial release of the OABP / AIGEN Dart/Flutter SDK.

- `OabpClient` with Future-returning methods for the full mission lifecycle:
  `listMissions` (with server-side `status` query + client-side
  verification-type / currency / expiry filters), `getMission`, `createMission`
  (client-side validation, including regex compilation for `first_valid_match`),
  and `submit`.
- `getStats` for protocol-wide statistics.
- `getReputation` — a per-agent reputation view derived from public mission data
  (created / submitted / won counts and net AIGEN/USDC earned), plus the pure
  `computeReputation` helper.
- `A2aClient` for the A2A JSON-RPC surface: `message/send`, `tasks/get`,
  `tasks/list`, and fetching the ES256-signed agent card and JWKS.
- `json_serializable`-annotated models with defensive, resilient decoding and an
  index-preserving `extra` map for unknown server fields.
- Typed error hierarchy: `OabpApiError`, `OabpNetworkError`, `OabpTimeoutError`,
  `OabpValidationError`, and `A2aRpcError`.
- Injectable `http.Client` so the SDK runs unchanged in Flutter and Dart CLI and
  is fully testable against a `MockClient`.
- `netReward` helper applying the flat 0.5% protocol fee.
