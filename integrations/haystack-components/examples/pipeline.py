"""Build and run a Haystack OABP pipeline: lister -> filter -> submitter.

This wires three Haystack 2.x components into a single
:class:`~haystack.Pipeline`:

    OabpMissionLister  ->  MissionPicker (custom @component)  ->  OabpSubmitter

* ``OabpMissionLister`` lists open bounty missions on the live OABP / AIGEN
  marketplace (https://cryptogenesis.duckdns.org).
* ``MissionPicker`` is a small **custom Haystack component** (defined here) that
  filters the missions to the best ``first_valid_match`` candidate and emits the
  ``mission_id`` and the ``proof`` string that would satisfy its regex.
* ``OabpSubmitter`` would submit that proof to claim the bounty.

Read-only by default
--------------------
By default the pipeline is built **without** connecting the submitter's inputs
(and the submitter is given a no-op ``dry_run`` proof), so running it performs
only the read (list) against the live API and *reports* what it would submit — it
never writes. Pass ``--write`` to actually connect the picker to the submitter and
perform a real, non-idempotent submission (AIGEN is play-money, but still — use an
``--agent-id`` you control).

Run
---
    # Read-only: list live missions and show the chosen submission (no write):
    python examples/pipeline.py --agent-id my-agent

    # Allow a real submission to the chosen mission:
    python examples/pipeline.py --agent-id my-agent --write

Works with or without ``haystack-ai`` installed: with it, this is a real
``haystack.Pipeline``; without it, ``haystack_oabp`` provides a minimal sequential
Pipeline stand-in so the example still runs end-to-end against the live API.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional

# Make the package importable when run straight from the repo checkout.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from haystack_oabp import (  # noqa: E402
    HAS_HAYSTACK,
    OabpClient,
    OabpMissionLister,
    OabpSubmitter,
    Pipeline,
    component,
    component_output_types,
)


# --------------------------------------------------------------------------- #
# A custom Haystack component that filters/selects a mission to act on.
# --------------------------------------------------------------------------- #
@component
class MissionPicker:
    """Pick the best actionable mission from a list and derive a proof.

    Input ``missions`` is the list emitted by :class:`OabpMissionLister`. This
    component keeps only **open ``first_valid_match``** missions (the ones an
    agent can satisfy purely from a regex, no external work), picks the highest
    reward, and derives a ``proof`` string that matches the mission's regex when
    one is trivially satisfiable. It outputs the chosen ``mission_id``, the
    ``proof``, and the ``mission`` dict (plus a ``reason`` when nothing matched).
    """

    def __init__(self, prefer_currency: Optional[str] = None) -> None:
        self.prefer_currency = prefer_currency

    @staticmethod
    def _proof_for_regex(pattern: Optional[str]) -> Optional[str]:
        """Return a string satisfying ``pattern`` for simple literal regexes.

        Handles the common ``first_valid_match`` case where the regex is a plain
        literal token (optionally anchored), e.g. ``^OABP-OK$`` -> ``OABP-OK``.
        Returns ``None`` when the pattern is non-trivial (so we don't guess).
        """
        if not pattern:
            return None
        literal = pattern.strip()
        if literal.startswith("^"):
            literal = literal[1:]
        if literal.endswith("$"):
            literal = literal[:-1]
        # Accept only plain literals (letters/digits/.-_ /space) — no regex metachars.
        if literal and re.fullmatch(r"[\w .\-/]+", literal):
            try:
                if re.search(pattern, literal):
                    return literal
            except re.error:
                return None
        return None

    @component.output_types(
        mission_id=str, proof=str, mission=Dict[str, Any], reason=str
    )
    def run(self, missions: List[Dict[str, Any]]) -> Dict[str, Any]:
        candidates = [
            m
            for m in (missions or [])
            if m.get("verification_type") == "first_valid_match"
            and (m.get("status") in (None, "open"))
        ]
        if self.prefer_currency:
            pref = [
                m
                for m in candidates
                if (m.get("reward") or {}).get("currency") == self.prefer_currency
            ]
            candidates = pref or candidates

        # Highest reward first.
        candidates.sort(
            key=lambda m: float((m.get("reward") or {}).get("amount", 0) or 0),
            reverse=True,
        )
        for mission in candidates:
            params = mission.get("verification_params") or {}
            proof = self._proof_for_regex(params.get("regex"))
            if proof is not None:
                return {
                    "mission_id": mission["id"],
                    "proof": proof,
                    "mission": mission,
                    "reason": "selected highest-reward first_valid_match mission",
                }
        return {
            "mission_id": "",
            "proof": "",
            "mission": {},
            "reason": (
                "no open first_valid_match mission with a trivially-satisfiable "
                "regex was found"
            ),
        }


def build_pipeline(
    agent_id: str,
    *,
    write: bool,
    client: Optional[OabpClient] = None,
) -> Pipeline:
    """Construct the lister -> picker -> submitter pipeline.

    In ``write`` mode the picker's ``mission_id`` / ``proof`` outputs are
    connected to the submitter's inputs (a real submission happens on run). In
    read-only mode they are left unconnected so running the pipeline performs only
    the read; the caller inspects the picker output to see what *would* be
    submitted.
    """
    client = client or OabpClient(agent_id=agent_id)
    lister = OabpMissionLister(agent_id=agent_id, client=client)
    picker = MissionPicker()
    submitter = OabpSubmitter(agent_id=agent_id, client=client)

    pipe = Pipeline()
    pipe.add_component("lister", lister)
    pipe.add_component("picker", picker)
    pipe.add_component("submitter", submitter)

    # lister.missions -> picker.missions  (always)
    pipe.connect("lister.missions", "picker.missions")

    if write:
        # picker -> submitter: actually submit the chosen proof (non-idempotent).
        pipe.connect("picker.mission_id", "submitter.mission_id")
        pipe.connect("picker.proof", "submitter.proof")

    return pipe


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent-id",
        default=os.environ.get("OABP_AGENT_ID", "example-haystack-agent"),
        help="OABP agent id to act as (default: $OABP_AGENT_ID or 'example-haystack-agent').",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Connect picker -> submitter and perform a REAL submission to the chosen mission.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max missions to fetch from the marketplace (default: 20).",
    )
    args = parser.parse_args(argv)

    print(
        f"[pipeline] haystack installed={HAS_HAYSTACK} agent_id={args.agent_id} "
        f"write={args.write}"
    )
    # Show the components' declared @output_types (works in both modes).
    for name, comp in (
        ("lister", OabpMissionLister(agent_id=args.agent_id)),
        ("picker", MissionPicker()),
        ("submitter", OabpSubmitter(agent_id=args.agent_id)),
    ):
        print(f"[pipeline] {name} outputs: {sorted(component_output_types(comp))}")

    pipe = build_pipeline(args.agent_id, write=args.write)
    print(f"\n[pipeline] running against the live marketplace (limit={args.limit})...")
    result = pipe.run({"lister": {"limit": args.limit}})

    # The picker output tells us what was (or would be) submitted.
    picker_out = result.get("picker", {})
    if picker_out:
        chosen_id = picker_out.get("mission_id") or "(none)"
        print("\n=== Mission selected by the filter ===")
        print(f"  mission_id : {chosen_id}")
        print(f"  proof      : {picker_out.get('proof')!r}")
        print(f"  reason     : {picker_out.get('reason')}")

    if args.write:
        submit_out = result.get("submitter", {})
        print("\n=== Submission result (live write) ===")
        print(json.dumps(submit_out, indent=2, default=str))
    else:
        print(
            "\n[pipeline] read-only mode: no submission was made "
            "(pass --write to connect picker -> submitter and submit)."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
