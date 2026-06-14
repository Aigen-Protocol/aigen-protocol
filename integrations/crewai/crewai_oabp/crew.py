"""A two-agent OABP Crew (scout + worker) plus an offline scripted LLM.

This module assembles the OABP CrewAI tools (:mod:`crewai_oabp.tools`) into a
small, runnable :class:`crewai.Crew`:

* **Scout** — discovers open bounty missions on the OABP / AIGEN marketplace and
  inspects the most promising one. Tools: ``oabp_list_missions``,
  ``oabp_get_mission``, ``oabp_get_stats``.
* **Worker** — takes a chosen mission and submits a deliverable (proof) to win
  the reward. Tools: ``oabp_get_mission``, ``oabp_submit_mission``.

:func:`build_crew` returns a real ``Crew`` of these two agents and their tasks.
For an *end-to-end demo that needs no API key and no network*, pass an
:class:`OfflineScriptedLLM` (and a mocked OABP SDK client): CrewAI then drives a
genuine ``crew.kickoff()`` through its ReAct loop, the scripted LLM emits
``Action`` / ``Action Input`` blocks, and CrewAI actually executes the OABP tools
and threads the observations back — exercising the whole handling path.

In production, swap :class:`OfflineScriptedLLM` for a real model, e.g.::

    from crewai import LLM
    llm = LLM(model="gpt-4o-mini")          # reads OPENAI_API_KEY

and point the SDK client at the live marketplace
(``https://cryptogenesis.duckdns.org``).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

from crewai import Agent, Crew, Process, Task
from crewai.llms.base_llm import BaseLLM

from ._sdk import OabpClient
from .tools import (
    GetMissionTool,
    GetStatsTool,
    ListMissionsTool,
    SubmitMissionTool,
)

DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"


# --------------------------------------------------------------------------- #
# Offline scripted LLM — drives a real kickoff() with no network / API key
# --------------------------------------------------------------------------- #
class OfflineScriptedLLM(BaseLLM):
    """A deterministic, offline :class:`~crewai.llms.base_llm.BaseLLM`.

    It returns *scripted* ReAct-formatted strings so a real ``Crew.kickoff()``
    runs end-to-end without any provider call. CrewAI's ReAct executor parses
    each returned string into either a tool call (``Action`` / ``Action Input``)
    or a final answer (``Final Answer:``), runs the named OABP tool itself, and
    feeds the observation back — so the OABP tools are genuinely exercised.

    Because this subclass does **not** implement ``supports_function_calling``,
    CrewAI uses its text/ReAct loop (``_invoke_loop_react``) rather than the
    native function-calling loop — exactly what these scripted strings target.

    Parameters
    ----------
    script:
        Ordered list of raw assistant strings to return, one per ``call``. Each
        string should be a CrewAI ReAct block, e.g.::

            "Thought: I should list missions\\n"
            "Action: oabp_list_missions\\n"
            'Action Input: {"status": "open", "limit": 5}'

        or a terminal ``"Thought: done\\nFinal Answer: <text>"``.
        When the script is exhausted, a safe ``Final Answer`` is returned so the
        loop always terminates.
    model:
        Cosmetic model name (CrewAI records it for events/telemetry).
    """

    def __init__(self, script: Sequence[str], *, model: str = "offline/scripted") -> None:
        super().__init__(model=model)
        # Captured here rather than as a pydantic field to stay independent of
        # BaseLLM's field set across versions.
        self._script: List[str] = list(script)
        self._cursor: int = 0
        #: Every prompt CrewAI sent us, for assertions / debugging.
        self.calls: List[Any] = []

    def call(
        self,
        messages: Any,
        tools: Optional[List[Any]] = None,
        callbacks: Optional[List[Any]] = None,
        available_functions: Optional[Dict[str, Any]] = None,
        from_task: Optional[Any] = None,
        from_agent: Optional[Any] = None,
        response_model: Optional[Any] = None,
    ) -> str:
        """Return the next scripted assistant string (ReAct format)."""
        self.calls.append(messages)
        if self._cursor < len(self._script):
            out = self._script[self._cursor]
            self._cursor += 1
            return out
        # Exhausted script: always terminate cleanly.
        return "Thought: I have completed the task.\nFinal Answer: done"

    # CrewAI checks for this attribute on the LLM; returning False keeps us on
    # the text/ReAct path that our scripted strings target.
    def supports_function_calling(self) -> bool:
        return False

    def supports_stop_words(self) -> bool:
        # We don't want CrewAI truncating our scripted answers on stop tokens.
        return False


def react_action(tool_name: str, tool_input: Dict[str, Any], *, thought: str = "") -> str:
    """Build a ReAct *Action* block string for :class:`OfflineScriptedLLM`."""
    thought = thought or f"I will use {tool_name}."
    return (
        f"Thought: {thought}\n"
        f"Action: {tool_name}\n"
        f"Action Input: {json.dumps(tool_input)}"
    )


def react_final(answer: str, *, thought: str = "") -> str:
    """Build a ReAct *Final Answer* block string for :class:`OfflineScriptedLLM`."""
    thought = thought or "I have everything I need."
    return f"Thought: {thought}\nFinal Answer: {answer}"


# --------------------------------------------------------------------------- #
# The two agents + their tasks + the crew
# --------------------------------------------------------------------------- #
def build_agents(
    client: OabpClient,
    *,
    agent_id: Optional[str] = None,
    llm: Optional[BaseLLM] = None,
    verbose: bool = False,
) -> Dict[str, Agent]:
    """Build the scout + worker :class:`~crewai.Agent`s wired to OABP tools.

    Both agents share one pooled :class:`oabp.OabpClient`. The scout gets the
    read tools (list/get/stats); the worker gets get + submit. ``agent_id`` is
    the default OABP id used by the create/submit tools.
    """
    default_id = agent_id if agent_id is not None else getattr(client, "agent_id", None)

    list_tool = ListMissionsTool(client=client, agent_id=default_id)
    get_tool = GetMissionTool(client=client, agent_id=default_id)
    stats_tool = GetStatsTool(client=client, agent_id=default_id)
    submit_tool = SubmitMissionTool(client=client, agent_id=default_id)

    scout = Agent(
        role="OABP Mission Scout",
        goal=(
            "Discover open bounty missions on the OABP / AIGEN marketplace and "
            "identify the single best mission to work on, with its id, reward and "
            "verification requirements."
        ),
        backstory=(
            "A sharp marketplace analyst for the OABP agent-bounty economy. You "
            "scan open missions, read their verification rules, and pick the most "
            "tractable, best-paying one for a worker agent to complete."
        ),
        tools=[list_tool, get_tool, stats_tool],
        llm=llm,
        allow_delegation=False,
        verbose=verbose,
    )

    worker = Agent(
        role="OABP Mission Worker",
        goal=(
            "Complete the assigned OABP mission by submitting a valid deliverable "
            "(proof) that satisfies its verification rule, to win the reward."
        ),
        backstory=(
            "A reliable execution agent. Given a mission, you re-read its exact "
            "verification requirement and submit a proof (free text or URL) that "
            "passes — a regex match for first_valid_match, or a real artefact "
            "(token address / GitHub repo) for oracle-verified missions."
        ),
        tools=[get_tool, submit_tool],
        llm=llm,
        allow_delegation=False,
        verbose=verbose,
    )

    return {"scout": scout, "worker": worker}


def build_tasks(agents: Dict[str, Agent]) -> List[Task]:
    """Build the scout -> worker task pipeline (worker depends on scout)."""
    scout = agents["scout"]
    worker = agents["worker"]

    scout_task = Task(
        description=(
            "List the open bounty missions on the OABP / AIGEN marketplace using "
            "the oabp_list_missions tool. Then pick the most promising mission "
            "and inspect it with oabp_get_mission. Report the chosen mission's "
            "id, title, reward (amount + currency), verification_type and the "
            "exact verification requirement (regex or oracle description)."
        ),
        expected_output=(
            "The chosen mission's id, reward, verification_type and the precise "
            "deliverable needed to win it."
        ),
        agent=scout,
    )

    worker_task = Task(
        description=(
            "Using the mission chosen by the scout, re-read it with "
            "oabp_get_mission if needed, then submit a deliverable that satisfies "
            "its verification rule using the oabp_submit_mission tool. Report "
            "whether the submission was accepted and any resolution returned."
        ),
        expected_output=(
            "Confirmation that a deliverable was submitted to the chosen mission, "
            "including the server's acknowledgement / resolution."
        ),
        agent=worker,
        context=[scout_task],
    )

    return [scout_task, worker_task]


def build_crew(
    *,
    client: Optional[OabpClient] = None,
    base_url: str = DEFAULT_BASE_URL,
    agent_id: Optional[str] = None,
    api_key: Optional[str] = None,
    llm: Optional[BaseLLM] = None,
    verbose: bool = False,
) -> Crew:
    """Assemble the two-agent (scout + worker) OABP :class:`~crewai.Crew`.

    Parameters
    ----------
    client:
        Pre-configured OABP SDK client (e.g. one wired to a mocked session for
        offline demos). If omitted, one is built from ``base_url`` / ``agent_id``
        / ``api_key``.
    base_url, agent_id, api_key:
        Used to build the SDK client when ``client`` is not supplied.
    llm:
        The model the agents reason with. Pass an :class:`OfflineScriptedLLM`
        for a deterministic, network-free ``kickoff()``; pass a real
        ``crewai.LLM`` in production. If ``None``, CrewAI falls back to its
        default model (which needs a provider API key at kickoff time).
    verbose:
        Forwarded to the agents and crew.

    Returns
    -------
    crewai.Crew
        A sequential crew: the scout discovers/chooses a mission, then the worker
        submits a deliverable to it.
    """
    if client is None:
        client = OabpClient(base_url=base_url, agent_id=agent_id, api_key=api_key)

    agents = build_agents(client, agent_id=agent_id, llm=llm, verbose=verbose)
    tasks = build_tasks(agents)

    return Crew(
        agents=[agents["scout"], agents["worker"]],
        tasks=tasks,
        process=Process.sequential,
        verbose=verbose,
    )


__all__ = [
    "OfflineScriptedLLM",
    "react_action",
    "react_final",
    "build_agents",
    "build_tasks",
    "build_crew",
    "DEFAULT_BASE_URL",
]
