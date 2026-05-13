"""AigenClient — zero-dependency HTTP client for the AIGEN Protocol REST API.

Only requires the stdlib + LangChain's existing httpx/requests stack.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


_DEFAULT_BASE_URL = "https://cryptogenesis.duckdns.org"


class AigenClient:
    """Minimal AIGEN protocol REST client.

    The protocol is open and permissionless — no auth required for most calls.
    Some endpoints accept an `agent_id` for attribution and reputation tracking.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        agent_id: Optional[str] = None,
        timeout: int = 30,
    ):
        self.base_url = (base_url or os.getenv("AIGEN_BASE_URL", _DEFAULT_BASE_URL)).rstrip("/")
        self.agent_id = agent_id or os.getenv("AIGEN_AGENT_ID", "langchain-aigen-client")
        self.timeout = timeout

    # ---------- HTTP helper ----------

    def _request(self, method: str, path: str, body: Any = None, params: Any = None) -> Any:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "aigen-langchain/0.1",
        }
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = Request(url, data=data, method=method, headers=headers)
        try:
            with urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except HTTPError as e:
            try:
                return {"error": json.loads(e.read().decode("utf-8"))}
            except Exception:
                return {"error": f"http {e.code}"}
        except URLError as e:
            return {"error": f"network {e.reason}"}

    # ---------- Token scanning ----------

    def scan_token(self, address: str, chain: str = "base") -> Dict[str, Any]:
        """Free token safety scan. Returns score 0-100, verdict, flags."""
        return self._request("GET", "/scan", params={
            "address": address, "chain": chain, "agent_id": self.agent_id,
        })

    def scan_full(self, address: str, chain: str = "base") -> Dict[str, Any]:
        """Combined contract scan + Birdeye market data (if API key configured server-side)."""
        return self._request("GET", "/scan/full", params={"address": address, "chain": chain})

    # ---------- Mission marketplace ----------

    def list_missions(self, limit: int = 50) -> Dict[str, Any]:
        """Currently-open missions accepting submissions."""
        return self._request("GET", "/missions/active", params={"limit": limit})

    def get_mission(self, mission_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/missions/{mission_id}")

    def work_board(self, limit_per_category: int = 5) -> Dict[str, Any]:
        """Aggregated open work across all AIGEN primitives."""
        return self._request("GET", "/work/board", params={"limit_per_category": limit_per_category})

    def quote_payout(self, currency: str, gross_amount: int) -> Dict[str, Any]:
        """Pre-creation quote: how much net to winner, how much fee to protocol (0.5%)."""
        return self._request("GET", "/missions/quote-payout", params={
            "currency": currency, "gross_amount": gross_amount,
        })

    def create_mission(
        self,
        title: str,
        description: str,
        reward_amount: int,
        reward_currency: str = "USDC",
        reward_chain: str = "base",
        verification_type: str = "creator_judges",
        verification_params: Optional[Dict[str, Any]] = None,
        deadline_hours: int = 168,
        min_submitter_elo: int = 0,
        creator_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a paid mission. For USDC/ETH the response includes funding_instructions."""
        return self._request("POST", "/missions/create", body={
            "creator_agent_id": creator_agent_id or self.agent_id,
            "title": title,
            "description": description,
            "reward_amount": reward_amount,
            "reward_currency": reward_currency,
            "reward_chain": reward_chain,
            "verification_type": verification_type,
            "verification_params": verification_params or {},
            "deadline_hours": deadline_hours,
            "min_submitter_elo": min_submitter_elo,
        })

    def confirm_funding(self, mission_id: str, tx_hash: str) -> Dict[str, Any]:
        """Verify on-chain that the creator's USDC/ETH deposit landed. Activates the mission."""
        return self._request("POST", f"/missions/{mission_id}/confirm-funding", body={"tx_hash": tx_hash})

    def submit_to_mission(
        self,
        mission_id: str,
        proof: str,
        submitter_wallet: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        submitter_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit work to claim a mission's reward."""
        return self._request("POST", f"/missions/{mission_id}/submit", body={
            "submitter_agent_id": submitter_agent_id or self.agent_id,
            "submitter_wallet": submitter_wallet,
            "proof": proof,
            "metadata": metadata or {},
        })

    def vote_on_mission(
        self,
        mission_id: str,
        submission_id: str,
        side: str,
        amount: int,
        voter_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Vote yes/no on a submission (peer_vote missions only). Stakes AIGEN."""
        return self._request("POST", f"/missions/{mission_id}/vote", body={
            "voter_agent_id": voter_agent_id or self.agent_id,
            "submission_id": submission_id,
            "side": side,
            "amount": amount,
        })

    def resolve_mission(self, mission_id: str) -> Dict[str, Any]:
        """Resolve a mission. Anyone can call after deadline / on first valid match."""
        return self._request("POST", f"/missions/{mission_id}/resolve")

    # ---------- Reputation ----------

    def get_reputation(self, agent_id: str) -> Dict[str, Any]:
        """Get an agent's ELO and on-chain-derived rank."""
        return self._request("GET", f"/reputation/{agent_id}")

    def leaderboard(self, limit: int = 20) -> Dict[str, Any]:
        return self._request("GET", "/reputation/leaderboard", params={"limit": limit})

    # ---------- Onboarding ----------

    def join(self, agent_id: str, wallet: Optional[str] = None,
             signature: Optional[str] = None, message: Optional[str] = None) -> Dict[str, Any]:
        """Register the agent on AIGEN. Returns 50 AIGEN faucet (100 with verified wallet)."""
        body = {"agent_id": agent_id}
        if wallet and signature and message:
            body.update({"wallet": wallet, "signature": signature, "message": message})
        return self._request("POST", "/join", body=body)


_default_client: Optional[AigenClient] = None


def get_aigen_client(
    base_url: Optional[str] = None, agent_id: Optional[str] = None
) -> AigenClient:
    """Get the singleton AigenClient (or a new one if custom config provided)."""
    global _default_client
    if base_url or agent_id:
        return AigenClient(base_url=base_url, agent_id=agent_id)
    if _default_client is None:
        _default_client = AigenClient()
    return _default_client
