"""
KLIPORA Operations Agent

Responsibilities:
- translate daily production targets into concrete video jobs
- manage job scheduling via WorkflowController and Redis queues

This first version runs a single, stateless production cycle. In practice you
would call it from a scheduler (cron, n8n, or an external orchestrator).
"""

from __future__ import annotations

import typing as t

from Infrastructure.redis_client import UpstashRedis, get_redis_client
from Command_Center.system_guardian import SystemGuardian
from Command_Center.workflow_controller import WorkflowController
from Command_Center.event_bus import EventBus, get_event_bus
from Agents.growth_agent import GrowthAgent


class OperationsAgent:
    """
    Operations Agent manages the production queue.
    """

    def __init__(
        self,
        redis: t.Optional[UpstashRedis] = None,
        guardian: t.Optional[SystemGuardian] = None,
        controller: t.Optional[WorkflowController] = None,
        growth_agent: t.Optional[GrowthAgent] = None,
        event_bus: t.Optional[EventBus] = None,
    ) -> None:
        self.redis = redis or get_redis_client()
        self.guardian = guardian or SystemGuardian(redis=self.redis)
        self.controller = controller or WorkflowController(redis=self.redis)
        self.growth_agent = growth_agent or GrowthAgent(redis=self.redis)
        self.event_bus = event_bus or get_event_bus()

    def run_production_cycle(self) -> dict:
        """
        Run a single production decision cycle:
        - check system flags
        - determine remaining capacity for today
        - select topics
        - create generation jobs via WorkflowController
        """
        flags = self.guardian.check_system_flags()

        if flags.get("paused"):
            self.event_bus.publish(
                "PRODUCTION_SKIPPED",
                {"reason": "system_paused"},
                category="production",
            )
            return {"status": "skipped", "reason": "paused"}

        target_per_day = int(flags.get("videos_per_day", 0))
        produced_today = int(flags.get("daily_count", 0))
        remaining_capacity = max(0, target_per_day - produced_today)

        if remaining_capacity <= 0:
            self.event_bus.publish(
                "PRODUCTION_SKIPPED",
                {"reason": "capacity_reached"},
                category="production",
            )
            return {
                "status": "skipped",
                "reason": "capacity_reached",
                "target_per_day": target_per_day,
                "produced_today": produced_today,
            }

        topics = self.growth_agent.select_topics(remaining_capacity)
        jobs = []

        for topic in topics:
            job = self.controller.start_generation_job(topic=topic)
            jobs.append(job)
            self.event_bus.publish(
                "VIDEO_JOB_CREATED",
                {"job_id": job["id"], "topic": topic, "source": "OperationsAgent"},
                category="videos",
            )

        return {
            "status": "ok",
            "created_jobs": [j["id"] for j in jobs],
            "topics": topics,
        }


def get_operations_agent() -> OperationsAgent:
    return OperationsAgent()


__all__ = ["OperationsAgent", "get_operations_agent"]

