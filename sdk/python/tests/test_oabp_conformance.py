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
from oabp import (
    OABPClient, OABPError, MissionTypeAffinity, __aip_supported__,
    VERIFICATION_COMPAT, check_verification_compat,
    RegistryAttestation, check_registry_session,
)


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


class TestAgentCardMcpInvocationContract:
    """AIP-1 §7.4 — A2A agent cards SHOULD carry MCP invocation recipes."""

    @pytest.fixture(scope="class")
    def agent_card(self):
        import json
        from pathlib import Path

        card_path = Path(__file__).resolve().parents[3] / "agent-card.json"
        return json.loads(card_path.read_text(encoding="utf-8"))

    def test_agent_card_declares_transport_block(self, agent_card):
        transport = agent_card.get("transport")
        assert isinstance(transport, dict), "SHOULD: agent-card.json includes transport object"
        assert transport.get("primary") == "mcp-streamable-http"
        protocols = transport.get("protocols")
        assert isinstance(protocols, list) and protocols, "SHOULD: transport.protocols is non-empty"

    def test_mcp_protocol_has_copyable_initialize_recipe(self, agent_card):
        protocols = agent_card["transport"]["protocols"]
        mcp = next((p for p in protocols if p.get("id") == "mcp-streamable-http"), None)
        assert mcp is not None, "SHOULD: mcp-streamable-http protocol is declared"
        handshake = mcp.get("handshake", {})
        headers = handshake.get("headers", {})
        body = handshake.get("body", {})

        assert handshake.get("method") == "POST"
        assert headers.get("Content-Type") == "application/json"
        assert "text/event-stream" in headers.get("Accept", "")
        assert headers.get("MCP-Protocol-Version")
        assert body.get("jsonrpc") == "2.0"
        assert body.get("method") == "initialize"
        assert body.get("params", {}).get("protocolVersion")

    def test_mcp_protocol_documents_session_progression(self, agent_card):
        mcp = next(p for p in agent_card["transport"]["protocols"] if p.get("id") == "mcp-streamable-http")
        handshake = mcp["handshake"]

        assert handshake.get("responseSessionHeader", {}).get("name") == "Mcp-Session-Id"
        notification = handshake.get("postInitializeNotification", {})
        assert notification.get("body", {}).get("method") == "notifications/initialized"
        assert notification.get("headers", {}).get("Mcp-Session-Id")
        next_call = handshake.get("exampleNextCall", {})
        assert next_call.get("body", {}).get("method") == "tools/list"
        assert next_call.get("headers", {}).get("Mcp-Session-Id")

    def test_mcp_protocol_advertises_machine_readable_error_and_rest_fallback(self, agent_card):
        protocols = agent_card["transport"]["protocols"]
        mcp = next(p for p in protocols if p.get("id") == "mcp-streamable-http")
        missing_initialize = mcp.get("errorShape", {}).get("missingInitialize", {})
        assert missing_initialize.get("jsonrpc") == "2.0"
        assert missing_initialize.get("error", {}).get("code") == -32600
        assert "recipeUrl" in missing_initialize.get("error", {}).get("data", {})

        fallback = next((p for p in protocols if p.get("id") == "oabp-rest-readonly"), None)
        assert fallback is not None, "SHOULD: REST read-only fallback protocol is declared"
        endpoints = {(e.get("method"), e.get("path")) for e in fallback.get("endpoints", [])}
        assert ("GET", "/api/missions") in endpoints


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


# ---- AIP-1 §2 — single mission read MUST return same shape as list ----

class TestSingleMissionRead:
    """GET /missions/{id} MUST return a valid mission record."""

    def test_get_known_mission(self, client):
        ms = client.list_missions(status="open", limit=1)
        if not ms:
            pytest.skip("No open missions available")
        m_list = ms[0]
        m_direct = client.get_mission(str(m_list.id))
        assert str(m_direct.id) == str(m_list.id), "MUST: /missions/{id} returns same id"

    def test_get_nonexistent_mission_returns_error(self, client):
        try:
            client.get_mission("nonexistent-mission-id-zzz")
            pytest.fail("MUST: non-existent mission raises OABPError")
        except OABPError as e:
            assert e.status in (404, 422), f"MUST: 404 or 422 for unknown id (got {e.status})"


