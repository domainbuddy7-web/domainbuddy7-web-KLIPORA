"""
KLIPORA Command Center — System Guardian

Continuous monitoring and self-healing loop for:
- Redis queues and control flags
- n8n execution failures

Policy goals:
- Detect stalled or failing pipelines early.
- Apply back-pressure (pause system, reduce throughput).
- Surface critical issues to higher-level agents (CTO, CEO).
"""

from __future__ import annotations

import datetime as _dt
import time
import typing as t

from Infrastructure.redis_client import UpstashRedis, get_redis_client
from Command_Center.pipeline_monitor import PipelineMonitor
from Command_Center.workflow_controller import WorkflowController


class SystemGuardian:
    """
    Monitoring and policy engine.
    """

    # Thresholds and timing (can be tuned by CTO Agent)
    QUEUE_STALL_MINUTES = 20
    MAX_FAILED_EXECUTIONS_WINDOW = 20  # soft threshold
    LOOP_SLEEP_SECONDS = 60

    def __init__(
        self,
        redis: t.Optional[UpstashRedis] = None,
        monitor: t.Optional[PipelineMonitor] = None,
        controller: t.Optional[WorkflowController] = None,
    ) -> None:
        self.redis = redis or get_redis_client()
        self.monitor = monitor or PipelineMonitor()
        self.controller = controller or WorkflowController(redis=self.redis)

    # ── Core checks ───────────────────────────────────────────────────────

    def _utc_now(self) -> _dt.datetime:
        return _dt.datetime.utcnow()

    def check_queues(self) -> dict:
        """
        Return a snapshot of key queue lengths.
        """
        queues = ["script_queue", "render_queue", "publish_queue", "failed_queue"]
        return {name: self.redis.llen(name) for name in queues}

    def _parse_iso(self, value: str) -> t.Optional[_dt.datetime]:
        try:
            # Accept both with and without trailing Z.
            if value.endswith("Z"):
                value = value[:-1]
            return _dt.datetime.fromisoformat(value)
        except Exception:
            return None

    def detect_stalled_jobs(self) -> t.List[str]:
        """
        Identify jobs that have been stuck in queues longer than the
        configured stall threshold.

        Returns a list of job ids considered stalled.
        """
        stalled: t.List[str] = []
        now = self._utc_now()
        max_age = _dt.timedelta(minutes=self.QUEUE_STALL_MINUTES)

        for queue in ("script_queue", "render_queue", "publish_queue"):
            job_ids = self.redis.lrange(queue, 0, -1)
            for job_id in job_ids:
                job = self.controller.load_job(job_id)
                if not job:
                    continue
                ts = job.get("updated_at") or job.get("created_at")
                dt = self._parse_iso(ts) if isinstance(ts, str) else None
                if dt and (now - dt) > max_age:
                    stalled.append(job_id)

        return stalled

    def check_system_flags(self) -> dict:
        """
        Read high-level system flags from Redis.
        """
        today = self._utc_now().strftime("%Y-%m-%d")
        paused = self.redis.get("system:paused")
        videos_per_day = self.redis.get("system:videos_per_day")
        max_concurrent = self.redis.get("system:max_concurrent_jobs")
        daily_count = self.redis.get(f"system:daily_count:{today}")

        return {
            "paused": bool(paused),
            "videos_per_day": int(videos_per_day or 0),
            "max_concurrent_jobs": int(max_concurrent or 0),
            "daily_count": int(daily_count or 0),
            "date": today,
        }

    def check_n8n_failures(self) -> dict:
        """
        Summarise recent n8n failures.
        """
        return self.monitor.summarize_failures(limit=50)

    # ── Policy application ────────────────────────────────────────────────

    def apply_policies(self) -> dict:
        """
        Run all checks and apply safety/back-pressure policies.

        Returns a summary dict that can be logged or reported.
        """
        queues = self.check_queues()
        flags = self.check_system_flags()
        failure_summary = self.check_n8n_failures()
        stalled_jobs = self.detect_stalled_jobs()

        actions: t.List[str] = []

        # Too many recent failures across workflows
        total_failures = sum(failure_summary.values())
        if total_failures > self.MAX_FAILED_EXECUTIONS_WINDOW:
            # Soft pause: set system:paused
            self.redis.set("system:paused", "1")
            actions.append(
                f"paused_system_due_to_failures({total_failures} recent failures)"
            )

        # Stalled jobs: mark failed and move to failed_queue
        for job_id in stalled_jobs:
            self.controller.mark_failed(
                job_id, reason="stalled_in_queue_too_long"
            )
            actions.append(f"marked_failed:{job_id}")

        summary = {
            "queues": queues,
            "flags": flags,
            "n8n_failures": failure_summary,
            "stalled_jobs": stalled_jobs,
            "actions": actions,
            "timestamp": self._utc_now().isoformat() + "Z",
        }

        return summary

    # ── Main loop ─────────────────────────────────────────────────────────

    def run_forever(self) -> None:
        """
        Simple blocking loop. In production this would typically be run inside
        a supervisor or container.
        """
        while True:
            summary = self.apply_policies()
            # For now, print summary; higher layers (CTO Agent) can hook into
            # this and forward to Telegram or reports.
            print(f"[SystemGuardian] {summary}")
            time.sleep(self.LOOP_SLEEP_SECONDS)


if __name__ == "__main__":
    guardian = SystemGuardian()
    guardian.run_forever()

