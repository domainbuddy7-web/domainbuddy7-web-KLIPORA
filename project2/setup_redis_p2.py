"""
Project 2 — Initialize p2: Redis keys (same Upstash DB, prefix p2:).

Run from repo root after loading Project 2 env, or use: .\project2\run_setup_p2.ps1

Sets: p2:system:videos_per_day, p2:system:voice_style, p2:system:active_genre,
      p2:system:brand_name; clears p2:system:paused and p2:failed_queue.
"""

import os
import sys

# Repo root (parent of project2)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

# Load project2 env file so UPSTASH_* are set
_env_file = os.path.join(SCRIPT_DIR, "KEY=value.env.project2")
if os.path.isfile(_env_file):
    with open(_env_file, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line and not line.startswith("="):
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
else:
    print("Optional: create project2/KEY=value.env.project2 for Upstash credentials.")
    print("Or set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN in the environment.\n")

from Infrastructure.redis_client import get_redis_client

def main():
    redis = get_redis_client(prefix="p2:")
    print("Initializing Project 2 Redis keys (prefix p2:)...\n")

    redis.set("system:videos_per_day", "2")
    print("  p2:system:videos_per_day = 2")
    redis.set("system:voice_style", "dramatic")
    print("  p2:system:voice_style = dramatic")
    redis.set("system:active_genre", "all")
    print("  p2:system:active_genre = all")
    redis.set("system:brand_name", "Klipora P2")
    print("  p2:system:brand_name = Klipora P2")
    redis.delete("system:paused")
    print("  p2:system:paused cleared (pipeline can run)")
    redis.delete("failed_queue")
    print("  p2:failed_queue cleared")

    print("\nDone. Project 2 keys are ready. Run the P2 bot: .\\project2\\run_bot.ps1")

if __name__ == "__main__":
    main()