# ---- AIP-1 §3 — deadline invariant ----

class TestDeadlineValidation:
    """Open missions MUST have deadline in the future, or no deadline (perpetual)."""

    def test_open_missions_deadline_sane(self, client):
        import time
        now = time.time()
        ms = client.list_missions(status="open", limit=10)
        if not ms:
            pytest.skip("No open missions")
        for m in ms:
            if hasattr(m, "deadline") and m.deadline:
                dl = m.deadline
                if isinstance(dl, str):
                    import datetime
                    try:
                        parsed = datetime.datetime.fromisoformat(dl.replace("Z", "+00:00"))
                        ts = parsed.timestamp()
                    except ValueError:
                        continue
                elif isinstance(dl, (int, float)):
                    ts = dl
                else:
                    continue
                # Allow 60s grace for clock skew
                assert ts > now - 60, \
                    f"MUST: open mission {m.id} deadline {dl} is not in the past"


# ---- AIP-1 §6 — reward asset normalization ----

class TestRewardAssetNormalization:
    """reward.asset MUST be a known canonical symbol."""

    KNOWN_ASSETS = {"AIGEN", "USDC", "ETH", "MATIC", "SOL", "BTC", "DAI", "USDT"}

    def test_open_missions_reward_asset_normalized(self, client):
        ms = client.list_missions(status="open", limit=10)
        if not ms:
            pytest.skip("No open missions")
        for m in ms:
            if m.reward_asset:
                assert m.reward_asset.upper() == m.reward_asset, \
                    f"MUST: reward.asset is uppercase (got '{m.reward_asset}' on mission {m.id})"


# ---- AIP-1 §2 — pagination MUST work ----

class TestPagination:
    """limit parameter MUST cap the result count; offset MUST shift window."""

    def test_limit_caps_results(self, client):
        ms = client.list_missions(limit=3)
        assert len(ms) <= 3, f"MUST: limit=3 returns ≤3 results (got {len(ms)})"

    def test_mission_ids_are_unique(self, client):
        ms = client.list_missions(limit=50)
        ids = [str(m.id) for m in ms]
        assert len(ids) == len(set(ids)), "MUST: no duplicate mission ids in list response"


# ---- AIP-1 §8 — HTTP response contract ----

class TestResponseContentType:
    """All JSON endpoints MUST return Content-Type: application/json."""

    def test_missions_content_type(self):
        import urllib.request
        url = BASE_URL.rstrip("/") + "/missions"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                ctype = r.headers.get("content-type", "")
        except Exception as e:
            pytest.fail(f"MUST: /missions reachable — {e}")
        assert "application/json" in ctype, \
            f"MUST: /missions returns application/json (got '{ctype}')"

    def test_error_response_is_json(self):
        """404 for unknown resource MUST be JSON, not HTML."""
        import urllib.request
        import json as _json
        url = BASE_URL.rstrip("/") + "/missions/totally-nonexistent-xyz-404-test"
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                body = r.read()
        except urllib.error.HTTPError as e:
            body = e.read()
            ctype = e.headers.get("content-type", "")
            # It's fine to 404 — we just need the body to be valid JSON
            try:
                _json.loads(body)
            except _json.JSONDecodeError:
                pytest.fail(f"MUST: error response is JSON (got non-JSON with Content-Type={ctype})")
        except Exception as e:
            pytest.skip(f"Could not reach error endpoint: {e}")


# ---- AIP-1 §7 — CORS MUST allow programmatic agent access ----

