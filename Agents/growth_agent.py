"""
KLIPORA Growth Agent

Responsibilities:
- select high-potential topics for content production
- combine trend signals with company memory

This agent does not generate content itself; it only decides *what* to make.
"""

from __future__ import annotations

import datetime as _dt
import typing as t

from Infrastructure.redis_client import UpstashRedis, get_redis_client
from Command_Center.company_brain import CompanyBrain
from Command_Center.event_bus import EventBus, get_event_bus


class GrowthAgent:
    """
    Growth Agent focuses on topic selection using trend signals + memory.
    """

    def __init__(
        self,
        redis: t.Optional[UpstashRedis] = None,
        brain: t.Optional[CompanyBrain] = None,
        event_bus: t.Optional[EventBus] = None,
    ) -> None:
        self.redis = redis or get_redis_client()
        self.brain = brain or CompanyBrain(redis=self.redis)
        self.event_bus = event_bus or get_event_bus()

    def _today_key(self) -> str:
        today = _dt.datetime.utcnow().strftime("%Y-%m-%d")
        return f"trend:topics:{today}"

    def _load_trend_topics(self) -> t.List[str]:
        """
        Read topics discovered by WF-TREND or other radar tools.
        """
        topics = self.redis.get_json(self._today_key()) or []
        return [t for t in topics if isinstance(t, str)]

    def select_topics(self, max_count: int) -> t.List[str]:
        """
        Choose up to `max_count` topics, preferring:
        - today's trend topics not used recently
        - fallback to historically successful topics
        """
        selected: t.List[str] = []

        # 1) Use today's trend topics first
        for topic in self._load_trend_topics():
            if len(selected) >= max_count:
                break
            if not self.brain.was_topic_used_recently(topic):
                selected.append(topic)

        # 2) Fallback to best historical topics if needed
        if len(selected) < max_count:
            for topic in self.brain.get_best_topics(limit=max_count * 2):
                if len(selected) >= max_count:
                    break
                if topic not in selected:
                    selected.append(topic)

        if selected:
            self.event_bus.publish(
                "TOPICS_SELECTED",
                {"topics": selected, "max_count": max_count},
                category="growth",
            )

        return selected


def get_growth_agent() -> GrowthAgent:
    return GrowthAgent()


__all__ = ["GrowthAgent", "get_growth_agent"]

