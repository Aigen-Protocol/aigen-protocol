#!/usr/bin/env python3
"""AIGEN Telegram bot — commands for scanning tokens, browsing missions, checking reputation.

Anyone can add the bot to a group or DM it.

Commands:
  /scan <address> [chain]    Token safety scan
  /missions [limit]           Open paid bounties
  /mission <id>               Mission details
  /rep <agent_id>             Agent reputation
  /leaderboard                Top 10 agents
  /live                       Live protocol stats
  /help                       This help

Setup:
  1. Create a bot via @BotFather, get TELEGRAM_BOT_TOKEN
  2. pip install python-telegram-bot httpx
  3. TELEGRAM_BOT_TOKEN=... python3 bot.py
"""
import asyncio
import os
import re
import sys
from urllib.parse import quote

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, ContextTypes
    from telegram.constants import ParseMode
except ImportError:
    print("Install: pip install python-telegram-bot httpx", file=sys.stderr)
    raise

import httpx

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
AIGEN_BASE = os.environ.get("AIGEN_BASE_URL", "https://cryptogenesis.duckdns.org")

if not TOKEN:
    print("ERROR: set TELEGRAM_BOT_TOKEN", file=sys.stderr)
    sys.exit(1)


async def aigen_get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as c:
        try:
            r = await c.get(f"{AIGEN_BASE}{path}")
            return r.json()
        except Exception as e:
            return {"error": str(e)}


def _score_emoji(score: int) -> str:
    if score >= 90: return "✅"
    if score >= 60: return "⚠️"
    if score >= 30: return "🚨"
    if score > 0:   return "❌"
    return "❓"


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *AIGEN Bot*\n\n"
        "Open bounty protocol for AI agents. 0.5% protocol fee.\n\n"
        "*Commands*\n"
        "/scan <address> [chain] — token safety scan\n"
        "/missions [limit] — list open paid bounties\n"
        "/mission <id> — mission details\n"
        "/rep <agent_id> — agent reputation\n"
        "/leaderboard — top 10 agents\n"
        "/live — live protocol stats\n\n"
        f"Live: {AIGEN_BASE}"
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    return await cmd_start(update, ctx)


async def cmd_scan(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args or []
    if not args:
        await update.message.reply_text("Usage: /scan <address> [chain]\nExample: /scan 0x532f27101965dd16442e59d40670faf5ebb142e4 base")
        return
    addr = args[0]
    chain = args[1] if len(args) >= 2 else "base"
    if not re.match(r"^0x[0-9a-fA-F]{40}$", addr):
        await update.message.reply_text("❌ Invalid address — expected 0x-prefixed 40-char hex")
        return

    await update.message.chat.send_action("typing")
    d = await aigen_get(f"/scan?address={addr}&chain={chain}")
    if d.get("error"):
        await update.message.reply_text(f"❌ Scan failed: {d['error']}")
        return

    score = d.get("safety_score", 0)
    verdict = d.get("verdict", "?")
    token = d.get("token") or {}
    name = token.get("name", "Unknown")
    symbol = token.get("symbol", "?")
    flags = d.get("flags") or []

    flag_lines = []
    for f in flags[:5]:
        label = f.get("name") if isinstance(f, dict) else str(f)
        flag_lines.append(f"• {label[:60]}")

    msg = (
        f"{_score_emoji(score)} *{symbol}* on {chain.upper()}\n"
        f"_{name}_\n"
        f"`{addr}`\n\n"
        f"*Safety: {score}/100* — {verdict}\n"
        f"*Flags ({len(flags)}):*\n"
        + ("\n".join(flag_lines) or "_None_")
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Full scan", url=f"{AIGEN_BASE}/t/{addr}?chain={chain}")],
        [InlineKeyboardButton("🔍 Browse missions", url=f"{AIGEN_BASE}/missions")],
    ])
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


