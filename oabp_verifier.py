#!/usr/bin/env python3
"""OABP oracle verifier — validates a submission's deliverable for real.

v1: GitHub-repo missions, validated via the GitHub REST API WITHOUT executing
any submitted code (no RCE). Rejects hallucinated text, fake PR/issue links,
non-existent repos, the protocol's own repo, wrong-language or empty repos.

Returns {"passed": True|False|None, "reason": str, ...}. `None` = indeterminate
(e.g. GitHub rate-limited, or no automated verifier for this category) → caller
must NOT auto-pay on None (leave for peer/manual or retry).
"""
import json
import re
import urllib.error
import urllib.request

GH_API = "https://api.github.com"
_URL_RE = re.compile(r"https?://github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git|/|\s|$)", re.I)
_PR_RE = re.compile(r"https?://github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)/pull/(\d+)", re.I)

# A merged PR into this repo counts as proof — the maintainer review IS the gate.
CANONICAL_ORG = "aigen-protocol"
CANONICAL_REPO = "aigen-protocol"
_LANG_HINTS = {
    "golang": "Go", " go ": "Go", "go client": "Go", "go 1.": "Go",
    "java": "Java", "jvm": "Java", "php": "PHP", "composer": "PHP",
    "ruby": "Ruby", "rubygem": "Ruby", "powershell": "PowerShell",
    "python": "Python", "smolagents": "Python", "langgraph": "Python",
    "rust": "Rust", "typescript": "TypeScript", "elizaos": "TypeScript",
    "mastra": "TypeScript", "node": "JavaScript", "javascript": "JavaScript",
}


