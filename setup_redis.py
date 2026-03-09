"""
KLIPORA OS — Redis Setup Script (Python)
Run from E:\KLIPORA: python setup_redis.py

Reads config from E:\KLIPORA\Infrastructure\config.json
Initialises all system keys, queues, and config in Upstash Redis.
"""

import json
import sys
import os
import urllib.request
import urllib.error

# ── Load config ──────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
KLIPORA_ROOT = os.path.dirname(SCRIPT_DIR) if os.path.basename(SCRIPT_DIR) == "KLIPORA HQ" else SCRIPT_DIR

# Try multiple config locations
CONFIG_PATHS = [
    os.path.join(KLIPORA_ROOT, "Infrastructure", "config.json"),
    os.path.join(SCRIPT_DIR, "config.json"),
    os.path.join(KLIPORA_ROOT, "config.json"),
]

config = None
config_path_used = None
for path in CONFIG_PATHS:
    if os.path.exists(path):
        with open(path) as f:
            config = json.load(f)
        config_path_used = path
        break

if not config:
    print("❌ config.json not found. Tried:")
    for p in CONFIG_PATHS:
        print(f"   {p}")
    sys.exit(1)

print(f"✅ Loaded config from: {config_path_used}")

# ── Extract credentials (handles both config formats) ─────────────────────
# KLIPORA HQ format: {"upstash": {"redis_rest_url": ..., "redis_rest_token": ...}}
# E:\KLIPORA format: {"upstash_url": ..., "upstash_token": ...}
if "upstash" in config:
    REDIS_URL   = config["upstash"]["redis_rest_url"].rstrip("/")
    REDIS_TOKEN = config["upstash"]["redis_rest_token"]
elif "upstash_url" in config:
    REDIS_URL   = config["upstash_url"].rstrip("/")
    REDIS_TOKEN = config["upstash_token"]
else:
    print("❌ Could not find Upstash credentials in config.json")
    sys.exit(1)

print(f"🔗 Redis URL: {REDIS_URL}")

# ── Redis helper ──────────────────────────────────────────────────────────────
def redis(command_parts):
    """
    Execute an Upstash REST command.
    command_parts: list of strings, e.g. ["SET", "key", "value"]
    Returns the parsed JSON response body.
    """
    path = "/".join(urllib.request.quote(str(p), safe="") for p in command_parts)
    url  = f"{REDIS_URL}/{path}"
    req  = urllib.request.Request(
        url,
        method="POST",
        headers={"Authorization": f"Bearer {REDIS_TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"   ⚠️  HTTP {e.code}: {body}")
        return None
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
        return None

# ── Initialise keys ───────────────────────────────────────────────────────────
print("\n📋 Initialising KLIPORA system keys...\n")

tasks = [
    # System settings
    ("SET",  ["system:videos_per_day",  "2"],         "System: videos_per_day = 2"),
    ("SET",  ["system:voice_style",     "dramatic"],  "System: voice_style = dramatic"),
    ("SET",  ["system:active_genre",    "all"],       "System: active_genre = all"),
    ("SET",  ["system:brand_name",      "Klipora"],   "System: brand_name = Klipora"),

    # Clear paused flag so pipeline can run
    ("DEL",  ["system:paused"],                       "System: paused flag cleared (pipeline can run)"),

    # Clear dead-letter queue
    ("DEL",  ["failed_queue"],                        "Queue: failed_queue cleared"),

    # Reset analytics counters (only if they don't exist)
    ("SETNX", ["analytics:total", "0"],               "Analytics: total counter initialised"),

    # Initialise company-level keys (Phase 2 agent layer)
    ("SET",  ["company:active_projects", "[]"],       "Company: active_projects = []"),
    ("SET",  ["agent:cto:infra_status",  "healthy"],  "Agent: CTO infra_status = healthy"),

    # Finance (policy: initial budget $440 max)
    ("SET",  ["finance:capital_initial",  "440"],      "Finance: capital_initial = 440"),
    ("SET",  ["finance:spent_total",     "0"],        "Finance: spent_total = 0"),
    ("SET",  ["finance:remaining",       "440"],      "Finance: remaining = 440"),
    ("SET",  ["finance:revenue:today",    "0"],       "Finance: revenue:today = 0"),
    ("SET",  ["finance:revenue:month",   "0"],        "Finance: revenue:month = 0"),
    ("SET",  ["finance:spend:category:api_usage", "0"], "Finance: api_usage = 0"),
    ("SET",  ["finance:spend:category:cloud_hosting", "0"], "Finance: cloud_hosting = 0"),
    ("SET",  ["finance:spend:category:tools", "0"],   "Finance: tools = 0"),
    ("SET",  ["finance:spend:category:advertising", "0"], "Finance: advertising = 0"),

    # Experiment Lab (max 3 active)
    ("SET",  ["experiments:active", "[]"],            "Experiments: active = []"),
]

ok = 0
fail = 0
for cmd, args, label in tasks:
    result = redis([cmd] + args)
    if result is not None:
        print(f"   ✅ {label}")
        ok += 1
    else:
        print(f"   ❌ FAILED: {label}")
        fail += 1

# ── Verify used_topics SET ────────────────────────────────────────────────────
print("\n🔍 Checking used_topics SET...")
result = redis(["SMEMBERS", "used_topics"])
if result and "result" in result:
    members = result["result"] or []
    count   = len(members)
    print(f"   📌 used_topics has {count} entries in Redis")
    if count == 0:
        print("   ✅ Clean slate — no topics used yet")
    elif count <= 5:
        print(f"   ⚠️  Only {count} topics — looks like a fresh start (good)")
    else:
        print(f"   ℹ️  {count} topics already marked as used")
else:
    print("   ⚠️  Could not read used_topics")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*55}")
print(f"✅ {ok} keys set successfully")
if fail:
    print(f"❌ {fail} keys failed")
print(f"{'='*55}")

print("""
⚡ NEXT STEPS:
   1. Import 5 workflow JSONs into n8n:
      → https://n8n-production-2762.up.railway.app
      → New Workflow → ⋮ menu → Import from File
      → Import each file from KLIPORA HQ/workflows/
      → Activate each workflow

   2. Test the pipeline:
      → Send /generate to your Telegram bot
      → Watch the wizard: genre → style → narration → confirm
""")