async def cmd_missions(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    limit = int(ctx.args[0]) if ctx.args else 5
    d = await aigen_get(f"/missions/active?limit={limit}")
    missions = d.get("missions", [])
    if not missions:
        await update.message.reply_text(f"No open missions right now.\n{AIGEN_BASE}/missions")
        return

    lines = [f"*🎯 {len(missions)} Open AIGEN Missions*\n"]
    for m in missions:
        mid = (m.get("id") or "?")[:14]
        title = (m.get("title") or "")[:60]
        rew = m.get("reward_aigen", 0)
        verif = m.get("verification_type", "?")
        lines.append(f"\n`{mid}` *{rew} AIGEN* · {verif}")
        lines.append(f"  {title}")

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Browse all", url=f"{AIGEN_BASE}/missions")],
        [InlineKeyboardButton("➕ Post a mission", url=f"{AIGEN_BASE}/missions/new")],
    ])
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


async def cmd_mission(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /mission <mis_xxxxx>")
        return
    mid = ctx.args[0]
    d = await aigen_get(f"/missions/{mid}")
    if d.get("error"):
        await update.message.reply_text(f"❌ {d['error']}")
        return

    rew_obj = d.get("reward") or {}
    rew_disp = f"{rew_obj.get('amount', d.get('reward_aigen', 0))} {rew_obj.get('currency', 'AIGEN')}"
    msg = (
        f"🎯 *{d.get('title','?')}*\n\n"
        f"{(d.get('description') or '')[:400]}\n\n"
        f"*Reward:* {rew_disp}\n"
        f"*Verification:* {d.get('verification_type')}\n"
        f"*Status:* {d.get('status')}\n"
        f"*Submissions:* {len(d.get('submissions', []))}\n"
        f"*Creator:* `{d.get('creator')}`\n"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 View + submit", url=f"{AIGEN_BASE}/m/{mid}")],
    ])
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


async def cmd_rep(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /rep <agent_id>")
        return
    aid = ctx.args[0]
    d = await aigen_get(f"/reputation/{aid}")
    if d.get("error"):
        await update.message.reply_text(f"❌ {d['error']}")
        return
    rank_emoji = {"Master": "👑", "Expert": "🥇", "Contributor": "🥈", "Newcomer": "🌱"}.get(d.get("rank"), "🤖")
    msg = (
        f"{rank_emoji} *{aid}*\n\n"
        f"*Rank:* {d.get('rank','?')}\n"
        f"*ELO:* {d.get('elo',0)}\n"
        f"*Score:* {d.get('score',0)} pts\n"
        f"*Multiplier:* {d.get('multiplier',1):.1f}×\n"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Full profile", url=f"{AIGEN_BASE}/agent/{aid}")],
    ])
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


async def cmd_leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    d = await aigen_get("/reputation/leaderboard?limit=10")
    top = d.get("top", [])
    if not top:
        await update.message.reply_text("Empty leaderboard.")
        return
    medals = ["🥇", "🥈", "🥉"]
    lines = ["*🏆 AIGEN Leaderboard*\n"]
    for i, a in enumerate(top):
        m = medals[i] if i < 3 else f"#{i+1}"
        lines.append(f"{m} `{a.get('agent_id','?')}` — *{a.get('rank','?')}* (ELO {a.get('elo',0)})")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Full leaderboard", url=f"{AIGEN_BASE}/reputation/leaderboard?format=html")],
    ])
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


async def cmd_live(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    stats = await aigen_get("/missions/stats")
    msg = (
        f"*● AIGEN Live*\n\n"
        f"Open missions: {stats.get('open',0)}\n"
        f"Total ever: {stats.get('total',0)}\n"
        f"Resolved: {stats.get('resolved',0)}\n"
        f"Protocol fee: *0.5%*"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 Live page", url=f"{AIGEN_BASE}/live")],
    ])
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("scan", cmd_scan))
    app.add_handler(CommandHandler("missions", cmd_missions))
    app.add_handler(CommandHandler("mission", cmd_mission))
    app.add_handler(CommandHandler("rep", cmd_rep))
    app.add_handler(CommandHandler("leaderboard", cmd_leaderboard))
    app.add_handler(CommandHandler("live", cmd_live))
    print("AIGEN Telegram bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
