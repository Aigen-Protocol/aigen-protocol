# SafeAgent Telegram Bot

`telegram_bot.py` turns SafeAgent Shield into a Telegram bot. Users paste an
EVM token contract address and receive a SafeAgent safety report without leaving
Telegram.

## Features

- `/scan 0x... base` returns token name, score, verdict, decision, and flags.
- `/shield 0x... base` is an alias for `/scan`.
- `/honeypot 0x... base` calls the SafeAgent honeypot endpoint.
- `/price 0x... base` calls the SafeAgent price endpoint.
- Plain messages containing a token address default to a Base scan.
- Supported chains: Base, Ethereum, Optimism, Arbitrum, Polygon, BSC.
- No private keys, wallet signatures, or custody. The bot only reads public
  SafeAgent endpoints and sends Telegram messages.
- No extra Python packages. It uses the Telegram HTTPS Bot API directly.

## Run

Create a Telegram bot with BotFather, then run:

```bash
export TELEGRAM_BOT_TOKEN="123456:telegram-token"
python3 telegram_bot.py
```

Optional environment variables:

```bash
export SAFEAGENT_API_BASE="https://cryptogenesis.duckdns.org"
export SAFEAGENT_DEFAULT_CHAIN="base"
```

## Verify Offline

The self-test does not call Telegram or SafeAgent. It validates command parsing
and response formatting with a fake SafeAgent client.

```bash
python3 telegram_bot.py --self-test
python3 -m py_compile telegram_bot.py
```

## Example User Flow

```text
User: /scan 0x833589fcd6edb6e08f4c7c32d4f71b54bdA02913 base

Bot:
SafeAgent Shield
Token: USD Coin / USDC (0x8335...)
Chain: base
Score: 100/100
Verdict: SYSTEM TOKEN
Decision: GO
Flags:
- none
Raw scan: https://cryptogenesis.duckdns.org/scan?address=...
```

## Operational Notes

- Use one bot token per deployment.
- Run behind systemd, Docker, or another process supervisor for production.
- Telegram messages are sent with HTML parse mode; token metadata and flags are
  escaped before sending.
- SafeAgent network errors are returned as user-facing "Could not scan"
  messages instead of crashing the bot.
