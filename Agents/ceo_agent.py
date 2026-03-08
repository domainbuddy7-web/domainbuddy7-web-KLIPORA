"""
KLIPORA CEO Agent

High-level responsibilities:
- align daily production targets with company configuration and budget
- set top-level system knobs (e.g. videos per day)

This is intentionally simple for the first version. More advanced strategy
(experiments, multi-business portfolios) can be layered on later.
"""

from __future__ import annotations

import json
import os
import typing as t

from Infrastructure.redis_client import UpstashRedis, get_redis_client
from Command_Center.event_bus import EventBus, get_event_bus


class CEOAgent:
    """
    CEO Agent focuses on high-level production planning.
    """

    def __init__(
        self,
        redis: t.Optional[UpstashRedis] = None,
        event_bus: t.Optional[EventBus] = None,
        company_config_path: t.Optional[str] = None,
    ) -> None:
        self.redis = redis or get_redis_client()
        self.event_bus = event_bus or get_event_bus()
        self.company_config_path = company_config_path or self._default_config_path()
        self.company_config = self._load_company_config()

    def _default_config_path(self) -> str:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(script_dir)
        candidate_json = os.path.join(root, "company_config.json")
        candidate_txt = os.path.join(root, "company_config.json.txt")
        return candidate_json if os.path.exists(candidate_json) else candidate_txt

    def _load_company_config(self) -> dict:
        try:
            with open(self.company_config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    # ── Public behaviours ─────────────────────────────────────────────────

    def align_daily_production_limit(self) -> None:
        """
        Ensure `system:videos_per_day` in Redis matches company configuration.
        """
        target = int(self.company_config.get("video_limit_per_day", 2))
        self.redis.set("system:videos_per_day", str(target))

        self.event_bus.publish(
            "CEO_PLAN_UPDATED",
            {
                "videos_per_day": target,
                "source": "CEOAgent",
            },
            category="planning",
        )


def get_ceo_agent() -> CEOAgent:
    return CEOAgent()


__all__ = ["CEOAgent", "get_ceo_agent"]

