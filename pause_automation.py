"""
Pause all n8n automation (WF-GEN, WF-VIDEO, WF-ASSEMBLE).
Sets Redis system:paused so scheduled runs do nothing.
Uses same config as setup_redis.py (Infrastructure/config.json).
Run from E:\KLIPORA: python pause_automation.py
"""

import json
import sys
import os
import urllib.request
import urllib.error

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KLIPORA_ROOT = SCRIPT_DIR
CONFIG_PATHS = [
    os.path.join(KLIPORA_ROOT, "Infrastructure", "config.json"),
    os.path.join(SCRIPT_DIR, "config.json"),
]
config = None
for path in CONFIG_PATHS:
    if os.path.exists(path):
        with open(path) as f:
            config = json.load(f)
        break
if not config:
    print("ERROR: config.json not found.")
    sys.exit(1)
if "upstash" in config:
    REDIS_URL = config["upstash"]["redis_rest_url"].rstrip("/")
    REDIS_TOKEN = config["upstash"]["redis_rest_token"]
elif "upstash_url" in config:
    REDIS_URL = config["upstash_url"].rstrip("/")
    REDIS_TOKEN = config["upstash_token"]
else:
    print("ERROR: No Upstash credentials in config.json")
    sys.exit(1)

def redis_cmd(command_parts):
    path = "/".join(urllib.request.quote(str(p), safe="") for p in command_parts)
    url = f"{REDIS_URL}/{path}"
    req = urllib.request.Request(
        url, method="POST",
        headers={"Authorization": f"Bearer {REDIS_TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"   ⚠️ Error: {e}")
        return None

print("Pausing automation (setting system:paused)...")
r = redis_cmd(["SET", "system:paused", "true"])
if r is not None:
    print("OK: system:paused set. WF-GEN, WF-VIDEO, WF-ASSEMBLE will no-op until you unpause.")
else:
    print("FAILED: Could not set system:paused.")
    sys.exit(1)
