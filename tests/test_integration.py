#!/usr/bin/env python3
"""
telegram_test_status.py

Async /test handler (python-telegram-bot v20+)

Checks:
- PROJECT_URL (HTTP)
- or PROJECT_HOST + PROJECT_PORT (TCP)
"""

from __future__ import annotations

import os
import time
import asyncio
from typing import Tuple, Optional
from importlib import import_module

# --- Load .env safely ---
try:
    from dotenv import load_dotenv, find_dotenv
    dotenv_path = find_dotenv()
    if dotenv_path:
        load_dotenv(dotenv_path)
except Exception:
    pass


# --- Config helpers ---
def get_config(name: str, modules: list[str]) -> Optional[str]:
    if os.getenv(name):
        return os.getenv(name)

    for module_name in modules:
        try:
            mod = import_module(module_name)
        except Exception:
            continue

        if hasattr(mod, name):
            return getattr(mod, name)

        if hasattr(mod, name.lower()):
            return getattr(mod, name.lower())

        if hasattr(mod, "CONFIG") and isinstance(mod.CONFIG, dict):
            return mod.CONFIG.get(name) or mod.CONFIG.get(name.lower())

    return None


COMMON_CONFIG_MODULES = [
    "config",
    "settings",
    "app.config",
    "app.settings",
]

# --- Defaults ---
FALLBACK_URL = "https://tlscontact-visa-watcher-py-production-a1a8.up.railway.app/"
CHECK_TIMEOUT = int(os.getenv("CHECK_TIMEOUT", "5"))

# --- Resolve target ---
PROJECT_URL = os.getenv("PROJECT_URL") or get_config("PROJECT_URL", COMMON_CONFIG_MODULES) or FALLBACK_URL
PROJECT_HOST = os.getenv("PROJECT_HOST") or get_config("PROJECT_HOST", COMMON_CONFIG_MODULES)

try:
    PROJECT_PORT = int(os.getenv("PROJECT_PORT") or get_config("PROJECT_PORT", COMMON_CONFIG_MODULES) or 0)
except ValueError:
    PROJECT_PORT = 0


# --- Networking ---
import aiohttp
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


async def check_http(url: str) -> Tuple[bool, str]:
    start = time.monotonic()
    timeout = aiohttp.ClientTimeout(total=CHECK_TIMEOUT)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, allow_redirects=True) as resp:
                elapsed = int((time.monotonic() - start) * 1000)
                ok = 200 <= resp.status < 400
                return ok, f"HTTP {resp.status} — {elapsed}ms"
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return False, f"HTTP error: {e} — {elapsed}ms"


async def check_tcp(host: str, port: int) -> Tuple[bool, str]:
    start = time.monotonic()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=CHECK_TIMEOUT,
        )
        writer.close()
        await writer.wait_closed()
        elapsed = int((time.monotonic() - start) * 1000)
        return True, f"TCP {host}:{port} reachable — {elapsed}ms"
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return False, f"TCP error: {e} — {elapsed}ms"


async def do_check() -> Tuple[bool, str]:
    if PROJECT_URL:
        return await check_http(PROJECT_URL)

    if PROJECT_HOST and PROJECT_PORT:
        return await check_tcp(PROJECT_HOST, PROJECT_PORT)

    return False, "No target configured (PROJECT_URL or PROJECT_HOST + PROJECT_PORT)."


# --- Telegram handlers ---
async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.effective_message.reply_text("🔍 Checking project status...")
    ok, info = await do_check()
    status = "ONLINE ✅" if ok else "OFFLINE ❌"
    await msg.edit_text(f"Project status: {status}\n{info}")


async def test_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.effective_message.text or "").strip().lower()
    if text == "test":
        await test_command(update, context)


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("test", test_command))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, test_text_handler)
    )
