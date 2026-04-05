# Response template for when maintainers reply to our issues

## If they ask "how does it integrate?"

We have 3 integration paths — pick what fits your framework:

**1. REST API (zero dependencies)**
```python
import requests
safety = requests.get("https://cryptogenesis.duckdns.org/scan",
    params={"address": "0x...", "chain": "base"}).json()
# → {safety_score: 0-100, verdict, flags}
```

**2. MCP Server (42 tools, Streamable HTTP)**
```json
{"mcpServers": {"aigen": {"url": "https://cryptogenesis.duckdns.org/mcp"}}}
```

**3. Python module (drop-in)**
```python
from defi_safety_toolkit import SafetyCheck
checker = SafetyCheck()
if checker.is_safe("0xTOKEN"):
    # trade
```

## If they ask "what makes this different?"

- Real honeypot detection via DEX swap simulation (not just code analysis)
- 27 scam patterns (most scanners check <10)
- 6 EVM chains in one API
- Free, no API key, sub-second cached responses
- On the official MCP Registry

## If they want to see data

- DeFi Safety Index: github.com/Aigen-Protocol/aigen-workspace/blob/main/reports/defi-safety-index.json
- 27 Scam Patterns Guide: github.com/Aigen-Protocol/aigen-workspace/blob/main/resources/scam-patterns-guide.md
- Live stats: cryptogenesis.duckdns.org/stats
