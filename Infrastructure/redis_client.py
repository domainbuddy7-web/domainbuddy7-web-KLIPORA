"""
KLIPORA Infrastructure — Upstash Redis Client

Thin wrapper around the Upstash Redis REST API, using the same config
conventions as `setup_redis.py`.

This module is the single place the rest of the codebase should use to talk to
Redis. It deliberately exposes a small, high-level surface that covers the
needs of the Command Center and agents:

- key/value access for job objects and control flags
- list operations for queues
- set membership for topic deduplication
"""

from __future__ import annotations

import json
import os
import typing as t
import urllib.error
import urllib.parse
import urllib.request

ScriptPath = os.path.dirname(os.path.abspath(__file__))
KliporaRoot = os.path.dirname(ScriptPath)


class RedisConfigError(RuntimeError):
    pass


def _config_from_env() -> t.Optional[dict]:
    """
    Build config from environment (for Railway/cloud deployment).
    Uses UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN.
    """
    url = os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("REDIS_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("REDIS_TOKEN")
    if url and token:
        return {"upstash_url": url.rstrip("/"), "upstash_token": token}
    return None


def _load_config() -> dict:
    """
    Load config from env (deployment) or from config.json (local).
    """
    env_config = _config_from_env()
    if env_config:
        return env_config

    config_paths = [
        os.path.join(KliporaRoot, "Infrastructure", "config.json"),
        os.path.join(ScriptPath, "config.json"),
        os.path.join(KliporaRoot, "config.json"),
    ]

    for path in config_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

    raise RedisConfigError(
        "Redis config not found. Set UPSTASH_REDIS_REST_URL and "
        "UPSTASH_REDIS_REST_TOKEN, or provide config.json in one of: "
        + ", ".join(config_paths)
    )


def _extract_upstash_credentials(config: dict) -> t.Tuple[str, str]:
    """
    Support both KLIPORA HQ and local config.json formats:

    - {\"upstash\": {\"redis_rest_url\": ..., \"redis_rest_token\": ...}}
    - {\"upstash_url\": ..., \"upstash_token\": ...}
    """
    if "upstash" in config:
        redis_url = config["upstash"].get("redis_rest_url", "").rstrip("/")
        redis_token = config["upstash"].get("redis_rest_token", "")
    elif "upstash_url" in config:
        redis_url = config["upstash_url"].rstrip("/")
        redis_token = config["upstash_token"]
    else:
        raise RedisConfigError("Upstash credentials not found in config")

    if not redis_url or not redis_token:
        raise RedisConfigError("Upstash URL and token must be non-empty")
    return redis_url, redis_token


class UpstashRedis:
    """
    Minimal Upstash Redis client specialised for KLIPORA.

    All methods return the `result` field from the Upstash response when
    available, or `None` on error.

    Optional `prefix`: all key-based operations use prefix + key (e.g. prefix
    "p2:" for Project 2 so keys are p2:script_queue, p2:job:xxx, etc.).
    """

    def __init__(
        self,
        redis_url: t.Optional[str] = None,
        redis_token: t.Optional[str] = None,
        config: t.Optional[dict] = None,
        prefix: str = "",
    ) -> None:
        if not (redis_url and redis_token):
            config = config or _load_config()
            redis_url, redis_token = _extract_upstash_credentials(config)

        self._redis_url = redis_url.rstrip("/")
        self._redis_token = redis_token
        self._prefix = prefix or ""

    # ── Low-level command helper ──────────────────────────────────────────

    def _key(self, key: str) -> str:
        """Return key with prefix if set (for key-based commands)."""
        if not self._prefix:
            return key
        return self._prefix + key

    def command(self, *parts: t.Union[str, int, float]) -> t.Any:
        """
        Execute a raw Upstash Redis command.
        Example: command("SET", "key", "value"). Key prefix is applied by get/set/rpush etc.
        """
        path_segments = [
            urllib.parse.quote(str(p), safe="") for p in parts
        ]
        url = f"{self._redis_url}/" + "/".join(path_segments)

        req = urllib.request.Request(
            url,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._redis_token}",
                "Content-Type": "application/json",
            },
        )

        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    payload = json.loads(resp.read())
                return payload.get("result", None)
            except urllib.error.HTTPError as e:
                _ = e.read()
                return None
            except (OSError, TimeoutError, urllib.error.URLError):
                if attempt == 0:
                    continue
                return None
            except Exception:
                return None
        return None

    # ── High-level primitives used across KLIPORA ────────────────────────

    # Strings / JSON blobs

    def get(self, key: str) -> t.Optional[str]:
        return self.command("GET", self._key(key))

    def set(self, key: str, value: str) -> bool:
        result = self.command("SET", self._key(key), value)
        return result == "OK"

    def delete(self, key: str) -> int:
        result = self.command("DEL", self._key(key))
        return int(result or 0)

    # Lists (queues)

    def lpush(self, key: str, *values: str) -> int:
        result = self.command("LPUSH", self._key(key), *values)
        return int(result or 0)

    def rpush(self, key: str, *values: str) -> int:
        result = self.command("RPUSH", self._key(key), *values)
        return int(result or 0)

    def lrange(self, key: str, start: int, end: int) -> t.List[str]:
        result = self.command("LRANGE", self._key(key), start, end)
        return list(result or [])

    def llen(self, key: str) -> int:
        result = self.command("LLEN", self._key(key))
        return int(result or 0)

    def lpop(self, key: str) -> t.Optional[str]:
        return self.command("LPOP", self._key(key))

    def rpop(self, key: str) -> t.Optional[str]:
        return self.command("RPOP", self._key(key))

    # Sets (topic deduplication, tags)

    def sadd(self, key: str, *members: str) -> int:
        result = self.command("SADD", self._key(key), *members)
        return int(result or 0)

    def sismember(self, key: str, member: str) -> bool:
        result = self.command("SISMEMBER", self._key(key), member)
        return bool(result)

    def smembers(self, key: str) -> t.List[str]:
        result = self.command("SMEMBERS", self._key(key))
        return list(result or [])

    # Convenience helpers for KLIPORA job objects

    def set_json(self, key: str, obj: t.Mapping[str, t.Any]) -> bool:
        return self.set(key, json.dumps(obj))

    def get_json(self, key: str) -> t.Optional[dict]:
        raw = self.get(key)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None


def get_redis_client(prefix: str = "") -> UpstashRedis:
    """
    Convenience factory. Use prefix="p2:" for Project 2 (same Upstash, keys p2:script_queue, etc.).
    """
    return UpstashRedis(prefix=prefix)


__all__ = [
    "UpstashRedis",
    "get_redis_client",
    "RedisConfigError",
]