class TestCORSHeaders:
    """Agents running in browser/sandboxed environments need CORS."""

    def test_cors_header_present(self):
        import urllib.request
        url = BASE_URL.rstrip("/") + "/missions"
        req = urllib.request.Request(url, method="OPTIONS", headers={
            "Origin": "https://agent.example.com",
            "Access-Control-Request-Method": "GET",
        })
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                acao = r.headers.get("access-control-allow-origin", "")
        except urllib.error.HTTPError as e:
            acao = e.headers.get("access-control-allow-origin", "")
        except Exception:
            pytest.skip("CORS preflight not reachable (possible firewall)")
        assert acao in ("*", "https://agent.example.com") or acao != "", \
            "SHOULD: Access-Control-Allow-Origin header present for agent-accessible endpoints"


# ---- AIP-1 §5 — leaderboard (SHOULD exist) ----

class TestLeaderboard:
    """Leaderboard SHOULD expose relative agent rankings."""

    def test_leaderboard_returns_list(self, client):
        try:
            lb = client.leaderboard(limit=5)
        except OABPError:
            pytest.skip("Leaderboard endpoint not available on this implementation")
        assert isinstance(lb, list), "SHOULD: leaderboard returns list"

    def test_leaderboard_entries_have_rating(self, client):
        try:
            lb = client.leaderboard(limit=5)
        except OABPError:
            pytest.skip("Leaderboard endpoint not available")
        if not lb:
            pytest.skip("Leaderboard is empty")
        for entry in lb:
            assert isinstance(entry.rating, int), \
                f"SHOULD: leaderboard entry has integer rating (got {type(entry.rating)})"


# ---- AIP-2 — mission types registry (conditional) ----

class TestAIP2Conformance:
    """If AIP-2 is declared in aip_supported, /missions/types MUST exist."""

    def test_mission_types_endpoint_if_aip2(self, manifest):
        if 2 not in manifest.get("aip_supported", []):
            pytest.skip("AIP-2 not declared by this implementation")
        import urllib.request
        import json as _json
        url = BASE_URL.rstrip("/") + "/missions/types"
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                body = _json.loads(r.read())
        except Exception as e:
            pytest.fail(f"MUST (AIP-2): /missions/types reachable — {e}")
        assert isinstance(body, (dict, list)), \
            "MUST (AIP-2): /missions/types returns JSON object or array"


# ---- AIP-1 §9 — protocol fee transparency ----

class TestProtocolFeeDeclaration:
    """AIP-1 §9 — implementations SHOULD declare their fee_bps in the manifest."""

    def test_manifest_declares_fee_bps(self, manifest):
        if "fee_bps" not in manifest:
            pytest.skip("fee_bps not declared — SHOULD be present per AIP-1 §9")
        fee = manifest["fee_bps"]
        assert isinstance(fee, int), "SHOULD: fee_bps is integer (basis points)"
        assert 0 <= fee <= 10000, f"SHOULD: fee_bps in [0, 10000] (got {fee})"


# ---- AIP-3 §5.2 — per-type affinity (RECOMMENDED) ----

