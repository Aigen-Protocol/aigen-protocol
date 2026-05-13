# AIGEN Browser Extension

Auto-detect token addresses on **any webpage** and show inline AIGEN safety badges. Works on Etherscan, Solscan, DexScreener, GeckoTerminal, DefiLlama, CoinGecko, Twitter/X — anywhere `0x...` addresses appear.

## Features

- **Inline badges** — every `0x...` address on the page gets a colored AIGEN safety badge next to it
- **Click badge** → modal with full scan: name/symbol, score, verdict, top 5 flags, link to full scan
- **Popup** (extension icon) — paste any address (EVM or Solana) for a quick scan, or hit "Re-scan this page"
- **Color-coded** — green ≥90, yellow ≥60, orange ≥30, red <30
- **Smart chain detection** — uses the URL host (basescan.org → base, optimistic.etherscan.io → optimism, etc.)
- **Cached** — same address scanned only once per session
- **Mutation observer** — picks up addresses inserted by SPA navigation (Etherscan, DexScreener)

## Install

### Dev install (Chrome/Edge/Brave/Opera)

1. Open `chrome://extensions/`
2. Enable "Developer mode" (top right)
3. "Load unpacked" → select `integrations/browser_extension/` directory
4. Visit any token page — see inline AIGEN badges

### Dev install (Firefox)

1. Open `about:debugging#/runtime/this-firefox`
2. "Load Temporary Add-on" → select `manifest.json`

### Production (once published)

- **Chrome Web Store:** _(pending)_
- **Firefox Add-ons:** _(pending)_

## Permissions

- `storage` — save user preferences (base URL, agent_id)
- `activeTab` — re-scan current page when popup button is clicked
- `host_permissions: cryptogenesis.duckdns.org` — fetch scan results from AIGEN API

The extension does NOT collect telemetry. All scans go directly from your browser to the AIGEN API. No proxy. No tracking.

## How it works

1. Content script runs on every page after `document_idle`
2. Walks all text nodes, regex-matches `0x[a-fA-F0-9]{40}` (EVM addresses)
3. For each match: inserts a `<span class="aigen-badge">` next to the address
4. Asynchronously calls `GET /scan?address=...&chain=auto` to AIGEN
5. Updates badge color + text with the score
6. Mutation observer re-runs whenever DOM changes (SPA-friendly)

Sites where this is most useful:
- **Etherscan / Basescan / Arbiscan** — every contract page is now scored
- **DexScreener / GeckoTerminal** — token list pages get inline scores
- **Twitter/X** — alpha posts with addresses get scored before you ape
- **GitHub** — contract source files get scored

## Why AIGEN

| | Etherscan native | Token sniffer | AIGEN |
|---|---|---|---|
| Free | ✅ | Limited | ✅ |
| Multi-chain | ❌ | Limited | 6 EVM + Solana |
| API key | ❌ | ✅ required | ❌ |
| On-chain bounties | ❌ | ❌ | ✅ |

## Architecture

- Manifest V3 (modern Chrome API)
- Pure vanilla JS — no React, no build step
- Single content.js (~200 lines)
- ~3KB minified once we minify
- Works in any Chromium-based browser + Firefox (with minor manifest tweaks)

## License

MIT
