#!/usr/bin/env python3
"""
Print what token is being read from KEY=value.env (safe: no full token printed).
Run: python scripts/check_telegram_token.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

# Same loader as telegram_command_center
def _looks_like_telegram_token(s):
    if not s or "xxx" in s.lower() or len(s) < 40:
        return False
    if ":" not in s:
        return False
    left, _, right = s.partition(":")
    return left.isdigit() and len(right) >= 30 and "x" not in right.lower().replace("_", "")

token_candidates = []
for name in ("KEY=value.env", ".env"):
    path = os.path.join(ROOT, name)
    if not os.path.isfile(path):
        continue
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("="):
                key, _, value = line.partition("=")
                value = value.strip().strip('"').strip("'").rstrip("|").strip()
                if key.strip().lstrip("|").strip().upper() == "TELEGRAM_BOT_TOKEN":
                    print(f"Line with TELEGRAM_BOT_TOKEN: length={len(value)}  first15={value[:15]!r}  last4={value[-4:]!r}  looks_real={_looks_like_telegram_token(value)}")
                if value and _looks_like_telegram_token(value):
                    token_candidates.append(value)
            for part in line.replace("|", " ").split():
                part = part.strip("'\"").rstrip(",")
                if _looks_like_telegram_token(part):
                    token_candidates.append(part)
    break
else:
    print("No KEY=value.env or .env found")
    sys.exit(1)

print(f"Token-like values found in file: {len(token_candidates)}")
if token_candidates:
    t = token_candidates[-1]
    print(f"Would use: length={len(t)}  first15={t[:15]!r}  last4={t[-4:]!r}")
else:
    print("No token-like value found. Replace the placeholder in KEY=value.env with the real token from @BotFather.")
