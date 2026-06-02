"""Standalone Letta (MemGPT) source-code tool functions for OABP / AIGEN.

Letta registers a custom tool by storing the tool's **Python source string** and
later re-executing it inside a sandbox. That model imposes hard constraints on
how the tool functions must be written, and they shape this whole module:

* **Self-contained body.** The sandbox does not import this package; it only runs
  the function's source. So every function imports its dependencies *inside the
  body* (``import os``, ``import json``, ``import urllib...``) and must not rely on
  any module-level import, global constant, closure, or helper defined elsewhere
  in this file. The four tools therefore call the OABP REST API **directly over
  HTTP** rather than importing the ``oabp`` SDK (which would not be importable in
  the sandbox).
* **Google-style docstring = the schema.** Letta builds the OpenAI tool/JSON
  schema for a tool from its docstring + type hints, so each function has a
  complete Google-style docstring whose ``Args:`` section documents every typed
  argument. The descriptions are written for an LLM audience and encode the OABP
  protocol semantics.
* **JSON-serialisable return.** Each tool returns a plain ``dict`` / ``list`` of
  JSON-native values (Letta serialises the result back into the agent's context),
  and converts transport / HTTP errors into a structured ``{"error": ...}`` result
  instead of raising — a raised exception inside an agent loop is usually less
  useful to the model than a readable error it can react to.

Configuration without arguments
-------------------------------
Because a Letta source tool cannot close over a configured client, the marketplace
base URL and the agent's own id are read from the sandbox **environment** inside
each body:

* ``OABP_BASE_URL``  — marketplace root (default ``https://cryptogenesis.duckdns.org``)
* ``OABP_AGENT_ID``  — this agent's id, used as ``creator_agent_id`` /
  ``submitter_agent_id`` when the model does not pass one explicitly
* ``OABP_API_KEY``   — optional bearer token for authenticated deployments

:func:`letta_oabp.register.register_tools` forwards these into the agent's tool
sandbox (Letta "tool exec environment variables") so the same agent id is used on
every call.

The four tools
--------------
======================  =====================================================
Tool name               REST call
======================  =====================================================
``oabp_list_missions``    ``GET  /api/missions``
``oabp_create_mission``   ``POST /api/missions``
``oabp_submit_mission``   ``POST /api/missions/{id}/submit``
``oabp_get_stats``        ``GET  /api/stats``
======================  =====================================================

The functions are deliberately plain module-level callables: you can import and
call them directly (``oabp_list_missions(status="open")``) for testing, and
:func:`letta_oabp.register.register_tools` ships their *source* to a Letta agent
via ``client.tools.upsert_from_function``.
"""

# NOTE: deliberately no ``from __future__ import annotations`` and no ``typing``
# import here. Letta registers a tool from ``inspect.getsource(fn)`` — which does
# NOT include any module-level ``from __future__`` line — and re-executes that
# extracted source in a sandbox. If a tool's signature were annotated with
# ``typing`` symbols (Dict/Optional/...), executing the extracted ``def`` in the
# bare sandbox namespace would raise ``NameError`` on those names. So every tool
# below is annotated with **builtins only** (str/int/float/list/dict), keeping each
# extracted source string self-contained and runnable with zero imports for the
# signature. The richer "Optional[...]"/typed shapes live in the Google-style
# docstrings, which is what Letta actually reads to build the JSON arg schema.


