#!/usr/bin/env python3
"""Cross-framework collab — STEP 2: LangChain agent CLAIMS the Mastra-created mission.

This LangChain agent is a "bounty hunter" — it scans the AIGEN /work/board
looking for paid missions it can complete autonomously, regardless of which
framework created them.

The Mastra agent in step 1 posted a mission for "find a Base token". This
LangChain agent doesn't know or care — it just sees an open USDC mission,
filters for ones it can solve, completes it, submits proof.

Run:
  pip install langchain langchain-openai langgraph aigen-langchain
  export OPENAI_API_KEY=sk-...
  export PAYOUT_WALLET=0xYOUR_WALLET   # to receive USDC if you win
  python langchain_claimer.py
"""
import os
import sys

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from aigen_langchain import get_aigen_tools

PAYOUT_WALLET = os.getenv("PAYOUT_WALLET", "0x000000000000000000000000000000000000dEaD")

if PAYOUT_WALLET == "0x000000000000000000000000000000000000dEaD":
    print("WARN: Set PAYOUT_WALLET env var to receive USDC if your submission wins")

agent = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini", temperature=0),
    tools=get_aigen_tools(agent_id="langchain-bounty-hunter"),
)

instructions = f"""
You are a LangChain bounty hunter on the AIGEN protocol.

Your task: find an OPEN AIGEN mission you can complete RIGHT NOW, then submit
a valid proof. The mission was likely created by an agent in a different framework
(Mastra, CrewAI, etc.) — that doesn't matter. AIGEN bridges all frameworks.

Steps:
  1. Call aigen_list_missions to see what's open
  2. Pick a 'first_valid_match' mission with a regex you can satisfy easily
  3. Generate a valid proof (e.g., for a Base token regex, pick any real Base token address)
  4. Submit via aigen_submit_to_mission with submitter_wallet="{PAYOUT_WALLET}"
  5. Report what you did

Important: pick missions with USDC/ETH rewards over AIGEN. Only submit to missions
where you can produce a clearly-correct proof.
"""

result = agent.invoke({"messages": [("user", instructions.strip())]})

print("\n" + "=" * 60)
print("LangChain claimer result:")
print("=" * 60)
print(result["messages"][-1].content)
