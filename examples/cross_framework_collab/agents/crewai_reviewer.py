#!/usr/bin/env python3
"""Cross-framework collab — STEP 3: CrewAI multi-agent crew REVIEWS the submission.

For peer_vote missions, CrewAI deploys a 2-agent crew:
  - Verifier: technical check on the submission
  - Voter: stakes AIGEN on YES/NO based on Verifier's analysis

The mission was created by Mastra, claimed by LangChain, and now reviewed by
CrewAI. Three different frameworks collaborating via AIGEN as the only shared layer.

This is the unique AIGEN value: cross-framework agent collaboration with
on-chain settlement.

Run:
  pip install crewai aigen-crewai
  export OPENAI_API_KEY=sk-...
  python crewai_reviewer.py <mission_id> <submission_id>
"""
import os
import sys

from crewai import Agent, Crew, Task
from crewai.llm import LLM

from aigen_crewai import get_aigen_tools

# Mission and submission IDs to review (from prior steps)
mission_id = sys.argv[1] if len(sys.argv) > 1 else "mis_DEMO"
submission_id = sys.argv[2] if len(sys.argv) > 2 else "sub_DEMO"

aigen_tools = get_aigen_tools(agent_id="crewai-peer-voter")

verifier = Agent(
    role="AIGEN Submission Verifier",
    goal="Determine if a submitted proof actually satisfies the mission requirements",
    backstory=(
        "You are a meticulous technical reviewer. You read the mission's verification "
        "params and check whether the submitted proof actually matches. You are skeptical "
        "but fair."
    ),
    tools=aigen_tools,
    llm=LLM(model="openai/gpt-4o-mini"),
    allow_delegation=False,
)

voter = Agent(
    role="AIGEN Token Holder & Voter",
    goal="Stake 5 AIGEN on YES or NO for the submission, based on the Verifier's analysis",
    backstory=(
        "You hold AIGEN and care about protocol health. You vote YES on submissions "
        "that genuinely complete missions, NO on ones that don't. You stake real AIGEN "
        "so your vote matters."
    ),
    tools=aigen_tools,
    llm=LLM(model="openai/gpt-4o-mini"),
    allow_delegation=False,
)

verify_task = Task(
    description=(
        f"Mission ID: {mission_id}\n"
        f"Submission ID: {submission_id}\n\n"
        "Use aigen_list_missions or aigen_get_reputation tools to inspect the mission "
        "and the submitter. Determine: does the proof match the mission's requirements?\n"
        "Return: { matches: true/false, reasoning: '...' }"
    ),
    expected_output="JSON object with 'matches' (boolean) and 'reasoning' (string)",
    agent=verifier,
)

vote_task = Task(
    description=(
        f"Based on the Verifier's analysis, vote on submission {submission_id} of "
        f"mission {mission_id}. If matches=true, vote YES with 5 AIGEN. If matches=false, "
        f"vote NO with 5 AIGEN. Use aigen_vote_on_mission... wait, this tool isn't in our "
        f"package yet — for the demo, just report what you would do."
    ),
    expected_output="A description of the vote you cast (or would cast)",
    agent=voter,
    context=[verify_task],
)

crew = Crew(
    agents=[verifier, voter],
    tasks=[verify_task, vote_task],
    verbose=True,
)

if __name__ == "__main__":
    print(f"\n{'=' * 60}")
    print(f"CrewAI peer-vote crew reviewing {mission_id} / {submission_id}")
    print(f"{'=' * 60}\n")
    result = crew.kickoff()
    print(f"\n{'=' * 60}")
    print(f"Crew final output:\n{result}")
    print(f"{'=' * 60}\n")
