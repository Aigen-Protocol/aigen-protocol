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


def _is_repo_mission(mission):
    vp = mission.get("verification_params", {}) or {}
    blob = (vp.get("regex", "") + " " + vp.get("oracle_description", "") + " " + mission.get("description", "")).lower()
    return "github" in blob or "repo" in blob


def verify_submission(mission, submission):
    """Main entry. Returns {passed: True|False|None, reason, ...}."""
    proof = submission.get("proof", "") or ""
    if _is_repo_mission(mission):
        return verify_github_repo(proof, required_language(mission))
    return {"passed": None, "reason": "no automated verifier for this mission category yet"}
