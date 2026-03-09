"""
KLIPORA Command Center — Workflow Controller

This module is the main bridge between Python and the n8n Automation Engine.
It encapsulates:

- creation of KLIPORA job objects in Redis
- triggering n8n workflows via webhooks or queues

Redis Job Contract (high level)
-------------------------------
Key: job:<id>
Value (JSON):
    {
        "id": "<id>",
        "topic": "...",
        "genre": "...",
        "script": null | "...",
        "scenes": [],
        "status": "pending" | "script_in_progress" | "script_ready"
                  | "video_in_progress" | "render_ready"
                  | "publishing" | "published" | "failed",
        "created_at": "<iso8601>",
        "updated_at": "<iso8601>",
        "meta": {...}
    }

Queues:
- script_queue  : contains job ids ready for WF-VIDEO
- render_queue  : contains job ids ready for WF-ASSEMBLE
- publish_queue : contains job ids ready for WF-PUBLISH
- failed_queue  : contains job ids that require manual attention
"""

from __future__ import annotations

import datetime as _dt
import typing as t
import uuid

from Infrastructure.api_clients import N8nClient, get_n8n_client
from Infrastructure.redis_client import UpstashRedis, get_redis_client


JobDict = t.Dict[str, t.Any]


class WorkflowTriggerError(RuntimeError):
    """Raised when n8n webhook cannot be reached (timeout, 5xx, connection)."""
    pass


class TopicRejectedError(RuntimeError):
    """Raised when WF-GEN returns 400 because the topic is already in used_topics."""
    def __init__(self, message: str, topic: str) -> None:
        super().__init__(message)
        self.message = message
        self.topic = topic


def _utc_now_iso() -> str:
    return _dt.datetime.utcnow().isoformat() + "Z"


