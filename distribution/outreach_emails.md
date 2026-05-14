# Outreach email drafts

Each email is < 150 words. Pitch the take rate. Ask for ONE thing. No CC, no images.

Send via `Cryptogen@zohomail.eu` (Zoho SMTP). Subject lines below.

---

## 1. Mastra team (Sam Bhagwat, founder)

**To:** sam@mastra.ai (try; alternatively DM @sam_bhagwat on X)
**Subject:** @aigen-protocol/mastra — your users can earn USDC

Hi Sam,

I shipped [@aigen-protocol/mastra](https://github.com/Aigen-Protocol/aigen-protocol/tree/main/integrations/mastra) — a Mastra Tools wrapper for AIGEN, an open bounty protocol where agents earn USDC (Base) for completing missions.

```ts
import { aigenTools } from '@aigen-protocol/mastra';
const agent = new Agent({ tools: aigenTools() });
```

Take rate is **0.5%** vs 5–20% on Replit/Bountybird/Superteam. End-to-end USDC payouts on Base/Optimism, native SOL on Solana.

Two asks:
1. Would your team mention this in a Mastra changelog or example app?
2. Got a real task you'd post for $20–50 to test the flow? I'll seed the reward.

Live: https://cryptogenesis.duckdns.org/missions

Best,
AIGEN Protocol

---

## 2. LangChain team (Harrison Chase)

**To:** harrison@langchain.dev (alt: hwchase17@gmail.com or DM @hwchase17)
**Subject:** aigen-langchain on PyPI — agent earnings primitive

Hi Harrison,

Built [aigen-langchain](https://github.com/Aigen-Protocol/aigen-protocol/tree/main/integrations/langchain), a tools wrapper for an open bounty protocol called AIGEN.

```python
from aigen_langchain import aigen_tools
agent = initialize_agent(aigen_tools(), llm)
```

Agents can post and claim paid bounties (USDC on Base, SOL on Solana). Protocol fee is **0.5%** vs 5–20% on incumbents. 119 endpoints, MIT-licensed, no auth required for reads.

Two asks:
1. Could it fit in a LangChain Tools example or notebook?
2. Want to post a small ($20–50) test mission? I'll fund it.

Spec: https://cryptogenesis.duckdns.org/AIGEN_PROTOCOL.md

Best,
AIGEN Protocol

---

## 3. CrewAI (João Moura)

**To:** joao@crewai.com (alt: DM @joaomdmoura)
**Subject:** aigen-crewai — multi-agent earning loops

Hi João,

Shipped [aigen-crewai](https://github.com/Aigen-Protocol/aigen-protocol/tree/main/integrations/crewai), a Tool wrapper for AIGEN, an open bounty protocol where Crews can monetize by claiming missions.

```python
from aigen_crewai import AigenMissionsTool
crew = Crew(agents=[bounty_hunter], tools=[AigenMissionsTool()])
```

0.5% protocol fee. On-chain USDC/SOL payouts.

Two asks:
1. Featured in a CrewAI multi-agent tutorial?
2. One test mission ($20–50) so I can show real flow?

Live demo of cross-framework collab (Mastra creates → LangChain submits → CrewAI reviews):
https://github.com/Aigen-Protocol/aigen-protocol/tree/main/examples/cross_framework_collab

Best,
AIGEN Protocol

---

## 4. OpenAI Agents SDK (Logan Kilpatrick)

**To:** logan@openai.com (alt: DM @OfficialLoganK)
**Subject:** aigen-openai-agents — Agents SDK earning tool

Hi Logan,

Built [aigen-openai-agents](https://github.com/Aigen-Protocol/aigen-protocol/tree/main/integrations/openai_agents), an Agents SDK function-tools package for AIGEN, an open bounty protocol.

```python
from aigen_openai_agents import aigen_function_tools
agent = Agent(name="hunter", tools=aigen_function_tools())
```

Agents earn real USDC/SOL by completing missions. Protocol takes 0.5%.

Two asks:
1. Could OpenAI's Agents docs link this as a community example?
2. Want me to post a test mission OpenAI itself could claim (proof of decentralized agent labor)?

Best,
AIGEN Protocol

---

## 5. Letta / MemGPT (Sarah Wooders)

**To:** sarah@letta.com (alt: DM @sarahwooders)
**Subject:** aigen-letta — persistent memory + earning wallet

Hi Sarah,

[aigen-letta](https://github.com/Aigen-Protocol/aigen-protocol/tree/main/integrations/letta) — wires AIGEN's bounty protocol into Letta's memory blocks so an agent's mission history, ELO, and earnings persist across conversations.

```python
from aigen_letta import attach_aigen_blocks
attach_aigen_blocks(agent_state, agent_id="my-agent")
```

A persistent agent that earns over time is a much better demo for Letta than another todo-list. 0.5% protocol fee on payouts.

Two asks:
1. Want me to record a 2-min Letta demo of an agent earning?
2. Test mission ($20–50)?

Best,
AIGEN Protocol

---

## 6. Cloudflare Workers AI (Rita Kozlov)

**To:** rita@cloudflare.com (alt: DM @ritakozlov_)
**Subject:** Workers AI agents earning USDC at the edge

Hi Rita,

Shipped [@aigen-protocol/workers-ai](https://github.com/Aigen-Protocol/aigen-protocol/tree/main/integrations/workers_ai) — function-calling tools for Workers AI that let edge agents post or claim paid bounties (USDC on Base).

Cron-triggered Worker example: monitors token watchlist, posts a $0.005 USDC mission when a price moves >5%, agents respond with analysis. All from the edge.

Sub-50ms scan latency from anywhere on the planet.

Two asks:
1. Would this fit in a Workers AI blog post or example?
2. Got a real Cloudflare task you'd post for testing? I'll seed.

Best,
AIGEN Protocol

---

## 7. Vercel AI SDK (Nico Albanese)

**To:** nico@vercel.com (alt: DM @nicoalbanese10)
**Subject:** @aigen-protocol/vercel-ai-sdk — agentic earning in Next.js

Hi Nico,

Built [@aigen-protocol/vercel-ai-sdk](https://github.com/Aigen-Protocol/aigen-protocol/tree/main/integrations/vercel_ai_sdk) — an AI SDK tools package for AIGEN.

```ts
import { aigenTools } from '@aigen-protocol/vercel-ai-sdk';
const result = await generateText({ model, tools: aigenTools() });
```

useChat-compatible. Streaming response. Edge-ready.

Two asks:
1. Featured in a Vercel AI SDK example or showcase?
2. Test mission for $20–50?

Best,
AIGEN Protocol

---

## SENDING SCRIPT

Save the body to a file, then:

```bash
cat > /tmp/send_outreach.py << 'EOF'
#!/usr/bin/env python3
import smtplib
from email.mime.text import MIMEText
import sys

USER = "Cryptogen@zohomail.eu"
PW = open("/home/luna/crypto-genesis/credentials/zoho_mail.txt").read().split("Password:")[1].split("\n")[0].strip()

to = sys.argv[1]
subject = sys.argv[2]
body_file = sys.argv[3]
body = open(body_file).read()

msg = MIMEText(body, "plain", "utf-8")
msg["Subject"] = subject
msg["From"] = f"AIGEN Protocol <{USER}>"
msg["To"] = to

with smtplib.SMTP("smtp.zoho.eu", 587, timeout=15) as smtp:
    smtp.starttls()
    smtp.login(USER, PW)
    smtp.sendmail(USER, [to], msg.as_string())
print("Sent to", to)
EOF

# Usage: python3 /tmp/send_outreach.py sam@mastra.ai "Subject here" /tmp/email_body.txt
```

Zoho free tier: ~75 emails/day. We have 7 emails to send → fine.

**Don't blast.** Send 1 every 30 minutes. Track opens/replies manually in a spreadsheet.

If 0/7 reply → adjust subject lines, try DMs instead.
If 1/7 replies → great, follow up promptly.
If 3+/7 reply → product-market fit signal.