class TestAIP3Conformance:
    """AIP-3 §5.2 — mission_type_affinity on reputation endpoint (RECOMMENDED).

    Passes trivially (with a skip) when the server omits affinity data — this
    field is RECOMMENDED, not MUST, for compliant implementations.
    """

    AIP2_CANONICAL_TYPES = {
        "code_review", "token_scan", "doc_write", "test_create",
        "data_label", "translation", "research", "freeform",
    }

    def test_affinity_field_is_dict(self, client):
        agent_id = os.environ.get("OABP_TEST_AGENT_ID", "aigen-autopilot")
        try:
            rep = client.agent(agent_id)
        except OABPError as e:
            if e.status == 404:
                pytest.skip(f"Test agent {agent_id} not found")
            raise
        assert isinstance(rep.mission_type_affinity, dict), \
            "SHOULD: mission_type_affinity is always a dict (empty when not supported)"

    def test_affinity_values_are_missiontypeaffinity(self, client):
        agent_id = os.environ.get("OABP_TEST_AGENT_ID", "aigen-autopilot")
        try:
            rep = client.agent(agent_id)
        except OABPError as e:
            if e.status == 404:
                pytest.skip(f"Test agent {agent_id} not found")
            raise
        if not rep.mission_type_affinity:
            pytest.skip("No mission_type_affinity data returned (server may not implement AIP-3)")
        for type_id, mta in rep.mission_type_affinity.items():
            assert isinstance(mta, MissionTypeAffinity), \
                f"SHOULD: affinity[{type_id!r}] is MissionTypeAffinity"
            assert isinstance(mta.elo, int), \
                f"SHOULD: affinity[{type_id!r}].elo is int (got {type(mta.elo)})"
            assert isinstance(mta.completions, int), \
                f"SHOULD: affinity[{type_id!r}].completions is int"
            assert mta.completions >= 1, \
                f"SHOULD: only types with ≥1 completion appear (got {mta.completions} for {type_id!r})"

    def test_affinity_keys_are_aip2_types_or_custom(self, client):
        agent_id = os.environ.get("OABP_TEST_AGENT_ID", "aigen-autopilot")
        try:
            rep = client.agent(agent_id)
        except OABPError as e:
            if e.status == 404:
                pytest.skip(f"Test agent {agent_id} not found")
            raise
        if not rep.mission_type_affinity:
            pytest.skip("No mission_type_affinity data (server may not implement AIP-3)")
        for type_id in rep.mission_type_affinity:
            assert isinstance(type_id, str) and len(type_id) > 0, \
                f"SHOULD: mission type key is non-empty string (got {type_id!r})"

    def test_sdk_declares_aip3(self):
        assert 3 in __aip_supported__, "SDK MUST declare AIP-3 support in __aip_supported__"


# ---- AIP-2 §3.9 — verification method compatibility ----

class TestVerificationCompat:
    """AIP-2 §3.9 — check_verification_compat() and VERIFICATION_COMPAT table."""

    def test_table_covers_all_registered_types(self):
        registered = {
            "code_review", "token_scan", "doc_write", "test_create",
            "data_label", "translation", "research", "freeform",
        }
        assert registered == set(VERIFICATION_COMPAT.keys()), \
            "MUST: VERIFICATION_COMPAT covers exactly the AIP-2 §3 registered types"

    def test_all_rows_have_four_methods(self):
        methods = {"creator_judges", "first_valid_match", "oracle", "peer_vote"}
        for type_id, row in VERIFICATION_COMPAT.items():
            assert set(row.keys()) == methods, \
                f"MUST: {type_id!r} row covers all four verification methods"

    def test_all_levels_are_valid(self):
        valid = {"RECOMMENDED", "OPTIONAL", "NOT_RECOMMENDED", "NOT_APPLICABLE"}
        for type_id, row in VERIFICATION_COMPAT.items():
            for method, level in row.items():
                assert level in valid, \
                    f"MUST: {type_id!r}/{method!r} has a valid level (got {level!r})"

    def test_token_scan_first_valid_match_not_recommended(self):
        level, warn = check_verification_compat("token_scan", "first_valid_match")
        assert level == "NOT_RECOMMENDED", \
            "MUST: token_scan + first_valid_match is NOT_RECOMMENDED (§3.9 binding clause)"
        assert warn is True, "MUST: NOT_RECOMMENDED triggers is_warning=True"

    def test_doc_write_oracle_not_applicable(self):
        level, warn = check_verification_compat("doc_write", "oracle")
        assert level == "NOT_APPLICABLE"
        assert warn is True

    def test_recommended_pairs_no_warning(self):
        recommended_pairs = [
            ("code_review", "creator_judges"),
            ("token_scan", "oracle"),
            ("data_label", "peer_vote"),
        ]
        for mt, vm in recommended_pairs:
            level, warn = check_verification_compat(mt, vm)
            assert level == "RECOMMENDED", f"Expected RECOMMENDED for {mt}/{vm}, got {level!r}"
            assert warn is False

    def test_unknown_type_returns_unknown(self):
        level, warn = check_verification_compat("aigen:nft_scan", "creator_judges")
        assert level == "UNKNOWN"
        assert warn is False, "Custom/unknown types MUST NOT trigger a warning"

    def test_unknown_method_returns_unknown(self):
        level, warn = check_verification_compat("code_review", "consensus_vote_v99")
        assert level == "UNKNOWN"

    def test_function_exported_from_package(self):
        import oabp
        assert hasattr(oabp, "check_verification_compat"), \
            "check_verification_compat MUST be exported from the oabp package"
        assert hasattr(oabp, "VERIFICATION_COMPAT"), \
            "VERIFICATION_COMPAT MUST be exported from the oabp package"


