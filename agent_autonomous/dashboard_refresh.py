#!/usr/bin/env python3
"""AIGEN autopilot dashboard refresh — PARALLEL version (2026-06-01).

Same output schema as the prior inline block, but all ~10 independent network
fetches run concurrently (ThreadPoolExecutor; I/O-bound -> GIL released), HN item
details fetched in parallel, IMAP headers fetched in a single batch round-trip.
Wall-clock drops from sum(all) to max(slowest)."""
import json
import os
import subprocess
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

out = {
    "_note": "Refreshed by dashboard_refresh.py (parallel)",
    "last_refresh_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
}


def _get(url, timeout=5, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def t_missions():
    try:
        return {"missions": _get("http://127.0.0.1:4444/missions/stats", 5)}
    except Exception as e:
        return {"missions_error": str(e)}


def t_treasury():
    try:
        body = json.dumps({"jsonrpc": "2.0", "method": "eth_call", "params": [
            {"to": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
             "data": "0x70a08231000000000000000000000000Da429f2034b62b8722713873dE3C045eec390d8F"},
            "latest"], "id": 1}).encode()
        d = _get("https://mainnet.base.org", 5, data=body,
                 headers={"Content-Type": "application/json", "User-Agent": "agent/1.0"})
        return {"treasury_usdc": int(d.get("result", "0x0"), 16) / 1e6}
    except Exception as e:
        return {"treasury_error": str(e)}


def t_nginx():
    try:
        res = subprocess.run(["sudo", "tail", "-100", "/var/log/nginx/access.log"],
                             capture_output=True, text=True, timeout=5)
        paths = {}
        ips = set()
        for line in res.stdout.split("\n"):
            parts = line.split()
            if len(parts) > 6:
                paths[parts[6]] = paths.get(parts[6], 0) + 1
                ips.add(parts[0])
        return {"recent_top_paths": sorted(paths.items(), key=lambda x: -x[1])[:8],
                "recent_unique_ips": len(ips), "hustlerops_recent": "89.213.118.44" in ips}
    except Exception as e:
        return {"nginx_error": str(e)}


def t_git():
    try:
        return {"recent_commits": subprocess.run(
            ["git", "-C", "/home/luna/crypto-genesis/aigen", "log", "--oneline", "-5"],
            capture_output=True, text=True, timeout=5).stdout.strip().split("\n")}
    except Exception as e:
        return {"git_error": str(e)}


def t_ghnotif():
    try:
        res = subprocess.run(
            ["gh", "api", "notifications", "--jq",
             "[.[] | {repo: .repository.full_name, type: .subject.type, title: .subject.title, "
             "url: .subject.url, reason: .reason, updated_at: .updated_at, unread: .unread}]"],
            capture_output=True, text=True, timeout=10)
        n = json.loads(res.stdout) if res.stdout.strip() else []
        return {"github_notifications": n, "github_notifications_count": len(n)}
    except Exception as e:
        return {"github_notifications_error": str(e)}


def t_triggers():
    try:
        if os.path.exists("state/triggers.log"):
            with open("state/triggers.log") as f:
                lines = f.readlines()
            return {"recent_webhook_triggers": [l.strip() for l in lines[-5:]]}
    except Exception:
        pass
    return {}


def t_repostats():
    try:
        res = subprocess.run(
            ["gh", "api", "repos/Aigen-Protocol/aigen-protocol", "--jq",
             "{stars: .stargazers_count, forks: .forks_count, open_issues: .open_issues_count, "
             "watchers: .subscribers_count}"],
            capture_output=True, text=True, timeout=8)
        if res.returncode == 0:
            return {"_fresh_repo_stats": json.loads(res.stdout)}
    except Exception as e:
        return {"_fresh_repo_stats_err": str(e)[:120]}
    return {}


def t_awesomemcp():
    try:
        res = subprocess.run(
            ["gh", "api", "repos/punkpeye/awesome-mcp-servers/commits", "--jq",
             "[.[0:5] | .[] | {sha: .sha[0:8], msg: .commit.message[0:80], when: .commit.author.date}]"],
            capture_output=True, text=True, timeout=8)
        if res.returncode == 0:
            return {"_fresh_awesome_mcp_recent": json.loads(res.stdout)}
    except Exception as e:
        return {"_fresh_awesome_mcp_err": str(e)[:120]}
    return {}


def t_hn():
    try:
        top_ids = _get("https://hacker-news.firebaseio.com/v0/topstories.json", 6)[:30]

        def fetch_item(sid):
            try:
                return _get("https://hacker-news.firebaseio.com/v0/item/%s.json" % sid, 4)
            except Exception:
                return None

        kw = ["agent", "mcp", "anthropic", "bounty", "claude", "open ai", "openai", "model context"]
        hits = []
        with ThreadPoolExecutor(max_workers=10) as ex:
            for st in ex.map(fetch_item, top_ids):   # preserves order
                if not st:
                    continue
                title = (st.get("title", "") or "").lower()
                if any(k in title for k in kw):
                    hits.append({"id": st.get("id"), "title": st.get("title"), "score": st.get("score"),
                                 "url": st.get("url"), "comments": st.get("descendants", 0)})
                    if len(hits) >= 5:
                        break
        return {"_fresh_hn_relevant": hits}
    except Exception as e:
        return {"_fresh_hn_err": str(e)[:120]}


def t_imap():
    try:
        import imaplib
        import email as email_mod
        from email.header import decode_header
        creds = open("/home/luna/crypto-genesis/credentials/zoho_mail.txt").read()
        pw = creds.split("Password:")[1].split("\n")[0].strip()
        M = imaplib.IMAP4_SSL("imap.zoho.eu", 993)
        M.login("Cryptogen@zohomail.eu", pw)
        M.select("INBOX")
        typ, data = M.search(None, '(SINCE "01-May-2026")')
        ids = data[0].split()[-15:]
        inbox = []
        if ids:
            # single batch round-trip instead of 15 sequential fetches
            typ, msg_data = M.fetch(",".join(x.decode() for x in ids), '(BODY.PEEK[HEADER])')
            for part in msg_data:
                if not isinstance(part, tuple):
                    continue
                try:
                    seq = part[0].split()[0].decode()
                except Exception:
                    seq = ""
                msg = email_mod.message_from_bytes(part[1])
                subject = msg.get("Subject", "")
                try:
                    subject = "".join(s.decode(c or "utf-8") if isinstance(s, bytes) else s
                                      for s, c in decode_header(subject))
                except Exception:
                    pass
                inbox.append({"from": msg.get("From", ""), "subject": subject[:140],
                              "date": msg.get("Date", ""), "uid": seq})
        M.close()
        M.logout()
        return {"inbox_recent": inbox[-15:], "inbox_count": len(ids)}
    except Exception as e:
        return {"inbox_error": str(e)[:200]}


TASKS = [t_missions, t_treasury, t_nginx, t_git, t_ghnotif, t_triggers,
         t_repostats, t_awesomemcp, t_hn, t_imap]

fresh = {}
with ThreadPoolExecutor(max_workers=len(TASKS)) as ex:
    for res in ex.map(lambda f: f(), TASKS):
        for k, v in res.items():
            if k.startswith("_fresh_"):
                fresh[k[len("_fresh_"):]] = v
            else:
                out[k] = v
out["fresh_context"] = fresh
print(json.dumps(out, indent=2))
