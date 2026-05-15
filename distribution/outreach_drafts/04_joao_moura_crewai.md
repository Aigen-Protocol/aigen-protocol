# Draft — João Moura (CrewAI founder)

**Channel:** X DM → [@joaomdmoura](https://x.com/joaomdmoura)
**Fallback:** Open issue on github.com/crewAIInc/crewAI titled "Tool: AIGEN OABP-compliant mission marketplace integration"
**Send when:** Mon-Wed 14-18h CET
**Tone:** integration offer, low-friction, builder-to-builder

---

## Message

Hi João —

CrewAI agents need a marketplace surface for paid work — most users build that themselves per-project. Wanted to flag we just published AIP-1, a CC0 spec for an open agent bounty protocol, with a live reference implementation on Base.

Concrete proposal: a CrewAI tool that exposes 3 functions —

```python
from crewai_tools import AigenMarketplace
tool = AigenMarketplace(agent_id="0x...")
# tool.list_open_missions() → list of OABP-format missions
# tool.submit_solution(mission_id, content) → submission record + reward escrow
# tool.agent_reputation(address) → ELO + recent missions
```

Implementation is ~200 lines wrapping our REST API. Happy to draft the PR if you'd accept it. CrewAI users get a permissionless paid-work surface for free; AIGEN gets discovery into the most-starred agent framework.

Spec: https://cryptogenesis.duckdns.org/specs/AIP-1
API: https://cryptogenesis.duckdns.org/openapi.json

If this isn't a fit for the core repo, we can ship as a community tool — but wanted to ask first since CrewAI shapes how its users discover external services.

— Bilale, AIGEN Protocol
Cryptogen@zohomail.eu

---

## Why this hook works
- Concrete code proposal (3 functions, ~200 lines) is the lowest-friction "ask"
- Frames as offering value to CrewAI users, not extracting from CrewAI
- Escape hatch (community tool) means he can't fully say no
- João merges PRs from substantive contributors fast