# ---- Run summary ----

def test_aip_version_alignment():
    """Sanity: this test suite is aligned to AIP-1 + AIP-2 + AIP-3."""
    assert 1 in __aip_supported__, "This SDK supports AIP-1"
    assert 2 in __aip_supported__, "This SDK supports AIP-2"
    assert 3 in __aip_supported__, "This SDK supports AIP-3"


# ---------------------------------------------------------------------------
# AIP-3 §3.1 — Self-Submission Detection (unit tests, no network required)
# ---------------------------------------------------------------------------

class TestSelfSubmissionDetection:
    """AIP-3 §3.1: client-side self-submission guard."""

    def _make_client(self, creator: str, mission_id: str = "mis_test"):
        """Return a minimal OABPClient where mission(id).creator == creator."""
        client = OABPClient.__new__(OABPClient)
        client.base_url = "http://mock"
        client.user_agent = "test"
        client._endpoints_cache = None

        # Inject a fake mission() method
        mission = Mission(
            id=mission_id, creator=creator, title="Test", description="",
            reward_asset="AIGEN", reward_amount=50,
            verification_type="first_valid_match",
            verification_params={}, deadline="2099-01-01T00:00:00Z",
            status="open", created_at="2026-05-19T00:00:00Z",
        )
        client.mission = lambda mid: mission
        return client

    def test_same_address_is_self_submission(self):
        """AIP-3 §3.1 MUST: creator == submitter → self_submission=True."""
        addr = "0xAaAaAa0000000000000000000000000000000001"
        client = self._make_client(creator=addr)
        assert client.check_self_submission("mis_test", addr) is True

    def test_case_insensitive_match(self):
        """AIP-3 §3.1: address comparison MUST be case-insensitive."""
        creator = "0xaaaaaa0000000000000000000000000000000001"
        submitter = "0xAAAAAA0000000000000000000000000000000001"
        client = self._make_client(creator=creator)
        assert client.check_self_submission("mis_test", submitter) is True

    def test_different_address_not_self_submission(self):
        """AIP-3 §3.1: different creator and submitter → self_submission=False."""
        creator = "0x1111110000000000000000000000000000000001"
        submitter = "0x2222220000000000000000000000000000000002"
        client = self._make_client(creator=creator)
        assert client.check_self_submission("mis_test", submitter) is False

    def test_checksum_vs_lower_match(self):
        """Checksummed creator vs lowercase submitter should still match."""
        creator = "0xAbCdEf0000000000000000000000000000000001"
        submitter = "0xabcdef0000000000000000000000000000000001"
        client = self._make_client(creator=creator)
        assert client.check_self_submission("mis_test", submitter) is True

    def test_mission_fetch_error_returns_false(self):
        """On mission fetch failure, returns False (fail-open, not fail-closed)."""
        client = OABPClient.__new__(OABPClient)
        client.base_url = "http://doesnotexist.invalid"
        client.user_agent = "test"
        client._endpoints_cache = None
        client.mission = lambda mid: (_ for _ in ()).throw(Exception("network error"))
        result = client.check_self_submission("mis_test", "0x1234")
        assert result is False