class WorkflowController:
    """
    High-level API to orchestrate KLIPORA jobs and n8n workflows.
    """

    def __init__(
        self,
        redis: t.Optional[UpstashRedis] = None,
        n8n_client: t.Optional[N8nClient] = None,
        webhook_path_gen: t.Optional[str] = None,
    ) -> None:
        self.redis = redis or get_redis_client()
        self.n8n = n8n_client or get_n8n_client()
        self._webhook_path_gen = webhook_path_gen or "/webhook/wf-gen"

    # ── Job lifecycle helpers ─────────────────────────────────────────────

    def _job_key(self, job_id: str) -> str:
        return f"job:{job_id}"

    def create_job(
        self,
        topic: str,
        genre: t.Optional[str] = None,
        visual_style: t.Optional[str] = None,
        narration_style: t.Optional[str] = None,
        duration: t.Optional[str] = None,
        aspect_ratio: t.Optional[str] = None,
        meta: t.Optional[dict] = None,
        job_id: t.Optional[str] = None,
    ) -> JobDict:
        """
        Create and persist a new job object in Redis.
        """
        job_id = job_id or str(uuid.uuid4())
        now = _utc_now_iso()

        job: JobDict = {
            "id": job_id,
            "topic": topic,
            "genre": genre,
            "script": None,
            "scenes": [],
            "status": "pending",
            "created_at": now,
            "updated_at": now,
            "meta": {
                "visual_style": visual_style,
                "narration_style": narration_style,
                "duration": duration,
                "aspect_ratio": aspect_ratio,
                **(meta or {}),
            },
        }

        self.redis.set_json(self._job_key(job_id), job)
        return job

    def load_job(self, job_id: str) -> t.Optional[JobDict]:
        return self.redis.get_json(self._job_key(job_id))

    def update_job_status(self, job_id: str, status: str) -> None:
        job = self.load_job(job_id)
        if not job:
            return
        job["status"] = status
        job["updated_at"] = _utc_now_iso()
        self.redis.set_json(self._job_key(job_id), job)

    # ── n8n workflow triggers ─────────────────────────────────────────────

    def start_generation_job(
        self,
        topic: str,
        genre: t.Optional[str] = None,
        visual_style: t.Optional[str] = None,
        narration_style: t.Optional[str] = None,
        duration: t.Optional[str] = None,
        aspect_ratio: t.Optional[str] = None,
        chat_id: t.Optional[str] = None,
        job_id: t.Optional[str] = None,
        meta: t.Optional[dict] = None,
    ) -> JobDict:
        """
        Create a job and trigger WF-GEN via its webhook.

        The exact payload shape must match the WF-GEN webhook node. This
        implementation follows the existing WF-GEN contract used by
        `KliporaSetupAgent` and the Telegram WF-CTRL workflow.
        """
        job = self.create_job(
            topic=topic,
            genre=genre,
            visual_style=visual_style,
            narration_style=narration_style,
            duration=duration,
            aspect_ratio=aspect_ratio,
            meta=meta,
            job_id=job_id,
        )

        # WF-GEN Parse Job Params expects vstyle/nstyle (lowercase underscore); also send visual_style/narration_style for compatibility
        vstyle = (visual_style or "").lower().replace(" ", "_").strip() or None
        nstyle = (narration_style or "").lower().replace(" ", "_").strip() or None
        # aspect_ratio: workflow expects 9x16; API may send 9:16
        ar = (aspect_ratio or "").replace(":", "x").strip() or None
        payload = {
            "topic": topic,
            "genre": genre,
            "visual_style": visual_style,
            "narration_style": narration_style,
            "vstyle": vstyle or "dark_cinematic",
            "nstyle": nstyle or "dramatic",
            "duration": duration,
            "aspect_ratio": ar or "9x16",
            "job_id": job["id"],
            "chat_id": chat_id,
        }

        # n8n WF-GEN webhook. 400 = topic rejected (raise TopicRejectedError). 5xx/connection = retry then WorkflowTriggerError.
        last_err: t.Optional[Exception] = None
        for attempt in range(2):
            try:
                resp = self.n8n.trigger_webhook(self._webhook_path_gen, payload=payload)
                if resp.status_code == 400:
                    try:
                        body = resp.json() if resp.headers.get("content-type", "").strip().startswith("application/json") else {}
                    except Exception:
                        body = {}
                    if not isinstance(body, dict):
                        body = {}
                    msg = body.get("message") or "Topic already used."
                    topic_val = body.get("topic") or topic
                    raise TopicRejectedError(msg, topic_val)
                if resp.ok:
                    self.update_job_status(job["id"], "script_in_progress")
                    return job
                resp.raise_for_status()
            except TopicRejectedError:
                raise
            except Exception as e:
                last_err = e
                if attempt == 0:
                    continue
        # Both attempts failed (5xx or connection): mark job failed, push to failed_queue, raise for API to return 503
        try:
            job["status"] = "failed"
            job["updated_at"] = _utc_now_iso()
            job.setdefault("meta", {})["failure_reason"] = "n8n_webhook_unreachable"
            self.redis.set_json(self._job_key(job["id"]), job)
            self.redis.rpush("failed_queue", job["id"])
        except Exception:
            pass
        raise WorkflowTriggerError(f"n8n webhook unreachable: {last_err}") from last_err

    def trigger_trend_scan(self) -> None:
        """
        Trigger WF-TREND.

        Implementation assumes there is a webhook exposed at `/webhook/wf-trend`.
        If WF-TREND is purely schedule-based, this may be a no-op in production
        and can be removed or adapted.
        """
        try:
            resp = self.n8n.trigger_webhook("/webhook/wf-trend", payload={})
            if resp.ok:
                return
        except Exception:
            # Non-fatal; System Guardian can surface telemetry separately.
            return

    # ── Queue operations for downstream workflows ────────────────────────

    def enqueue_for_video(self, job_id: str) -> None:
        """
        Place a job onto `script_queue` so that WF-VIDEO can pick it up.
        """
        self.redis.rpush("script_queue", job_id)
        self.update_job_status(job_id, "script_ready")

    def enqueue_for_assemble(self, job_id: str) -> None:
        """
        Place a job onto `render_queue` so that WF-ASSEMBLE can pick it up.
        """
        self.redis.rpush("render_queue", job_id)
        self.update_job_status(job_id, "render_ready")

    def enqueue_for_publish(self, job_id: str) -> None:
        """
        Place a job onto `publish_queue` so that WF-PUBLISH can pick it up.
        """
        self.redis.rpush("publish_queue", job_id)
        self.update_job_status(job_id, "publishing")

    def mark_failed(self, job_id: str, reason: str) -> None:
        """
        Move a job into failed state and push it to `failed_queue`.
        """
        job = self.load_job(job_id) or {"id": job_id}
        job["status"] = "failed"
        job["updated_at"] = _utc_now_iso()
        job.setdefault("meta", {})
        job["meta"]["failure_reason"] = reason
        self.redis.set_json(self._job_key(job_id), job)
        self.redis.rpush("failed_queue", job_id)


__all__ = ["WorkflowController", "WorkflowTriggerError", "TopicRejectedError"]

