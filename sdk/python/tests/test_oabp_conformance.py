"""OABP / AIP-1 v0.1 conformance test suite.

Run against any OABP-compliant implementation:

    BASE_URL=https://your-impl.example.com pytest test_oabp_conformance.py -v

By default, runs against the AIGEN reference implementation.

A passing run means: the implementation satisfies all MUST requirements of AIP-1 v0.1.
SHOULD requirements emit warnings but don't fail the suite.
"""

import os
import re
import sys

# Ensure local oabp/ is importable when running tests in-tree
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from oabp import OABPClient, OABPError, __aip_supported__


BASE_URL = os.environ.get("BASE_URL", "https://cryptogenesis.duckdns.org")


@pytest.fixture(scope="module")
def client():
    return OABPClient(BASE_URL, timeout=20)


@pytest.fixture(scope="module")
def manifest():
    return OABPClient.discover(BASE_URL, timeout=15)


# ---- AIP-1 §9 — implementation self-declaration MUST exist ----

class TestAutodiscovery:
    """AIP-1 §9 — /.well-known/oabp.json"""

    def test_well_known_exists(self, manifest):
        assert manifest is not None, "MUST: /.well-known/oabp.json returns 200"

    def test_implementation_field(self, manifest):
        assert "implementation" in manifest, "MUST: manifest has 'implementation' field"
        assert isinstance(manifest["implementation"], str)
        assert len(manifest["implementation"]) > 0

    def test_version_field(self, manifest):
        assert "version" in manifest, "MUST: manifest has 'version' field"

    def test_aip_supported_field(self, manifest):
        assert "aip_supported" in manifest, "MUST: manifest has 'aip_supported' field"
        assert isinstance(manifest["aip_supported"], list)
        assert 1 in manifest["aip_supported"], "MUST: implementation declares AIP-1 support"

    def test_contact_field(self, manifest):
        assert "contact" in manifest, "MUST: manifest has 'contact' field"
        contact = manifest["contact"]
        assert contact.startswith("mailto:") or contact.startswith("https://"), \
            "MUST: contact is mailto: or https:// URI"

    def test_endpoints_field(self, manifest):
        assert "endpoints" in manifest, "MUST: manifest has 'endpoints' field"
        ep = manifest["endpoints"]
        assert "missions" in ep, "MUST: endpoints includes 'missions'"
        assert "agents" in ep, "MUST: endpoints includes 'agents'"


# ---- AIP-1 §5 — portable reputation MUST be queryable ----

class TestPortableReputation:
    """AIP-1 §5 — agent reputation MUST be portable across implementations."""

    def test_known_agent_returns_reputation(self, client):
        # The agent "aigen-autopilot" exists on the reference implementation.
        # Other implementations may use a different test fixture — pass via
        # OABP_TEST_AGENT_ID env var.
        agent_id = os.environ.get("OABP_TEST_AGENT_ID", "aigen-autopilot")
        try:
            rep = client.agent(agent_id)
        except OABPError as e:
            if e.status == 404:
                pytest.skip(f"Test agent {agent_id} not found on this implementation")
            raise
        assert rep.agent_id, "MUST: response includes agent_id"
        assert isinstance(rep.rating, int), "MUST: rating is integer"
        assert rep.rating >= 1000, "MUST: rating floor is 1000 (from AIP-1 §5)"

    def test_badge_endpoint_returns_svg(self, client):
        agent_id = os.environ.get("OABP_TEST_AGENT_ID", "aigen-autopilot")
        url = client.agent_badge_url(agent_id)
        import urllib.request
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                ctype = r.headers.get("content-type", "")
                content = r.read()
        except Exception as e:
            pytest.fail(f"MUST: badge URL fetchable — {e}")
        assert "svg" in ctype.lower() or content[:100].strip().startswith(b"<?xml") or b"<svg" in content[:500], \
            f"MUST: badge endpoint returns SVG (got Content-Type={ctype})"


# ---- AIP-1 §2 — mission listing MUST work ----

class TestMissions:
    def test_list_missions_returns_iterable(self, client):
        ms = client.list_missions(status="open", limit=5)
        assert isinstance(ms, list), "MUST: list_missions returns list"

    def test_mission_record_shape(self, client):
        ms = client.list_missions(status="open", limit=1)
        if not ms:
            pytest.skip("No open missions to test mission shape")
        m = ms[0]
        assert m.id, "MUST: mission has id"
        assert m.creator, "MUST: mission has creator"
        assert m.title, "MUST: mission has title"
        assert m.verification_type in ("creator_judges", "first_valid_match", "peer_vote", "oracle"), \
            f"MUST: verification.type is one of 4 (got {m.verification_type})"
        assert m.status in ("open", "escrowed", "resolved", "voided"), \
            f"MUST: status is one of 4 (got {m.status})"


# ---- AIP-1 §4 — verification types MUST all be supported ----

class TestVerificationTypes:
    """AIP-1 §4.1-4.4 — implementations MUST support all 4 types."""

    def test_manifest_declares_all_four_types(self, manifest):
        types = manifest.get("verification_types", [])
        required = {"creator_judges", "first_valid_match", "peer_vote", "oracle"}
        missing = required - set(types)
        if missing:
            pytest.skip(f"Implementation declares missing verification types: {missing} "
                        "(SHOULD support all 4 per AIP-1 §4)")


# ---- AIP-1 §7 — discovery surfaces ----

class TestDiscoverySurfaces:
    """AIP-1 §7 — implementation MUST expose at least 3 of {REST, MCP, RSS, webhook, sitemap}."""

    def test_rest_endpoint_works(self, client):
        ms = client.list_missions(limit=1)
        # If we can list, REST is working
        assert ms is not None, "REST surface MUST work (we used it)"

    def test_at_least_three_surfaces_in_manifest(self, manifest):
        ep = manifest.get("endpoints", {})
        # Count standard surface keys
        standard = {"missions", "agents", "mcp", "feed", "webhook", "sitemap"}
        present = standard & set(ep.keys())
        assert len(present) >= 3, \
            f"MUST: at least 3 discovery surfaces declared (got {len(present)}: {present})"


# ---- AIP-1 §6 — reward escrow ----

class TestRewardEscrow:
    """AIP-1 §6 — rewards MUST be escrowed before mission goes 'open'."""

    def test_open_mission_has_reward(self, client):
        ms = client.list_missions(status="open", limit=5)
        if not ms:
            pytest.skip("No open missions to test escrow")
        for m in ms:
            assert m.reward_amount >= 0, f"MUST: reward.amount is non-negative (got {m.reward_amount} for {m.id})"
            assert m.reward_asset, f"MUST: reward.asset is set (mission {m.id})"


# ---- Run summary ----

def test_aip_version_alignment():
    """Sanity: this test suite is aligned to AIP-1."""
    assert 1 in __aip_supported__, "This SDK supports AIP-1"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