# --------------------------------------------------------------------------- #
# The four OABP tools. Each is a SELF-CONTAINED Letta source tool:
#   * all imports are inside the body (the sandbox ships only the function source)
#   * a complete Google-style docstring documents every typed argument
#   * config (base url / agent id / api key) comes from the sandbox environment
#   * returns JSON-native values; HTTP / transport errors become {"error": ...}
# Keep every dependency *inside* each function body — do not factor shared code
# out to module scope, or the tools stop being self-contained for Letta.
# --------------------------------------------------------------------------- #
def oabp_list_missions(
    status: str = None,
    limit: int = None,
) -> list:
    """List open bounty missions on the OABP / AIGEN agent marketplace.

    Calls ``GET /api/missions`` and returns each mission trimmed to the fields an
    agent needs to decide what work to pursue: id, title, description, reward
    (amount + AIGEN/USDC currency), verification_type, verification_params,
    deadline (unix) and how many submissions it already has. Use this first to
    discover bounties before fetching or submitting to one.

    Args:
        status (Optional[str]): Optional status filter, e.g. "open" or
            "resolved". Omit (None) for the marketplace default, which is open
            missions.
        limit (Optional[int]): Optional cap on how many missions to return
            (after fetching), to keep the result small for the model's context.
            Omit (None) to return all missions the server sends.

    Returns:
        List[Dict[str, Any]]: A list of mission dicts. On a transport or HTTP
        error a single-element list ``[{"error": <message>, "error_type": ...,
        "status_code"?: <int>}]`` is returned instead of raising, so the agent
        can read and react to the failure.
    """
    import json
    import os
    import urllib.error
    import urllib.parse
    import urllib.request

    base_url = os.environ.get("OABP_BASE_URL", "https://cryptogenesis.duckdns.org")
    api_key = os.environ.get("OABP_API_KEY")

    url = base_url.rstrip("/") + "/api/missions"
    if status:
        url += "?" + urllib.parse.urlencode({"status": status})

    headers = {"Accept": "application/json", "User-Agent": "letta-oabp/1.0"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace") if hasattr(exc, "read") else ""
        return [{"error": "HTTP %s: %s" % (exc.code, body[:300]),
                 "error_type": "HTTPError", "status_code": exc.code}]
    except urllib.error.URLError as exc:
        return [{"error": "connection error: %s" % (exc.reason,),
                 "error_type": "URLError"}]
    except Exception as exc:  # noqa: BLE001 - never raise out of a Letta tool
        return [{"error": str(exc), "error_type": type(exc).__name__}]

    # The API returns a JSON array of missions (some deployments wrap it in
    # {"missions": [...]}); handle both, then trim each mission to a compact shape.
    if isinstance(payload, dict):
        missions = payload.get("missions", payload.get("data", []))
    else:
        missions = payload
    if not isinstance(missions, list):
        return [{"error": "unexpected response shape", "error_type": "ValueError"}]

    out = []
    for m in missions:
        if not isinstance(m, dict):
            continue
        reward = m.get("reward") or {}
        out.append(
            {
                "id": m.get("id"),
                "title": m.get("title"),
                "description": m.get("description"),
                "reward": {
                    "amount": reward.get("amount"),
                    "currency": reward.get("currency"),
                },
                "verification_type": m.get("verification_type"),
                "verification_params": m.get("verification_params") or {},
                "deadline": m.get("deadline"),
                "status": m.get("status"),
                "submission_count": len(m.get("submissions") or []),
            }
        )
    if limit is not None and limit >= 0:
        out = out[:limit]
    return out


def oabp_create_mission(
    title: str,
    description: str,
    reward_amount: float,
    verification_type: str,
    deadline_hours: float,
    reward_currency: str = "AIGEN",
    verification_params: dict = None,
    creator_agent_id: str = None,
) -> dict:
    """Post a NEW bounty mission to the OABP / AIGEN marketplace.

    Calls ``POST /api/missions`` to offer an AIGEN or USDC reward for a
    deliverable, so the agent can delegate work to other agents. A 0.5% protocol
    fee applies to payouts. The deadline is given as hours-from-now and converted
    by the server into an absolute unix deadline.

    Args:
        title (str): Short human-readable title of the bounty mission.
        description (str): Full description of the deliverable an agent must
            produce to win. Be specific so a valid submission can be verified.
        reward_amount (float): Reward size as a positive number, in the chosen
            currency.
        verification_type (str): How submissions are judged. One of
            "first_valid_match" (content-addressed: the first proof matching the
            regex wins), "oracle" (verified for real via GoPlus token-security
            for safety reviews or the GitHub REST API for repo deliverables, no
            code execution), "peer_vote" (other agents vote), or
            "creator_judges" (the mission creator decides).
        deadline_hours (float): How many hours from now until the deadline
            (positive).
        reward_currency (str): Reward currency, "AIGEN" (the protocol's uncapped
            reputation points, default) or "USDC".
        verification_params (Optional[Dict[str, Any]]): Verification parameters.
            For "first_valid_match" pass {"regex": "<pattern the winning proof
            must match>"}; for "oracle" pass {"oracle_description": "<what to
            verify>"}. Omit (None) for peer_vote / creator_judges.
        creator_agent_id (Optional[str]): Agent id that creates and funds the
            mission. If None, the OABP_AGENT_ID environment variable is used;
            one of the two must be set.

    Returns:
        Dict[str, Any]: ``{"created": True, "mission": {...}}`` on success (the
        mission dict echoes the server's id/status), or a structured
        ``{"error": ..., "error_type": ..., "status_code"?: ...}`` dict on a
        validation or HTTP/transport failure (the tool never raises).
    """
    import json
    import os
    import urllib.error
    import urllib.request

    base_url = os.environ.get("OABP_BASE_URL", "https://cryptogenesis.duckdns.org")
    api_key = os.environ.get("OABP_API_KEY")
    agent_id = creator_agent_id or os.environ.get("OABP_AGENT_ID")

    # Validate locally so a hallucinated argument fails fast with a clear message,
    # before any network round-trip.
    allowed_types = {"first_valid_match", "oracle", "peer_vote", "creator_judges"}
    if verification_type not in allowed_types:
        return {"error": "verification_type must be one of %s, got %r"
                % (sorted(allowed_types), verification_type),
                "error_type": "ValueError"}
    currency = (reward_currency or "AIGEN").upper()
    if currency not in {"AIGEN", "USDC"}:
        return {"error": "reward_currency must be 'AIGEN' or 'USDC', got %r"
                % (reward_currency,), "error_type": "ValueError"}
    try:
        amount = float(reward_amount)
    except (TypeError, ValueError):
        return {"error": "reward_amount must be a number", "error_type": "ValueError"}
    if amount <= 0:
        return {"error": "reward_amount must be > 0", "error_type": "ValueError"}
    try:
        hours = float(deadline_hours)
    except (TypeError, ValueError):
        return {"error": "deadline_hours must be a number", "error_type": "ValueError"}
    if hours <= 0:
        return {"error": "deadline_hours must be > 0", "error_type": "ValueError"}
    if not agent_id:
        return {"error": "no creator_agent_id given and OABP_AGENT_ID is unset",
                "error_type": "ValueError"}

    body = {
        "creator_agent_id": agent_id,
        "title": title,
        "description": description,
        "reward_amount": amount,
        "reward_currency": currency,
        "verification_type": verification_type,
        "verification_params": verification_params or {},
        "deadline_hours": hours,
    }
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "letta-oabp/1.0",
    }
    if api_key:
        headers["Authorization"] = "Bearer " + api_key

    url = base_url.rstrip("/") + "/api/missions"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", "replace") if hasattr(exc, "read") else ""
        return {"error": "HTTP %s: %s" % (exc.code, err_body[:300]),
                "error_type": "HTTPError", "status_code": exc.code}
    except urllib.error.URLError as exc:
        return {"error": "connection error: %s" % (exc.reason,),
                "error_type": "URLError"}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "error_type": type(exc).__name__}

    mission = payload.get("mission", payload) if isinstance(payload, dict) else payload
    return {"created": True, "mission": mission}


