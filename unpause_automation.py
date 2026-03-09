"""
Unpause automation — clear Redis system:paused so WF-GEN, WF-VIDEO, WF-ASSEMBLE run again.
Uses same config as setup_redis.py.
Run from E:\KLIPORA: python unpause_automation.py
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

print("Unpausing automation (clearing system:paused)...")
r = redis_cmd(["DEL", "system:paused"])
if r is not None:
    print("OK: system:paused cleared. Scheduled workflows will run again at their cron times.")
else:
    print("FAILED: Could not clear system:paused.")
    sys.exit(1)