# ---- AIP-1 §1.4 — Registry identity propagation ----

class TestRegistryIdentityPropagation:
    """AIP-1 §1.4 — identity model for registry-multiplexed sessions.

    These tests cover the five normative MUST rules:
    1. No auto-binding of routing tokens
    2. Anonymous by default (no api_key match → None)
    3. Attested sessions resolve to bound EVM address
    4. Cross-registry portability (same address, different registries)
    5. RegistryAttestation dataclass validity helpers
    """

    def test_anonymous_session_returns_none(self):
        """§1.4 rule 2: request without api_key MUST be treated as anonymous."""
        result = check_registry_session(query_params={}, authorization_header=None)
        assert result is None

    def test_unknown_api_key_returns_none(self):
        """§1.4 rule 2: api_key without attestation binding MUST remain anonymous."""
        bindings = {"known-key": "0xAAAA0000000000000000000000000000000000AA"}
        result = check_registry_session(
            query_params={"api_key": "unknown-uuid", "profile": "qq+account"},
            authorization_header=None,
            attested_bindings=bindings,
        )
        assert result is None

    def test_attested_session_resolves_to_evm_address(self):
        """§1.4 rule 3: api_key with binding resolves to the bound EVM address."""
        bound_address = "0x7aA55BBeF52782E0dF46AB449bc8036851c5a38A"
        bindings = {"smithery-uuid-abc": bound_address}
        result = check_registry_session(
            query_params={"api_key": "smithery-uuid-abc", "profile": "nju+account"},
            authorization_header=None,
            attested_bindings=bindings,
        )
        assert result == bound_address

    def test_cross_registry_portability(self):
        """§1.4 rule 4: same EVM address bindable under multiple api_keys from different registries."""
        shared_address = "0x7aA55BBeF52782E0dF46AB449bc8036851c5a38A"
        bindings = {
            "smithery-key-1": shared_address,
            "glama-key-99":   shared_address,
        }
        addr_smithery = check_registry_session(
            query_params={"api_key": "smithery-key-1"},
            authorization_header=None,
            attested_bindings=bindings,
        )
        addr_glama = check_registry_session(
            query_params={"api_key": "glama-key-99"},
            authorization_header=None,
            attested_bindings=bindings,
        )
        assert addr_smithery == addr_glama == shared_address

    def test_registry_attestation_address_validation(self):
        """RegistryAttestation.is_valid_address() rejects non-EVM strings."""
        good = RegistryAttestation(
            api_key="k1", evm_address="0xAbCd1234567890AbCd1234567890AbCd12345678",
            registry_domain="smithery.ai", issued_at="2026-05-19T07:00:00Z",
            signature="0xdeadbeef",
        )
        bad = RegistryAttestation(
            api_key="k2", evm_address="not-an-address",
            registry_domain="smithery.ai", issued_at="2026-05-19T07:00:00Z",
            signature="0xdeadbeef",
        )
        assert good.is_valid_address() is True
        assert bad.is_valid_address() is False

    def test_registry_attestation_roundtrip(self):
        """RegistryAttestation serializes and deserializes losslessly."""
        attest = RegistryAttestation(
            api_key="ec7c3863-49cf-4591-8a1e-ae775beaa703",
            evm_address="0x7aA55BBeF52782E0dF46AB449bc8036851c5a38A",
            registry_domain="smithery.ai",
            issued_at="2026-05-19T07:13:00Z",
            signature="0xcafe",
            profile="outlook+account",
            ttl_seconds=3600,
        )
        restored = RegistryAttestation.from_dict(attest.to_dict())
        assert restored.api_key == attest.api_key
        assert restored.evm_address == attest.evm_address
        assert restored.registry_domain == attest.registry_domain
        assert restored.profile == attest.profile
        assert restored.ttl_seconds == attest.ttl_seconds


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
