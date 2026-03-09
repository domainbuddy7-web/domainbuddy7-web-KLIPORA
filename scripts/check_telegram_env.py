#!/usr/bin/env python3
"""
Print what the bot will use for TELEGRAM_BOT_TOKEN and OWNER_TELEGRAM_ID (masked).
Run from repo root: python scripts/check_telegram_env.py
Use this to verify KEY=value.env is read correctly and no later line overwrites the token.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Load env the same way the bot does (first file only)
for name in ("KEY=value.env", ".env"):
    path = os.path.join(ROOT, name)
    if not os.path.isfile(path):
        continue
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line and not line.startswith("="):
                key, _, value = line.partition("=")
                key = key.strip().lstrip("|").strip()
                value = value.strip().strip('"').strip("'").rstrip("|").strip()
                if not key or key in os.environ:
                    continue
                os.environ[key] = value
    break  # only first file (KEY=value.env wins over .env)

token = (os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN") or "").strip()
owner = (os.environ.get("OWNER_TELEGRAM_ID") or os.environ.get("TELEGRAM_CHAT_ID") or "").strip()

print("From first file found (KEY=value.env or .env):")
print("  TELEGRAM_BOT_TOKEN:", f"set ({len(token)} chars): {token[:6]}...{token[-4:]}" if token else "NOT SET")
print("  OWNER_TELEGRAM_ID:", owner or "NOT SET")
if token and len(token) < 40:
    print("  WARNING: Token shorter than 40 chars - Telegram tokens are usually longer. Check for truncation or wrong variable.")
if token and ":" not in token:
    print("  WARNING: Token has no ':' - Telegram tokens look like 123456789:AAH...")
