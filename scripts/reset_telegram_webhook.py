#!/usr/bin/env python3
"""
Clear the Telegram bot webhook so the Python bot can use long polling.
Run from repo root: python scripts/reset_telegram_webhook.py
Loads TELEGRAM_BOT_TOKEN from KEY=value.env or .env.
"""
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_env():
    """Load first env file found: KEY=value.env then .env. Only first file is used (same as bot)."""
    for name in ("KEY=value.env", ".env"):
        path = os.path.join(ROOT, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line and not line.startswith("="):
                        key, _, value = line.partition("=")
                        key = key.strip().lstrip("|").strip()
                        value = value.strip().strip('"').strip("'").rstrip("|").strip()
                        if key and key not in os.environ:
                            os.environ[key] = value
        except Exception:
            pass
        return  # use only first file found, so KEY=value.env wins over .env


def main():
    _load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("TELEGRAM_BOT_TOKEN not found in KEY=value.env or .env")
        sys.exit(1)
    url = f"https://api.telegram.org/bot{token}/deleteWebhook"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode()
        print("Webhook cleared. Response:", data[:200])
    except Exception as e:
        print("Failed:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
