#!/usr/bin/env python3
"""
telegram_test_status_ptb20.py
Async handler for python-telegram-bot v20+.

Usage:
- Set PROJECT_URL (e.g. "https://example.com") OR PROJECT_HOST and PROJECT_PORT.
- Register handlers:
    from telegram_test_status_ptb20 import register_handlers
    register_handlers(application)
"""
import os
import asyncio
import time
from typing import Tuple

import aiohttp
from telegram import Update
from telegram.ext import (
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    Application,
)

PROJECT_URL = os.environ.get("PROJECT_URL")
PROJECT_HOST = os.environ.get("PROJECT_HOST")
PROJECT_PORT = int(os.environ.get("PROJECT_PORT") or 0)


async def check_http(url: str, timeout: int = 5) -> Tuple[bool, str]:
    start = time.monotonic()
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, timeout=timeout) as resp:
                elapsed_ms = int((time.monotonic() - start) * 1000)
                ok = resp.status < 500
                return ok, f"HTTP {resp.status} ({resp.reason}) - {elapsed_ms}ms"
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return False, f"HTTP error: {e} - {elapsed_ms}ms"


async def check_tcp(host: str, port: int, timeout: int = 3) -> Tuple[bool, str]:
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
        return True, f"TCP {host}:{port} reachable - {elapsed_ms}ms"
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return False, f"TCP error: {e} - {elapsed_ms}ms"


async def _do_check() -> Tuple[bool, str]:
    if PROJECT_URL:
        return await check_http(PROJECT_URL)
    if PROJECT_HOST and PROJECT_PORT:
        return await check_tcp(PROJECT_HOST, PROJECT_PORT)
    return False, "No project target configured. Set PROJECT_URL or PROJECT_HOST & PROJECT_PORT."


async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Respond to /test command"""
    msg = await update.effective_message.reply_text("Checking project status...")
    ok, info = await _do_check()
    status = "ONLINE ✅" if ok else "OFFLINE ❌"
    await msg.edit_text(f"Project is {status}\nDetail: {info}")


async def test_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Respond to plain text 'test' (case-insensitive)"""
    text = (update.effective_message.text or "").strip().lower()
    if text != "test":
        return
    await test_command(update, context)


def register_handlers(application: Application) -> None:
    application.add_handler(CommandHandler("test", test_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, test_text_handler))
