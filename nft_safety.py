"""NFT collection safety analysis for AIGEN MCP.

The checker combines explorer verification and ERC interface probes. It keeps
network calls optional and dependency-free so agents can run it in constrained
environments while still getting structured risk output.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
ERC721_INTERFACE = "0x80ac58cd"
ERC1155_INTERFACE = "0xd9b67a26"
ERC2981_INTERFACE = "0x2a55205a"
SUPPORTED_CHAINS = {
    "base": {
        "explorer": "https://base.blockscout.com",
        "rpc": "https://mainnet.base.org",
    },
    "optimism": {
        "explorer": "https://optimism.blockscout.com",
        "rpc": "https://mainnet.optimism.io",
    },
    "ethereum": {
        "explorer": "https://eth.blockscout.com",
        "rpc": "https://eth.llamarpc.com",
    },
}


class NFTSafetyError(RuntimeError):
    """Raised for expected NFT safety validation failures."""


@dataclass
class Signal:
    name: str
    ok: bool
    weight: int
    detail: str


def http_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None, timeout: int = 15) -> dict[str, Any]:
    data = None
    headers = {"User-Agent": "aigen-nft-safety/1.0"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def validate_address(address: str) -> str:
    if not ADDRESS_RE.match(address or ""):
        raise NFTSafetyError("collection address must be a 20-byte EVM address")
    return address


def chain_config(chain: str) -> dict[str, str]:
    key = (chain or "base").lower()
    if key not in SUPPORTED_CHAINS:
        raise NFTSafetyError(f"unsupported chain '{chain}'. Use one of: {', '.join(SUPPORTED_CHAINS)}")
    return SUPPORTED_CHAINS[key]


def explorer_address(address: str, chain: str) -> dict[str, Any]:
    cfg = chain_config(chain)
    return http_json(f"{cfg['explorer']}/api/v2/addresses/{address}")


def rpc_call(chain: str, to: str, data: str) -> str:
    cfg = chain_config(chain)
    response = http_json(
        cfg["rpc"],
        method="POST",
        payload={"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": to, "data": data}, "latest"]},
    )
    result = response.get("result")
    if not isinstance(result, str):
        raise NFTSafetyError(f"RPC returned no result: {response}")
    return result


def supports_interface(chain: str, address: str, interface_id: str) -> bool:
    data = "0x01ffc9a7" + interface_id.removeprefix("0x").rjust(64, "0")
    try:
        result = rpc_call(chain, address, data)
    except Exception:
        return False
    return bool(int(result or "0x0", 16))


def decode_address_word(word: str) -> str | None:
    raw = word.removeprefix("0x")[-40:]
    if len(raw) != 40:
        return None
    return "0x" + raw


def owner_of(chain: str, address: str) -> str | None:
    for selector in ("0x8da5cb5b", "0xf2fde38b"):
        try:
            result = rpc_call(chain, address, selector)
            owner = decode_address_word(result)
            if owner and int(owner, 16) != 0:
                return owner
        except Exception:
            continue
    return None


def build_signals(address_info: dict[str, Any], chain: str, address: str) -> list[Signal]:
    is_contract = bool(address_info.get("is_contract"))
    is_verified = bool(address_info.get("is_verified"))
    is_scam = bool(address_info.get("is_scam"))
    erc721 = supports_interface(chain, address, ERC721_INTERFACE) if is_contract else False
    erc1155 = supports_interface(chain, address, ERC1155_INTERFACE) if is_contract else False
    royalties = supports_interface(chain, address, ERC2981_INTERFACE) if is_contract else False
    owner = owner_of(chain, address) if is_contract else None

    return [
        Signal("contract_code", is_contract, 25, "address has deployed bytecode" if is_contract else "address is not a contract"),
        Signal("source_verified", is_verified, 20, "explorer source is verified" if is_verified else "explorer source is not verified"),
        Signal("nft_interface", erc721 or erc1155, 25, "supports ERC-721 or ERC-1155" if erc721 or erc1155 else "does not advertise ERC-721/ERC-1155"),
        Signal("royalty_interface", royalties, 10, "supports ERC-2981 royalties" if royalties else "no ERC-2981 royalty interface detected"),
        Signal("explorer_reputation", not is_scam, 15, "explorer does not mark contract as scam" if not is_scam else "explorer marks contract as scam"),
        Signal("owner_visibility", owner is not None, 5, f"owner/admin visible: {owner}" if owner else "owner/admin not detected"),
    ]


def score(signals: list[Signal]) -> int:
    return max(0, min(100, sum(signal.weight for signal in signals if signal.ok)))


def verdict_for(score_value: int) -> str:
    if score_value >= 80:
        return "LIKELY LEGITIMATE"
    if score_value >= 55:
        return "NEEDS REVIEW"
    return "HIGH RISK"


def analyze_collection(address: str, chain: str = "base") -> dict[str, Any]:
    clean_address = validate_address(address)
    chain_config(chain)
    info = explorer_address(clean_address, chain)
    signals = build_signals(info, chain, clean_address)
    score_value = score(signals)
    return {
        "chain": chain,
        "address": clean_address,
        "name": info.get("name") or info.get("token", {}).get("name"),
        "score": score_value,
        "verdict": verdict_for(score_value),
        "signals": [signal.__dict__ for signal in signals],
        "risk_flags": [signal.detail for signal in signals if not signal.ok],
        "explorer_url": f"{SUPPORTED_CHAINS[chain]['explorer']}/address/{clean_address}",
    }


def format_report(report: dict[str, Any]) -> str:
    flags = report.get("risk_flags") or ["none"]
    signal_lines = "\n".join(
        f"- {item['name']}: {'OK' if item['ok'] else 'WARN'} ({item['detail']})"
        for item in report.get("signals", [])
    )
    flag_lines = "\n".join(f"- {flag}" for flag in flags)
    return (
        "=== NFT SAFETY REPORT ===\n"
        f"Chain: {report['chain']}\n"
        f"Address: {report['address']}\n"
        f"Name: {report.get('name') or 'unknown'}\n"
        f"Score: {report['score']}/100\n"
        f"Verdict: {report['verdict']}\n\n"
        f"Signals:\n{signal_lines}\n\n"
        f"Risk flags:\n{flag_lines}\n\n"
        f"Explorer: {report['explorer_url']}"
    )


def _self_test() -> None:
    signals = [
        Signal("contract_code", True, 25, "address has deployed bytecode"),
        Signal("source_verified", True, 20, "explorer source is verified"),
        Signal("nft_interface", True, 25, "supports ERC-721"),
        Signal("royalty_interface", False, 10, "no royalty interface"),
        Signal("explorer_reputation", True, 15, "not marked scam"),
        Signal("owner_visibility", True, 5, "owner visible"),
    ]
    assert score(signals) == 90
    report = {
        "chain": "base",
        "address": "0x0000000000000000000000000000000000000001",
        "name": "Example NFT",
        "score": 90,
        "verdict": verdict_for(90),
        "signals": [signal.__dict__ for signal in signals],
        "risk_flags": ["no royalty interface"],
        "explorer_url": "https://base.blockscout.com/address/0x0000000000000000000000000000000000000001",
    }
    assert "NFT SAFETY REPORT" in format_report(report)
    assert verdict_for(50) == "HIGH RISK"
    assert validate_address("0x0000000000000000000000000000000000000001")
    print("nft_safety self-test passed")


if __name__ == "__main__":
    _self_test()
