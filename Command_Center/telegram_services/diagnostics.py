"""
Connectivity and system diagnostics: structured results for Mission Control, n8n, Redis.

Returns dicts only; no Telegram types. The Telegram UI formats these for display.
See docs/TELEGRAM_DASHBOARD_ARCHITECTURE_DESIGN.md.
"""

from __future__ import annotations

import typing as t

# api_get: (path: str) -> dict (with optional _error, _code keys on failure)
ApiGetFn = t.Callable[[str], dict]
# Redis-like: optional .get(key) and exception on failure
RedisLike = t.Any


def check_mission_control_connectivity(
    api_get: ApiGetFn,
    base_url: str,
) -> dict:
    """
    Verify MISSION_CONTROL_URL and Mission Control API /health.

    Returns:
        {
            "url": str (or "" if not set),
            "reachable": bool,
            "message": str (short human-readable status),
            "config_ok": bool | None (from /health when reachable),
        }
    """
    url = (base_url or "").strip()
    if not url:
        return {
            "url": "",
            "reachable": False,
            "message": "MISSION_CONTROL_URL is not set. Add it in KEY=value.env and restart the bot.",
            "config_ok": None,
        }
    try:
        health = api_get("/health")
    except Exception as exc:
        # Include exception text so diagnostics show the real failure reason.
        return {
            "url": url,
            "reachable": False,
            "message": f"Mission Control API offline. /health error: {exc!s}. Check Railway deployment or MISSION_CONTROL_URL.",
            "config_ok": None,
        }
    if not health:
        return {
            "url": url,
            "reachable": False,
            "message": "Mission Control API offline. /health returned empty response. Check Railway deployment or MISSION_CONTROL_URL.",
            "config_ok": None,
        }
    config_ok = health.get("config_ok")
    if config_ok is not True:
        return {
            "url": url,
            "reachable": True,
            "message": "API reachable but config missing (Redis/n8n env on Railway).",
            "config_ok": config_ok,
        }
    return {
        "url": url,
        "reachable": True,
        "message": "API /health OK",
        "config_ok": True,
    }


def check_n8n_connectivity(api_get: ApiGetFn) -> dict:
    """
    Verify n8n workflow fetch via Mission Control /automation.

    Mission Control uses N8N_API_URL and N8N_API_KEY; this checks whether
    the /automation endpoint returns workflows (n8n reachable from MC).

    Returns:
        {
            "reachable": bool,
            "message": str,
            "workflow_count": int | None (when reachable),
        }
    """
    a = api_get("/automation")
    if not a or a.get("_error"):
        err = a.get("_error", "request failed") if a else "no response"
        return {
            "reachable": False,
            "message": f"Cannot fetch n8n workflows ({err}). Check N8N_API_URL and N8N_API_KEY on Mission Control (Railway).",
            "workflow_count": None,
        }
    wfs = a.get("workflows", []) if isinstance(a, dict) else []
    if not wfs:
        return {
            "reachable": False,
            "message": "Cannot fetch n8n workflows. Check N8N_API_URL and N8N_API_KEY (Mission Control / Railway).",
            "workflow_count": 0,
        }
    return {
        "reachable": True,
        "message": f"n8n OK ({len(wfs)} workflow(s)).",
        "workflow_count": len(wfs),
    }


def check_redis_connectivity(redis: RedisLike) -> dict:
    """
    Ping Redis (or equivalent: one read). Redis may be None if not configured.

    Returns:
        {
            "reachable": bool,
            "message": str,
        }
    """
    if redis is None:
        return {
            "reachable": False,
            "message": "Redis not configured (no client).",
        }
    try:
        redis.get("system:paused")
        return {"reachable": True, "message": "Redis OK"}
    except Exception as e:
        return {
            "reachable": False,
            "message": f"Redis unreachable: {e!s}",
        }


def run_system_diagnostics(
    api_get: ApiGetFn,
    base_url: str,
    redis: RedisLike,
) -> dict:
    """
    Run mission_control, n8n, and redis checks and return a summary dict.

    Returns:
        {
            "mission_control": {...},  # check_mission_control_connectivity result
            "n8n": {...},              # check_n8n_connectivity result
            "redis": {...},            # check_redis_connectivity result
        }
    """
    return {
        "mission_control": check_mission_control_connectivity(api_get, base_url),
        "n8n": check_n8n_connectivity(api_get),
        "redis": check_redis_connectivity(redis),
    }
