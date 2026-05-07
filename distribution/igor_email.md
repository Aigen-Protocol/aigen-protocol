**To:** igor@bankr.fun (or DevRel email Danny forwarded)
**From:** Cryptogen@zohomail.eu
**Subject:** SafeAgent x402 — concrete agent-protection layer now live, looking for Bankr collab
**Reply-To:** Cryptogen@zohomail.eu

---

Hi Igor,

Following up on Danny's intro. I shipped two pieces this week that I think
make the SafeAgent x402 service materially more useful for Bankr's agent
ecosystem. Wanted to share concrete demos before re-pitching.

**1. `/watch` — push-based wallet protection, signed alerts**

Most safety oracles (incl. ours until now) are pull-only: agent calls
`/scan`, gets a score, leaves. `/watch` makes it push:

```bash
curl -X POST https://cryptogenesis.duckdns.org/watch \
  -H 'Content-Type: application/json' \
  -d '{"agent_id":"<your_agent>","wallet":"0x...","callback_url":"https://...","chain":"base"}'
```

We poll the wallet's holdings (Aerodrome / Blockscout), score each, and POST
a signed HMAC-SHA256 alert to the callback URL when a held token's score
drops 20+ pts or a new risky holding (<50/100) is detected. Schema:
`aigen.watch.v1`. Each alert has a `signature` field — agents can forward
the alert to their principal as cryptographic proof.

Public key fingerprint:
`73684eee72e4854394f558aa7be84e23bf848e27ca46150ab35e7e9b4106d95f`

If Bankr agents register their working wallets with us, they get free
continuous protection. Premium tier ($AIGEN gated) drops poll to 10min.

**2. SafeRouter on-chain — atomic swap protection on Base**

Contract: `0xb200357a35C7e96A81190C53631BC5Beca84A8FA` (Aerodrome wrapped).
Score-aware: any swap into a token scoring <40 reverts with cite-able
revert reason. First live swap last week:

  https://basescan.org/tx/0x60885512baac0d99270de754c1ba099205e4ae459f8468c8338e7962994ed97b

Oracle address: `0x37b9e9B8789181f1AaaD1cD51A5f00A887fa9b8e` (ERC-7913 interface).
We refresh the top 20 Base tokens every 6h via an autonomous updater.

Agents call our `/saferouter/calldata` endpoint to get ready-to-sign tx
calldata — they retain custody. Or directly via the Solidity library:

```solidity
import {SafeGuard} from "@aigen/safeguard/SafeGuard.sol";
using SafeGuard for address;

function trade(address token) external {
    token.requireSafe();        // reverts if oracle says unsafe
    // ... rest of your swap
}
```

**Where Bankr fits**

Two ideas, both 0-touch from your side:

(a) Surface SafeAgent as a built-in "pre-trade safety" check in Bankr's
    agent SDK. Agents already trading via Bankr could route through
    SafeRouter with no UX change.

(b) List us in your x402 service directory under "security/safety oracle"
    so agents browsing the registry find us. We're currently 5 services
    deep (token-safety, wallet-risk, contract-audit, defi-yields,
    market-deep) but with 0 agent-side visibility from Bankr's UI.

Happy to do a 15-min demo over Telegram or wherever works. Token addresses,
docs, and source: github.com/Aigen-Protocol.

Best,
CG / opus-founder
Cryptogen@zohomail.eu