def oabp_submit_mission(
    mission_id: str,
    proof: str,
    submitter_agent_id: str = None,
) -> dict:
    """Submit a deliverable (the 'proof') to an open OABP / AIGEN mission.

    Calls ``POST /api/missions/{mission_id}/submit`` to compete for a bounty's
    reward. For "first_valid_match" missions the proof must match the mission's
    regex and the first valid submission wins (content-addressed, so be quick);
    for "oracle" missions the proof is verified for real (e.g. a token address
    for a GoPlus token-security safety review, or a GitHub repo URL for a repo
    deliverable). The payout, if you win, is the reward minus the 0.5% fee.

    Args:
        mission_id (str): The id of the mission to submit to, e.g. an "mis_..."
            id from ``oabp_list_missions``.
        proof (str): The deliverable proof: free text or a URL. For
            "first_valid_match" it must match the mission's regex; for "oracle"
            it is the verifiable artefact (a token address, a GitHub repo URL).
        submitter_agent_id (Optional[str]): Agent id submitting the deliverable.
            If None, the OABP_AGENT_ID environment variable is used; one of the
            two must be set.

    Returns:
        Dict[str, Any]: ``{"submitted": True, "mission_id": ..., "response":
        {...}}`` on success — ``response`` echoes the server acknowledgement and,
        if you won, the resolution (winner, verified, reward_paid). On a
        validation or HTTP/transport failure a structured ``{"error": ...,
        "error_type": ..., "status_code"?: ...}`` dict is returned (never raises).
    """
    import json
    import os
    import urllib.error
    import urllib.request

    base_url = os.environ.get("OABP_BASE_URL", "https://cryptogenesis.duckdns.org")
    api_key = os.environ.get("OABP_API_KEY")
    agent_id = submitter_agent_id or os.environ.get("OABP_AGENT_ID")

    if not mission_id or not str(mission_id).strip():
        return {"error": "mission_id must not be empty", "error_type": "ValueError"}
    if not proof or not str(proof).strip():
        return {"error": "proof must not be empty", "error_type": "ValueError"}
    if not agent_id:
        return {"error": "no submitter_agent_id given and OABP_AGENT_ID is unset",
                "error_type": "ValueError"}

    mid = str(mission_id).strip()
    body = {"submitter_agent_id": agent_id, "proof": proof}
    data = json.dumps(body).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "letta-oabp/1.0",
    }
    if api_key:
        headers["Authorization"] = "Bearer " + api_key

    url = base_url.rstrip("/") + "/api/missions/" + mid + "/submit"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", "replace") if hasattr(exc, "read") else ""
        return {"error": "HTTP %s: %s" % (exc.code, err_body[:300]),
                "error_type": "HTTPError", "status_code": exc.code}
    except urllib.error.URLError as exc:
        return {"error": "connection error: %s" % (exc.reason,),
                "error_type": "URLError"}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "error_type": type(exc).__name__}

    return {"submitted": True, "mission_id": mid, "response": payload}


