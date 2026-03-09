"""
KLIPORA Command Center — Event Bus

Central coordination layer for:
- system events
- task orchestration signals
- agent-to-agent communication
- dashboard and notification timelines

All components should prefer publishing structured events here instead of
calling each other directly.
"""

from __future__ import annotations

import datetime as _dt
import json
import typing as t

from Infrastructure.redis_client import UpstashRedis, get_redis_client


EventPayload = t.Dict[str, t.Any]


class EventBus:
    """
    Simple Redis-backed event bus.

    Events are appended to:
    - events:stream       (global chronological log)
    - events:<category>   (optional sub-streams, e.g. events:revenue)
    """

    def __init__(self, redis: t.Optional[UpstashRedis] = None) -> None:
        self.redis = redis or get_redis_client()

    def _iso_now(self) -> str:
        return _dt.datetime.utcnow().isoformat() + "Z"

    def publish(
        self,
        event_type: str,
        data: t.Optional[EventPayload] = None,
        category: t.Optional[str] = None,
    ) -> None:
        """
        Publish a structured event into the global event stream and optional
        category-specific stream. No-op on Redis failure to keep callers stable.
        """
        try:
            event = {
                "type": event_type,
                "timestamp": self._iso_now(),
                "data": data or {},
            }
            payload = json.dumps(event)
            self.redis.rpush("events:stream", payload)
            if category:
                self.redis.rpush(f"events:{category}", payload)
        except Exception:
            pass

    def get_events(
        self,
        limit: int = 100,
        event_type: t.Optional[str] = None,
    ) -> t.List[EventPayload]:
        """
        Return the most recent events, optionally filtered by type.
        """
        raw_events = self.redis.lrange("events:stream", -limit, -1)
        out: t.List[EventPayload] = []

        for raw in raw_events:
            try:
                evt = json.loads(raw)
            except Exception:
                continue

            if event_type and evt.get("type") != event_type:
                continue

            out.append(evt)

        # Most recent events last in the list (natural order)
        return out


def get_event_bus() -> EventBus:
    return EventBus()


__all__ = ["EventBus", "get_event_bus"]