def _gh(path):
    req = urllib.request.Request(
        GH_API + path,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "aigen-oracle/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.getcode(), json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return 0, None


def required_language(mission):
    vp = mission.get("verification_params", {}) or {}
    if vp.get("language"):
        return vp["language"]
    text = (" " + (mission.get("title", "") + " " + mission.get("description", "")).lower() + " ")
    for hint, lang in _LANG_HINTS.items():
        if hint in text:
            return lang
    return None


def verify_merged_canonical_pr(proof):
    """A merged PR into the canonical AIGEN repo is valid contribution proof.
    Returns dict if proof IS a PR URL into canonical repo (regardless of status);
    returns None if proof is not such a URL — caller falls through to repo verify."""
    pm = _PR_RE.search(proof or "")
    if not pm:
        return None
    owner, repo, num = pm.group(1), pm.group(2), pm.group(3)
    if owner.lower() != CANONICAL_ORG or repo.lower() != CANONICAL_REPO:
        return None
    code, data = _gh(f"/repos/{owner}/{repo}/pulls/{num}")
    ref = f"{owner}/{repo}#{num}"
    if code == 403:
        return {"passed": None, "reason": "GitHub API rate-limited — retry later", "url": ref}
    if code != 200 or not data:
        return {"passed": False, "reason": f"PR #{num} not found in {owner}/{repo} (http {code})", "url": ref}
    if not data.get("merged"):
        return {"passed": False, "reason": f"PR #{num} not merged (state: {data.get('state', 'unknown')})", "url": ref}
    return {"passed": True, "reason": f"PR #{num} merged into {owner}/{repo}", "url": ref,
            "merge_commit_sha": data.get("merge_commit_sha")}


def verify_github_repo(proof, req_lang=None):
    pr_result = verify_merged_canonical_pr(proof)
    if pr_result is not None:
        return pr_result
    m = _URL_RE.search(proof or "")
    if not m:
        return {"passed": False, "reason": "no GitHub repo URL found in proof"}
    owner, repo = m.group(1), m.group(2)
    matched = m.group(0)
    if "/pull/" in (proof or "") or "/issues/" in (proof or ""):
        return {"passed": False, "reason": "link is a PR/issue (not into canonical repo), not a repository", "url": matched}
    if owner.lower() == "aigen-protocol":
        return {"passed": False, "reason": "submitted the protocol's own repo — not a deliverable", "url": matched}

    code, data = _gh(f"/repos/{owner}/{repo}")
    if code == 403:
        return {"passed": None, "reason": "GitHub API rate-limited — retry later", "url": matched}
    if code != 200 or not data:
        return {"passed": False, "reason": f"repo does not exist ({owner}/{repo}, http {code})", "url": matched}

    non_empty = (data.get("size", 0) or 0) > 0
    _, langs = _gh(f"/repos/{owner}/{repo}/languages")
    detected = list((langs or {}).keys())
    lang_ok = True
    if req_lang and langs is not None:
        lang_ok = any(req_lang.lower() == l.lower() for l in detected)
    rc, _ = _gh(f"/repos/{owner}/{repo}/readme")
    readme = rc == 200

    passed = bool(non_empty and lang_ok)
    if not non_empty:
        reason = "repo is empty (no code)"
    elif not lang_ok:
        reason = f"required language {req_lang} not present (repo has: {detected or 'none'})"
    else:
        reason = "valid repo: exists, non-empty, language ok" + ("" if readme else " (no README)")
    return {"passed": passed, "reason": reason, "url": f"{owner}/{repo}",
            "languages": detected, "readme": readme, "non_empty": non_empty}


# ---------------------------------------------------------------------------
# GoPlus safety-review oracle (added 2026-06-01, rebuilt after 05-31 revert).
# Verifies a token safety review against real on-chain GoPlus data WITHOUT
# executing anything. passed=True (review matches chain) / False (review lies)
# / None (indeterminate -> never auto-reject). Solana + EVM.
# ---------------------------------------------------------------------------
_GOPLUS = "https://api.gopluslabs.io/api/v1"
_EVM_RE = re.compile(r"0x[a-fA-F0-9]{40}")
_SOL_RE = re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b")
_EVM_CHAINS = {"base": "8453", "bsc": "56", "binance": "56", "polygon": "137",
               "arbitrum": "42161", "optimism": "10", "avalanche": "43114", "ethereum": "1"}


def _goplus_json(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": "aigen-oracle/1.0",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _extract_token(text):
    text = text or ""
    m = _EVM_RE.search(text)
    if m:
        return ("evm", m.group(0))
    m = _SOL_RE.search(text)
    if m:
        return ("solana", m.group(0))
    return (None, None)


def _evm_chain_id(text):
    t = (text or "").lower()
    for name, cid in _EVM_CHAINS.items():
        if name in t:
            return cid
    return "1"


def _goplus_reality(chain, addr, mission_text):
    if chain == "solana":
        d = _goplus_json(_GOPLUS + "/solana/token_security?contract_addresses=" + addr)
        res = (d.get("result") or {}).get(addr) or {}
        if not res:
            return None
        return {
            "mintable": str((res.get("mintable") or {}).get("status", "")) == "1",
            "freezable": str((res.get("freezable") or {}).get("status", "")) == "1",
            "honeypot": None,
        }
    cid = _evm_chain_id(mission_text)
    a = addr.lower()
    d = _goplus_json(_GOPLUS + "/token_security/" + cid + "?contract_addresses=" + a)
    res = (d.get("result") or {}).get(a) or {}
    if not res:
        return None
    return {
        "mintable": str(res.get("is_mintable", "")) == "1",
        "freezable": str(res.get("transfer_pausable", "")) == "1",
        "honeypot": str(res.get("is_honeypot", "")) == "1",
    }


def _claim(p, pos, neg):
    has_pos = any(k in p for k in pos)
    has_neg = any(k in p for k in neg)
    if has_pos and not has_neg:
        return True
    if has_neg and not has_pos:
        return False
    return None


_MINT_POS = ["is mintable", "mintable: yes", "mintable=yes", "can be minted", "can mint more",
             "mint authority is active", "mint authority active", "active mint authority",
             "unlimited supply", "owner can mint", "supply can increase"]
_MINT_NEG = ["mint authority revoked", "no active authority", "no mint authority", "not mintable",
             "mintable: no", "mintable=no", "mint disabled", "renounced", "fixed supply",
             "supply is fixed", "authority revoked"]
_FREEZE_POS = ["freeze authority is active", "freeze authority active", "freezable: yes",
               "can freeze", "can be frozen", "active freeze authority", "transfers can be paused"]
_FREEZE_NEG = ["freeze authority revoked", "not freezable", "freezable: no", "no freeze authority",
               "cannot freeze", "cannot be frozen"]
_HP_POS = ["honeypot: yes", "is a honeypot", "is honeypot", "cannot sell", "can't sell", "unable to sell"]
_HP_NEG = ["not a honeypot", "honeypot: no", "no honeypot", "can sell", "sellable"]


def verify_safety_review(mission, submission):
    """Validate a token safety review vs GoPlus on-chain reality."""
    proof = (submission.get("proof", "") or "")
    desc = mission.get("description", "") or ""
    chain, addr = _extract_token(desc)
    if not addr:
        chain, addr = _extract_token(proof)
    if not addr:
        return {"passed": None, "reason": "no token address found to verify against"}
    try:
        reality = _goplus_reality(chain, addr, desc + " " + mission.get("title", ""))
    except Exception as e:
        return {"passed": None, "reason": "GoPlus unavailable: " + str(e)[:80]}
    if not reality:
        return {"passed": None, "reason": "GoPlus has no data for " + addr[:10]}
    p = proof.lower()
    claims = {
        "mintable": _claim(p, _MINT_POS, _MINT_NEG),
        "freezable": _claim(p, _FREEZE_POS, _FREEZE_NEG),
        "honeypot": _claim(p, _HP_POS, _HP_NEG),
    }
    contradictions, matches = [], []
    for dim, claimed in claims.items():
        real = reality.get(dim)
        if claimed is None or real is None:
            continue
        (matches if claimed == real else contradictions).append((dim, claimed, real))
    short = addr[:8] + "…"
    if contradictions:
        dim, c, r = contradictions[0]
        return {"passed": False, "goplus": reality,
                "reason": "review LIES on " + dim + ": claims " + str(c) + " but GoPlus on-chain is " + str(r) + " (" + short + ")"}
    if matches:
        return {"passed": True, "goplus": reality,
                "reason": "review matches GoPlus on " + ",".join(m[0] for m in matches) + " (" + short + ")"}
    return {"passed": None, "goplus": reality, "reason": "no checkable on-chain claim in review (" + short + ")"}


def _is_safety_mission(mission):
    vp = mission.get("verification_params", {}) or {}
    blob = (vp.get("regex", "") + " " + vp.get("oracle_description", "") + " "
            + mission.get("title", "") + " " + mission.get("description", "")).lower()
    return any(k in blob for k in ["safety review", "safety", "honeypot", "rug", "token security",
                                   "mintable", "freeze authority", "mint authority", "verdict:"])


def _is_repo_mission(mission):
    vp = mission.get("verification_params", {}) or {}
    blob = (vp.get("regex", "") + " " + vp.get("oracle_description", "") + " " + mission.get("description", "")).lower()
    return "github" in blob or "repo" in blob


def verify_submission(mission, submission):
    """Main entry. Returns {passed: True|False|None, reason, ...}."""
    proof = submission.get("proof", "") or ""
    if _is_repo_mission(mission):
        return verify_github_repo(proof, required_language(mission))
    if _is_safety_mission(mission):
        return verify_safety_review(mission, submission)
    return {"passed": None, "reason": "no automated verifier for this mission category yet"}