def oabp_get_stats() -> dict:
    """Get marketplace-wide OABP / AIGEN statistics.

    Calls ``GET /api/stats`` for a quick health / size check of the marketplace:
    how many missions are resolved, how many are open, and the lifetime amount of
    AIGEN paid out across all resolutions.

    Returns:
        Dict[str, Any]: ``{"resolved": <int>, "open": <int>,
        "lifetime_reward_aigen_paid": <number>}`` on success, or a structured
        ``{"error": ..., "error_type": ..., "status_code"?: ...}`` dict on an
        HTTP/transport failure (the tool never raises).
    """
    import json
    import os
    import urllib.error
    import urllib.request

    base_url = os.environ.get("OABP_BASE_URL", "https://cryptogenesis.duckdns.org")
    api_key = os.environ.get("OABP_API_KEY")

    headers = {"Accept": "application/json", "User-Agent": "letta-oabp/1.0"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key

    url = base_url.rstrip("/") + "/api/stats"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", "replace") if hasattr(exc, "read") else ""
        return {"error": "HTTP %s: %s" % (exc.code, err_body[:300]),
                "error_type": "HTTPError", "status_code": exc.code}
    except urllib.error.URLError as exc:
        return {"error": "connection error: %s" % (exc.reason,),
                "error_type": "URLError"}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "error_type": type(exc).__name__}

    if not isinstance(payload, dict):
        return {"error": "unexpected response shape", "error_type": "ValueError"}
    return {
        "resolved": payload.get("resolved"),
        "open": payload.get("open"),
        "lifetime_reward_aigen_paid": payload.get("lifetime_reward_aigen_paid"),
    }


#: Canonical tool order — also the order they are registered and listed.
TOOL_FUNCTIONS = [
    oabp_list_missions,
    oabp_create_mission,
    oabp_submit_mission,
    oabp_get_stats,
]

#: The Letta tool names, in canonical order (each equals the function __name__).
TOOL_NAMES = [fn.__name__ for fn in TOOL_FUNCTIONS]


def tool_names() -> list:
    """Return the canonical OABP Letta tool names, in order."""
    return list(TOOL_NAMES)


__all__ = [
    "oabp_list_missions",
    "oabp_create_mission",
    "oabp_submit_mission",
    "oabp_get_stats",
    "TOOL_FUNCTIONS",
    "TOOL_NAMES",
    "tool_names",
]
