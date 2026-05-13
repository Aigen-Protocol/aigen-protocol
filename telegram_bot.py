#!/usr/bin/env python3
"""Telegram wrapper for SafeAgent Shield.

The bot is intentionally dependency-free: it uses Telegram's HTTPS Bot API
directly and calls the public SafeAgent REST endpoints. Set TELEGRAM_BOT_TOKEN
and run this file to start long polling.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


SAFEAGENT_API_BASE = os.environ.get("SAFEAGENT_API_BASE", "https://cryptogenesis.duckdns.org").rstrip("/")
TELEGRAM_API_BASE = "https://api.telegram.org"
DEFAULT_CHAIN = os.environ.get("SAFEAGENT_DEFAULT_CHAIN", "base")
SUPPORTED_CHAINS = {"base", "ethereum", "optimism", "arbitrum", "polygon", "bsc"}
ADDRESS_RE = re.compile(r"0x[a-fA-F0-9]{40}")
MAX_FLAGS = 8


class BotError(RuntimeError):
    """Raised for user-facing bot errors."""


def http_json(method: str, url: str, *, payload: dict[str, Any] | None = None, timeout: int = 20) -> dict[str, Any]:
    data = None
    headers = {"User-Agent": "aigen-telegram-shield/1.0"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise BotError(f"HTTP {exc.code}: {body[:180]}") from exc
    except urllib.error.URLError as exc:
        raise BotError(f"Network error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise BotError("Upstream returned invalid JSON") from exc


def normalize_chain(value: str | None) -> str:
    chain = (value or DEFAULT_CHAIN).lower().strip()
    if chain not in SUPPORTED_CHAINS:
        supported = ", ".join(sorted(SUPPORTED_CHAINS))
        raise BotError(f"Unsupported chain '{chain}'. Use one of: {supported}.")
    return chain


def extract_address_and_chain(text: str) -> tuple[str, str]:
    address_match = ADDRESS_RE.search(text)
    if not address_match:
        raise BotError("Send an EVM token contract address, for example /scan 0x... base")

    parts = text.replace(",", " ").split()
    chain = DEFAULT_CHAIN
    for part in parts:
        candidate = part.lower().strip()
        if candidate in SUPPORTED_CHAINS:
            chain = candidate
            break
    return address_match.group(0), normalize_chain(chain)


@dataclass
class SafeAgentClient:
    api_base: str = SAFEAGENT_API_BASE

    def get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        query = urllib.parse.urlencode(params)
        return http_json("GET", f"{self.api_base}{path}?{query}", timeout=30)

    def scan(self, address: str, chain: str) -> dict[str, Any]:
        return self.get("/scan", {"address": address, "chain": chain})

    def honeypot(self, address: str, chain: str) -> dict[str, Any]:
        return self.get("/honeypot", {"address": address, "chain": chain})

    def price(self, address: str, chain: str) -> dict[str, Any]:
        return self.get("/price", {"address": address, "chain": chain})


def value_from(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


def token_label(data: dict[str, Any], address: str) -> str:
    token = data.get("token") if isinstance(data.get("token"), dict) else {}
    name = value_from(token, "name", default=value_from(data, "name", default="Unknown"))
    symbol = value_from(token, "symbol", default=value_from(data, "symbol", default="???"))
    return f"{name} / {symbol} ({address})"


def risk_flags(data: dict[str, Any]) -> list[str]:
    flags = value_from(data, "flags", "risks", "risk_factors", default=[])
    if isinstance(flags, str):
        return [flags]
    if isinstance(flags, list):
        return [str(flag) for flag in flags if flag]
    return []


def decision_for(score: int) -> str:
    if score >= 80:
        return "GO"
    if score >= 50:
        return "CAUTION"
    return "BLOCK"


def format_scan_report(address: str, chain: str, data: dict[str, Any]) -> str:
    score = int(value_from(data, "safety_score", "score", default=0) or 0)
    verdict = value_from(data, "verdict", "risk_level", default="UNKNOWN")
    flags = risk_flags(data)
    flag_lines = "\n".join(f"- {html.escape(flag)}" for flag in flags[:MAX_FLAGS]) if flags else "- none"

    return (
        "<b>SafeAgent Shield</b>\n"
        f"<b>Token:</b> {html.escape(token_label(data, address))}\n"
        f"<b>Chain:</b> {html.escape(chain)}\n"
        f"<b>Score:</b> {score}/100\n"
        f"<b>Verdict:</b> {html.escape(str(verdict))}\n"
        f"<b>Decision:</b> {decision_for(score)}\n\n"
        f"<b>Flags:</b>\n{flag_lines}\n\n"
        f"<a href=\"{html.escape(SAFEAGENT_API_BASE)}/scan?address={html.escape(address)}&amp;chain={html.escape(chain)}\">Raw scan</a>"
    )


def format_price_report(address: str, chain: str, data: dict[str, Any]) -> str:
    price = value_from(data, "price_usd", "priceUsd", "price", default="unknown")
    symbol = value_from(data, "symbol", default=address[:10])
    return (
        "<b>SafeAgent Price</b>\n"
        f"<b>Token:</b> {html.escape(str(symbol))}\n"
        f"<b>Chain:</b> {html.escape(chain)}\n"
        f"<b>Price:</b> {html.escape(str(price))}"
    )


def format_honeypot_report(address: str, chain: str, data: dict[str, Any]) -> str:
    is_honeypot = bool(value_from(data, "is_honeypot", "honeypot", default=False))
    buy_tax = value_from(data, "buy_tax", "buyTax", default="?")
    sell_tax = value_from(data, "sell_tax", "sellTax", default="?")
    status = "YES - high risk" if is_honeypot else "NO - sell simulation passed"
    return (
        "<b>SafeAgent Honeypot Test</b>\n"
        f"<b>Token:</b> {html.escape(address)}\n"
        f"<b>Chain:</b> {html.escape(chain)}\n"
        f"<b>Honeypot:</b> {status}\n"
        f"<b>Buy tax:</b> {html.escape(str(buy_tax))}\n"
        f"<b>Sell tax:</b> {html.escape(str(sell_tax))}"
    )


HELP_TEXT = """<b>AIGEN SafeAgent Telegram Bot</b>

