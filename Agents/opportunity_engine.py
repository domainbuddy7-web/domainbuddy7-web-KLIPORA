"""
KLIPORA Opportunity Scoring Engine

AI venture scout responsible for:
- structuring and scoring business opportunities
- persisting them in Redis
- emitting events into the central Event Bus

Discovery of raw market signals (Google Trends, Reddit, etc.) is expected to be
handled by specialised agents / tools (Market Radar). This module focuses on
normalising inputs, scoring, and managing opportunity lifecycle.
"""

from __future__ import annotations

import dataclasses
import typing as t

from Infrastructure.redis_client import UpstashRedis, get_redis_client
from Command_Center.event_bus import EventBus, get_event_bus


@dataclasses.dataclass
class Opportunity:
    id: str
    title: str
    category: str
    market_signal: str
    demand_score: float
    competition_score: float  # higher = more competition
    automation_potential: float  # 0–1
    estimated_cost: float
    estimated_revenue: float
    risk_level: str = "medium"
    score: float = 0.0
    status: str = "pending"  # pending | approved | rejected

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


class OpportunityEngine:
    """
    Scoring and lifecycle manager for business opportunities.
    """

    SCORE_THRESHOLD = 70.0

    def __init__(
        self,
        redis: t.Optional[UpstashRedis] = None,
        event_bus: t.Optional[EventBus] = None,
    ) -> None:
        self.redis = redis or get_redis_client()
        self.event_bus = event_bus or get_event_bus()

    # ── Core scoring logic ────────────────────────────────────────────────

    def compute_score(self, opp: Opportunity) -> float:
        """
        Compute final opportunity score based on:
        - demand
        - automation potential
        - profit potential
        - competition
        - cost
        """
        demand = max(0.0, min(10.0, opp.demand_score))

        # Higher competition should reduce the "low competition" benefit.
        # Map competition_score (0–10, higher=worse) to low_comp in 0–10.
        low_comp = max(0.0, 10.0 - max(0.0, min(10.0, opp.competition_score)))

        automation = max(0.0, min(1.0, opp.automation_potential))

        # Profit ratio: guard against division by zero.
        if opp.estimated_cost <= 0:
            profit_ratio = 0.0
        else:
            profit_ratio = opp.estimated_revenue / opp.estimated_cost

        # Normalise profit ratio into ~0–10 band using a simple squash.
        profit_score = max(0.0, min(10.0, profit_ratio))

        # Lower cost is better.
        if opp.estimated_cost <= 0:
            low_cost = 10.0
        else:
            low_cost = max(0.0, min(10.0, 10.0 / (1.0 + opp.estimated_cost / 100.0)))

        # Weighted sum into 0–100 scale.
        score = (
            demand * 0.30
            + automation * 10.0 * 0.25  # automation already 0–1
            + profit_score * 0.25
            + low_comp * 0.10
            + low_cost * 0.10
        )

        return round(score, 2)

    # ── Redis helpers ─────────────────────────────────────────────────────

    def _load_list(self, key: str) -> t.List[dict]:
        return self.redis.get_json(key) or []

    def _save_list(self, key: str, items: t.List[dict]) -> None:
        self.redis.set_json(key, items)

    # ── Public API ────────────────────────────────────────────────────────

    def register_opportunity(self, opp: Opportunity) -> Opportunity:
        """
        Compute score, persist as pending, and emit OPPORTUNITY_FOUND.
        To send the opportunity to Telegram for approval, the caller should
        POST to Mission Control /internal/notify-new-opportunity after registering.
        """
        opp.score = self.compute_score(opp)

        pending_key = "opportunities:pending"
        pending = self._load_list(pending_key)
        pending.append(opp.to_dict())
        self._save_list(pending_key, pending)

        self.event_bus.publish(
            "OPPORTUNITY_FOUND",
            {
                "id": opp.id,
                "title": opp.title,
                "score": opp.score,
                "category": opp.category,
                "risk_level": opp.risk_level,
            },
            category="opportunities",
        )

        return opp

    def approve_opportunity(self, opp_id: str) -> t.Optional[dict]:
        """
        Move opportunity from pending to approved and emit OPPORTUNITY_APPROVED.
        """
        pending_key = "opportunities:pending"
        approved_key = "opportunities:approved"
        history_key = "opportunities:history"

        pending = self._load_list(pending_key)
        approved = self._load_list(approved_key)
        history = self._load_list(history_key)

        opp: t.Optional[dict] = None
        remaining: t.List[dict] = []
        for item in pending:
            if item.get("id") == opp_id and opp is None:
                opp = item
            else:
                remaining.append(item)

        if not opp:
            return None

        opp["status"] = "approved"
        approved.append(opp)
        history.append(opp)

        self._save_list(pending_key, remaining)
        self._save_list(approved_key, approved)
        self._save_list(history_key, history)

        self.event_bus.publish(
            "OPPORTUNITY_APPROVED",
            {
                "id": opp["id"],
                "title": opp["title"],
                "score": opp.get("score"),
            },
            category="opportunities",
        )

        return opp

    def reject_opportunity(self, opp_id: str, reason: str) -> t.Optional[dict]:
        """
        Move opportunity from pending to rejected.
        """
        pending_key = "opportunities:pending"
        rejected_key = "opportunities:rejected"
        history_key = "opportunities:history"

        pending = self._load_list(pending_key)
        rejected = self._load_list(rejected_key)
        history = self._load_list(history_key)

        opp: t.Optional[dict] = None
        remaining: t.List[dict] = []
        for item in pending:
            if item.get("id") == opp_id and opp is None:
                opp = item
            else:
                remaining.append(item)

        if not opp:
            return None

        opp["status"] = "rejected"
        opp["reject_reason"] = reason
        rejected.append(opp)
        history.append(opp)

        self._save_list(pending_key, remaining)
        self._save_list(rejected_key, rejected)
        self._save_list(history_key, history)

        self.event_bus.publish(
            "OPPORTUNITY_REJECTED",
            {
                "id": opp["id"],
                "title": opp["title"],
                "reason": reason,
            },
            category="opportunities",
        )

        return opp

    def top_opportunities(self, min_score: float = 70.0, limit: int = 10) -> t.List[dict]:
        """
        Return pending opportunities above a score threshold, sorted by score.
        """
        pending = self._load_list("opportunities:pending")
        filtered = [
            o for o in pending if float(o.get("score", 0.0)) >= min_score
        ]
        filtered.sort(key=lambda o: float(o.get("score", 0.0)), reverse=True)
        return filtered[:limit]


def get_opportunity_engine() -> OpportunityEngine:
    return OpportunityEngine()


__all__ = ["Opportunity", "OpportunityEngine", "get_opportunity_engine"]

