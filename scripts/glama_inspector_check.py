#!/usr/bin/env python3
"""Glama/MCP compatibility checks for the AIGEN server.

Default mode is offline and CI-friendly: validate registry metadata, documented
remotes, and advertised tools against the source. Use --remote to also perform
a minimal Streamable HTTP JSON-RPC handshake against the live endpoint.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_TOOLS = {
    "shield",
    "test_honeypot",
    "check_token_safety",
    "explore",
    "agent_register",
    "task_board",
}
REQUIRED_REMOTE_TYPES = {"streamable-http", "sse"}


class CheckFailure(AssertionError):
    """Raised when a compatibility check fails."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise CheckFailure(f"{path.name} is not valid JSON: {exc}") from exc


def tool_names_from_source(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            func = decorator.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "tool"
                and isinstance(func.value, ast.Name)
                and func.value.id == "mcp"
            ):
                names.add(node.name)
    return names


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CheckFailure(message)


def require_https_url(url: str, label: str) -> None:
    parsed = urllib.parse.urlparse(url)
    require(parsed.scheme == "https", f"{label} must use https: {url}")
    require(bool(parsed.netloc), f"{label} is missing a host: {url}")


def check_static() -> list[str]:
    server = load_json(ROOT / "server.json")
    glama = load_json(ROOT / "glama.json")
    readme = (ROOT / "README.md").read_text()
    mcp_source = (ROOT / "mcp_server.py").read_text()
    source_tools = tool_names_from_source(ROOT / "mcp_server.py")
    glama_tools = {item.get("name") for item in glama.get("tools", []) if isinstance(item, dict)}

    require(server.get("name") == "org.duckdns.cryptogenesis/safe-agent", "server.json name changed")
    require(server.get("repository", {}).get("source") == "github", "server.json repository.source must be github")

    remotes = server.get("remotes", [])
    require(isinstance(remotes, list) and remotes, "server.json remotes must be a non-empty list")
    remote_by_type = {remote.get("type"): remote.get("url") for remote in remotes if isinstance(remote, dict)}
    require(REQUIRED_REMOTE_TYPES <= set(remote_by_type), "server.json must expose streamable-http and sse remotes")
    for remote_type, url in remote_by_type.items():
        require_https_url(str(url), f"server.json {remote_type} remote")

    transport = glama.get("transport", {})
    require_https_url(str(transport.get("streamable_http", "")), "glama streamable_http")
    require_https_url(str(transport.get("sse", "")), "glama sse")
    require(
        transport.get("streamable_http") == remote_by_type["streamable-http"],
        "glama streamable_http must match server.json streamable-http remote",
    )
    require(transport.get("sse") == remote_by_type["sse"], "glama sse must match server.json sse remote")

    missing_required = REQUIRED_TOOLS - source_tools
    require(not missing_required, f"mcp_server.py missing required tools: {sorted(missing_required)}")
    missing_from_glama = source_tools - glama_tools
    stale_in_glama = glama_tools - source_tools
    require(not missing_from_glama, f"glama.json missing tools from source: {sorted(missing_from_glama)}")
    require(not stale_in_glama, f"glama.json advertises missing source tools: {sorted(stale_in_glama)}")

    require('streamable_http_path="/mcp"' in mcp_source, 'mcp_server.py must set streamable_http_path="/mcp"')
    require(remote_by_type["streamable-http"] in readme, "README must document the streamable-http endpoint")
    require(remote_by_type["sse"] in (ROOT / "API.md").read_text(), "API.md must document the SSE endpoint")

    return [
        f"server remotes: {', '.join(sorted(remote_by_type))}",
        f"source tools: {len(source_tools)}",
        "glama metadata matches mcp_server.py",
    ]


def parse_mcp_response(content_type: str, body: str) -> dict[str, Any]:
    if "text/event-stream" not in content_type:
        return json.loads(body)
    data_lines = []
    for line in body.splitlines():
        if line.startswith("data:"):
            data_lines.append(line.removeprefix("data:").strip())
    if not data_lines:
        raise CheckFailure("MCP SSE response did not contain data lines")
    return json.loads("\n".join(data_lines))


def mcp_post(url: str, payload: dict[str, Any], session_id: str | None = None) -> tuple[dict[str, Any], str | None]:
    data = json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "User-Agent": "aigen-glama-inspector-check/1.0",
    }
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
            parsed = parse_mcp_response(response.headers.get("Content-Type", ""), body)
            return parsed, response.headers.get("Mcp-Session-Id") or session_id
    except urllib.error.URLError as exc:
        raise CheckFailure(f"remote MCP request failed: {exc}") from exc


def check_remote(url: str) -> list[str]:
    initialize, session_id = mcp_post(
        url,
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "aigen-glama-inspector-check", "version": "1.0.0"},
            },
        },
    )
    require("result" in initialize, f"initialize failed: {initialize}")
    mcp_post(url, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}, session_id)
    tools, _ = mcp_post(url, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, session_id)
    result_tools = tools.get("result", {}).get("tools", [])
    require(isinstance(result_tools, list) and result_tools, "tools/list returned no tools")
    names = {tool.get("name") for tool in result_tools if isinstance(tool, dict)}
    missing = REQUIRED_TOOLS - names
    require(not missing, f"remote tools/list missing required tools: {sorted(missing)}")
    return [f"remote tools/list: {len(result_tools)} tools"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Glama/MCP compatibility")
    parser.add_argument("--remote", action="store_true", help="also inspect the live Streamable HTTP endpoint")
    args = parser.parse_args()

    try:
        results = check_static()
        if args.remote:
            endpoint = load_json(ROOT / "glama.json")["transport"]["streamable_http"]
            results.extend(check_remote(endpoint))
    except CheckFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print("Glama inspector checks passed")
    for result in results:
        print(f"- {result}")
    if not args.remote:
        print("- remote MCP handshake skipped; run with --remote to inspect the live endpoint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