Paste an EVM token contract address or use:

<code>/scan 0x... base</code>
<code>/shield 0x... optimism</code>
<code>/honeypot 0x... base</code>
<code>/price 0x... base</code>

Supported chains: base, ethereum, optimism, arbitrum, polygon, bsc.
"""


class TelegramBot:
    def __init__(self, token: str, client: SafeAgentClient | None = None):
        if not token:
            raise BotError("TELEGRAM_BOT_TOKEN is required")
        self.token = token
        self.client = client or SafeAgentClient()
        self.api_base = f"{TELEGRAM_API_BASE}/bot{token}"

    def telegram(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        return http_json("POST", f"{self.api_base}/{method}", payload=payload, timeout=20)

    def send_message(self, chat_id: int, text: str) -> None:
        self.telegram(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text[:3900],
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
        )

    def handle_text(self, text: str) -> str:
        command = text.strip().split(maxsplit=1)[0].lower() if text.strip() else ""
        if command in {"/start", "/help"}:
            return HELP_TEXT

        address, chain = extract_address_and_chain(text)
        if command == "/price":
            return format_price_report(address, chain, self.client.price(address, chain))
        if command == "/honeypot":
            return format_honeypot_report(address, chain, self.client.honeypot(address, chain))

        return format_scan_report(address, chain, self.client.scan(address, chain))

    def handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        text = message.get("text") or ""
        if not chat_id or not text:
            return
        try:
            reply = self.handle_text(text)
        except BotError as exc:
            reply = f"<b>Could not scan</b>\n{html.escape(str(exc))}"
        self.send_message(chat_id, reply)

    def run(self) -> None:
        offset = 0
        while True:
            payload = {"timeout": 50, "offset": offset}
            try:
                response = self.telegram("getUpdates", payload)
                for update in response.get("result", []):
                    offset = max(offset, int(update.get("update_id", 0)) + 1)
                    self.handle_update(update)
            except BotError as exc:
                print(f"telegram bot error: {exc}", file=sys.stderr)
                time.sleep(5)


class FakeClient(SafeAgentClient):
    def scan(self, address: str, chain: str) -> dict[str, Any]:
        return {
            "token": {"name": "USD Coin", "symbol": "USDC"},
            "safety_score": 100,
            "verdict": "SYSTEM TOKEN",
            "flags": [],
        }

    def honeypot(self, address: str, chain: str) -> dict[str, Any]:
        return {"is_honeypot": False, "buy_tax": 0, "sell_tax": 0}

    def price(self, address: str, chain: str) -> dict[str, Any]:
        return {"symbol": "USDC", "price_usd": "1.00"}


def self_test() -> None:
    usdc = "0x833589fcd6edb6e08f4c7c32d4f71b54bdA02913"
    address, chain = extract_address_and_chain(f"/scan {usdc} base")
    assert address == usdc
    assert chain == "base"
    bot = TelegramBot("test-token", client=FakeClient())
    scan = bot.handle_text(f"/scan {usdc} base")
    assert "SafeAgent Shield" in scan and "100/100" in scan and "USDC" in scan
    price = bot.handle_text(f"/price {usdc} base")
    assert "SafeAgent Price" in price and "1.00" in price
    honeypot = bot.handle_text(f"/honeypot {usdc} base")
    assert "Honeypot" in honeypot and "NO" in honeypot
    help_text = bot.handle_text("/help")
    assert "Supported chains" in help_text
    print("telegram_bot self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the AIGEN SafeAgent Telegram bot")
    parser.add_argument("--self-test", action="store_true", help="run offline parser/formatter tests")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return 0
    TelegramBot(os.environ.get("TELEGRAM_BOT_TOKEN", "")).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
