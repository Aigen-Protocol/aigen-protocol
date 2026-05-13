#!/bin/bash
# One-shot demo runner — orchestrates the full Mastra → LangChain → CrewAI flow.
# Outputs each step's result + a final report linking everything together.
#
# Usage:
#   export OPENAI_API_KEY=sk-...
#   export PAYOUT_WALLET=0xYOUR_WALLET
#   bash run_demo.sh

set -e

if [ -z "$OPENAI_API_KEY" ]; then
    echo "ERR: set OPENAI_API_KEY first"
    exit 1
fi

if [ -z "$PAYOUT_WALLET" ]; then
    echo "WARN: PAYOUT_WALLET not set — using burn address (you won't receive USDC)"
    export PAYOUT_WALLET="0x000000000000000000000000000000000000dEaD"
fi

cd "$(dirname "$0")"

echo "════════════════════════════════════════════════════════════════"
echo "AIGEN Cross-Framework Collaboration Demo"
echo "Mastra (TS) → LangChain (Py) → CrewAI (Py)"
echo "════════════════════════════════════════════════════════════════"

echo ""
echo "▶ STEP 1: Mastra agent creates mission..."
npx tsx agents/mastra_creator.ts | tee /tmp/aigen_demo_step1.log

echo ""
echo "(Pause 5s for AIGEN autopilot to index the new mission)"
sleep 5

echo ""
echo "▶ STEP 2: LangChain agent claims the mission..."
python3 agents/langchain_claimer.py | tee /tmp/aigen_demo_step2.log

# Extract mission_id and submission_id from logs (rough)
MISSION_ID=$(grep -oE 'mis_[a-f0-9]+' /tmp/aigen_demo_step1.log /tmp/aigen_demo_step2.log | head -1)
SUBMISSION_ID=$(grep -oE 'sub_[a-f0-9]+' /tmp/aigen_demo_step2.log | head -1)

echo ""
echo "Detected mission: $MISSION_ID"
echo "Detected submission: $SUBMISSION_ID"

if [ -n "$MISSION_ID" ] && [ -n "$SUBMISSION_ID" ]; then
    echo ""
    echo "▶ STEP 3: CrewAI peer-vote crew reviews..."
    python3 agents/crewai_reviewer.py "$MISSION_ID" "$SUBMISSION_ID"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "DEMO COMPLETE"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Watch resolution + payout (autopilot runs every 5 min):"
echo "  https://cryptogenesis.duckdns.org/missions/$MISSION_ID"
echo ""
echo "See the live activity:"
echo "  https://cryptogenesis.duckdns.org/live"
