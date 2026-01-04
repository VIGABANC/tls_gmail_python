#!/usr/bin/env python3
"""
Robust loader for PROJECT_URL / PROJECT_HOST / PROJECT_PORT with a Telegram /test handler.

Priority:
1. Environment variables (os.environ)
2. .env file (python-dotenv)
3. Project config modules (config.py, settings.py, or package-level attributes)
4. Defaults (None / 0)

Usage:
- pip install python-dotenv aiohttp python-telegram-bot>=20
- Configure either env vars, a .env file, or add PROJECT_* variables to your project's config module.
- Register register_handlers(application) with your python-telegram-bot Application instance.
"""
from __future__ import annotations
import os
import time
import asyncio
from typing import Tuple, Optional
from importlib import import_module

# Optional: load .env if present
try:
    from dotenv import load_dotenv, find_dotenv
    _dotenv_path = find_dotenv(raise_error_if_not_found=False)
    if _dotenv_path:
        load_dotenv(_dotenv_path)
except Exception:
    # python-dotenv not installed or .env not present — continue
    pass

# Helper to get from env or fallback from module attributes
def _get_from_env_or_module(name: str, modules: list[str]) -> Optional[str]:
    v = os.environ.get(name)
    if v:
        return v
    for mod_name in modules:
        try:
            mod = import_module(mod_name)
        except Exception:
            continue
        # try attribute or key (for dict-style configs)
        if hasattr(mod, name):
            return getattr(mod, name)
        if isinstance(mod, dict) and name in mod:
            return mod[name]
        # some projects use lowercase names
        ln = name.lower()
        if hasattr(mod, ln):
            return getattr(mod, ln)
        if isinstance(mod, dict) and ln in mod:
            return mod[ln]
    return None

# Common module names to attempt importing from your project
_COMMON_CONFIG_MODULES = [
    "config",
    "settings",
    "app.config",
    "app.settings",
    "tls_gmail_python.config",
    "tls_gmail_python.settings",
]

PROJECT_URL: Optional[str] = _get_from_env_or_module("PROJECT_URL", _COMMON_CONFIG_MODULES)
PROJECT_HOST: Optional[str] = _get_from_env_or_module("PROJECT_HOST", _COMMON_CONFIG_MODULES)
_project_port_raw = _get_from_env_or_module("PROJECT_PORT", _COMMON_CONFIG_MODULES) or os.environ.get("PROJECT_PORT")
try:
    PROJECT_PORT: int = int(_project_port_raw) if _project_port_raw else 0
except Exception:
    PROJECT_PORT = 0

# Optional override via explicit env (ensures env still has highest priority)
PROJECT_URL = os.environ.get("PROJECT_URL") or PROJECT_URL
PROJECT_HOST = os.environ.get("PROJECT_HOST") or PROJECT_HOST
_project_port_env = os.environ.get("PROJECT_PORT")
if _project_port_env:
    try:
        PROJECT_PORT = int(_project_port_env)
    except Exception:
        pass

# Rest is the same check + Telegram handler (async for ptb v20+)
import aiohttp
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

CHECK_TIMEOUT: int = int(os.environ.get("CHECK_TIMEOUT") or 5)

async def check_http(url: str, timeout: int = CHECK_TIMEOUT) -> Tuple[bool, str]:
    start = time.monotonic()
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=timeout) as resp:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                ok = resp.status < 500
                return ok, f"HTTP {resp.status} ({resp.reason}) — {elapsed_ms}ms"
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return False, f"HTTP error: {e} — {elapsed_ms}ms"

async def check_tcp(host: str, port: int, timeout: int = CHECK_TIMEOUT) -> Tuple[bool, str]:
    start = time.monotonic()
    try:
        fut = asyncio.open_connection(host, port)
        reader, writer = await asyncio.wait_for(fut, timeout=timeout)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return True, f"TCP {host}:{port} reachable — {elapsed_ms}ms"
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return False, f"TCP error: {e} — {elapsed_ms}ms"

async def _do_check() -> Tuple[bool, str]:
    if PROJECT_URL:
        return await check_http(PROJECT_URL)
    if PROJECT_HOST and PROJECT_PORT:
        return await check_tcp(PROJECT_HOST, PROJECT_PORT)
    return False, "No target configured. Set PROJECT_URL or PROJECT_HOST and PROJECT_PORT."

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.effective_message.reply_text("Checking project status...")
    ok, info = await _do_check()
    status = "ONLINE ✅" if ok else "OFFLINE ❌"
    await msg.edit_text(f"Project is {status}\nDetail: {info}")

async def test_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    txt = (update.effective_message.text or "").strip().lower()
    if txt == "test":
        await test_command(update, context)

def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("test", test_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, test_text_handler))
