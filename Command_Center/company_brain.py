"""
KLIPORA Command Center — Company Brain

Centralised interface for:
- topic memory and deduplication
- tracking successful / failed jobs
- exposing high-signal topics back to agents

Backed by Upstash Redis, with an optional human-readable layer in
`company_memory.md` (to be handled by higher-level reporting tools).
"""

from __future__ import annotations

import datetime as _dt
import typing as t

from Infrastructure.redis_client import UpstashRedis, get_redis_client


class CompanyBrain:
    """
    Memory and analytics facade over Redis.
    """

    def __init__(self, redis: t.Optional[UpstashRedis] = None) -> None:
        self.redis = redis or get_redis_client()

    # ── Topic deduplication ───────────────────────────────────────────────

    def was_topic_used_recently(self, topic: str) -> bool:
        """
        Check if a topic was used before.

        This method relies on the shared `used_topics` set also used by
        n8n (WF-GEN) and setup scripts.
        """
        return self.redis.sismember("used_topics", topic)

    def record_topic_used(self, topic: str) -> None:
        """
        Mark a topic as used.
        """
        self.redis.sadd("used_topics", topic)

    # ── Job outcome tracking ──────────────────────────────────────────────

    def _utc_now_iso(self) -> str:
        return _dt.datetime.utcnow().isoformat() + "Z"

    def record_success(self, topic: str, job_id: str, metrics: t.Optional[dict] = None) -> None:
        """
        Record a successful piece of content tied to a topic.
        """
        self.record_topic_used(topic)

        key = "company:topics:success_log"
        entry = {
            "topic": topic,
            "job_id": job_id,
            "timestamp": self._utc_now_iso(),
            "metrics": metrics or {},
        }
        self.redis.rpush(key, repr(entry))

    def record_failure(self, job_id: str, reason: str) -> None:
        """
        Record a failed job so that agents can analyse patterns later.
        """
        key = "company:jobs:failure_log"
        entry = {
            "job_id": job_id,
            "reason": reason,
            "timestamp": self._utc_now_iso(),
        }
        self.redis.rpush(key, repr(entry))

    # ── Topic ranking helpers ─────────────────────────────────────────────

    def get_best_topics(self, limit: int = 10) -> t.List[str]:
        """
        Return a list of historically successful topics.

        Implementation is intentionally simple: it reads the success log and
        returns the most recent distinct topics, newest first.
        """
        raw_entries = self.redis.lrange("company:topics:success_log", -limit * 5, -1)
        topics: t.List[str] = []
        seen: set = set()

        for raw in reversed(raw_entries):
            try:
                entry = eval(raw, {"__builtins__": {}})  # simple, non-executing context
            except Exception:
                continue
            topic = entry.get("topic")
            if topic and topic not in seen:
                seen.add(topic)
                topics.append(topic)
                if len(topics) >= limit:
                    break

        return topics


__all__ = ["CompanyBrain"]

