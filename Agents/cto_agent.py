"""
KLIPORA CTO Agent

Responsibilities:
- run system health checks through SystemGuardian and PipelineMonitor
- surface issues via the Event Bus (for dashboard and notifications)
"""

from __future__ import annotations

import typing as t

from Infrastructure.redis_client import UpstashRedis, get_redis_client
from Command_Center.system_guardian import SystemGuardian
from Command_Center.event_bus import EventBus, get_event_bus


class CTOAgent:
    """
    CTO Agent uses SystemGuardian to keep an eye on infra health.
    """

    def __init__(
        self,
        redis: t.Optional[UpstashRedis] = None,
        event_bus: t.Optional[EventBus] = None,
        guardian: t.Optional[SystemGuardian] = None,
    ) -> None:
        self.redis = redis or get_redis_client()
        self.event_bus = event_bus or get_event_bus()
        self.guardian = guardian or SystemGuardian(redis=self.redis)

    def run_health_check(self) -> dict:
        """
        Run a single health-check pass and emit a summary event.
        """
        summary = self.guardian.apply_policies()

        # Emit a condensed event for dashboards/notifications.
        self.event_bus.publish(
            "SYSTEM_HEALTH_CHECK",
            {
                "status": "OK" if not summary.get("actions") else "ACTIONS_TAKEN",
                "queues": summary.get("queues"),
                "flags": summary.get("flags"),
                "actions": summary.get("actions"),
            },
            category="health",
        )
        return summary


def get_cto_agent() -> CTOAgent:
    return CTOAgent()


__all__ = ["CTOAgent", "get_cto_agent"]

