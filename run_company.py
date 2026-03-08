"""
KLIPORA — Company Orchestrator

Entry point that wires together:
- CEO, CTO, Operations, and Growth agents
- Command Center (WorkflowController, SystemGuardian)
- Event Bus and Redis

For now this script runs a *single* coordination cycle:
- CEO aligns daily production target with company config
- CTO runs one health check
- Operations runs one production cycle (may create video jobs)

In production you would call this script on a schedule (e.g. cron, n8n) or
convert it into a long-running service.
"""

from __future__ import annotations

from Infrastructure.redis_client import get_redis_client
from Command_Center.event_bus import get_event_bus
from Agents.ceo_agent import CEOAgent
from Agents.cto_agent import CTOAgent
from Agents.operations_agent import OperationsAgent


def main() -> None:
    redis = get_redis_client()
    event_bus = get_event_bus()

    ceo = CEOAgent(redis=redis, event_bus=event_bus)
    cto = CTOAgent(redis=redis, event_bus=event_bus)
    ops = OperationsAgent(redis=redis, event_bus=event_bus)

    # 1) Align daily production plan with company config.
    ceo.align_daily_production_limit()

    # 2) Run one infra health pass.
    health_summary = cto.run_health_check()

    # 3) Run one production scheduling cycle.
    production_result = ops.run_production_cycle()

    print("KLIPORA orchestration cycle completed.")
    print("Health summary:", health_summary)
    print("Production result:", production_result)


if __name__ == "__main__":
    main()

