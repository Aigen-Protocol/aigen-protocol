# /agent — autopilot live status page

**URL:** https://cryptogenesis.duckdns.org/agent
**Privacy:** filters Bilale's personal-forward emails (`bilale.badaoui@outlook.fr`, `bil317@hotmail.fr`) before public render. Counts hidden as "+ N private forwards filtered".
**Auto-refresh:** every 60s via `<script>setTimeout(reload, 60000)</script>`
**Source:** route added to `/home/luna/crypto-genesis/token-scanner/scanner.py` (token-scanner is not in this git repo)

## What it shows

- **Top metrics row**: total runs, commits today, pending cards, today api-equivalent $, treasury USDC, missions count, inbox count, GitHub notifications count
- **Last 8 runs**: timestamp + classified action type (📝 NO-OP / 🚀 COMMIT / 💬 COMMENT / 📤 SUBMIT / 🧠 LESSON / 📋 QUEUE / 📡 SIGNAL / ⚙️ ACTION) + 1-line title linking to full journal entry
- **Pending approval cards**: only shows what's actively in `approval_queue/*.md`
- **External signals**: HustlerOps state, top recent paths, unique IPs, GitHub notifs
- **Inbox tail**: last 5 EXTERNAL emails to `Cryptogen@zohomail.eu` (private forwards filtered)
- **Webhook triggers**: last 10 GitHub webhook events that fired the agent
- **Recent commits**: last 10 commits to aigen-protocol repo
- **System health**: timer/webhook-path/scanner ActiveState + next fire time
- **Quick links**: journal, specs, blog, atom feed, GitHub, outreach targets, OABP manifest

## How to track autopilot from your phone

Bookmark `https://cryptogenesis.duckdns.org/agent` on your phone home screen.
Open it once → you see everything in <2s.
Page auto-refreshes every 60s if you leave it open.

## Privacy boundary

The /agent page is public (no auth). The autopilot agent's private dashboard
(`agent_autonomous/state/dashboard.json`) shows MORE detail (full inbox, full
nginx logs, etc.) but is filesystem-private to the luna user — never exposed
via HTTP.

## What's NOT shown publicly

- Raw nginx access log lines (only aggregate stats)
- Personal forwarded emails from Bilale's outlook/hotmail addresses
- Approval queue card bodies (only count + filename — open them on disk for body)
- Webhook secret, IMAP credentials
