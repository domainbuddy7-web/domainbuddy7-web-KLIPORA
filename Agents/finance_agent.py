"""
KLIPORA Finance Agent

Tracks API usage costs, cloud hosting, tool subscriptions, and advertising spend.
Enforces initial budget cap ($440). Redis keys: finance:capital_initial,
finance:spent_total, finance:remaining, finance:revenue:today, finance:revenue:month,
finance:spend:category:<name>.
"""

from __future__ import annotations

import typing as t

from Infrastructure.redis_client import UpstashRedis, get_redis_client


BUDGET_CAP = 440.0
CATEGORIES = ("api_usage", "cloud_hosting", "tools", "advertising")


def _to_float(value: t.Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


class FinanceAgent:
    """Tracks spend and revenue; enforces budget cap."""

    def __init__(self, redis: t.Optional[UpstashRedis] = None) -> None:
        self.redis = redis or get_redis_client()

    def get_capital_initial(self) -> float:
        return _to_float(self.redis.get("finance:capital_initial") or str(BUDGET_CAP))

    def get_spent_total(self) -> float:
        return _to_float(self.redis.get("finance:spent_total"))

    def get_remaining(self) -> float:
        rem = self.redis.get("finance:remaining")
        if rem is not None:
            return _to_float(rem)
        return self.get_capital_initial() - self.get_spent_total()

    def record_spend(self, category: str, amount: float) -> bool:
        """Add spend to a category and update spent_total and remaining. Returns False if over budget."""
        if category not in CATEGORIES or amount <= 0:
            return False
        key = f"finance:spend:category:{category}"
        try:
            current = _to_float(self.redis.get(key))
            new_cat = current + amount
            self.redis.set(key, str(round(new_cat, 2)))

            spent = self.get_spent_total() + amount
            cap = self.get_capital_initial()
            self.redis.set("finance:spent_total", str(round(spent, 2)))
            self.redis.set("finance:remaining", str(round(max(0.0, cap - spent), 2)))
            return spent <= cap
        except Exception:
            return False

    def record_revenue_today(self, amount: float) -> None:
        key = "finance:revenue:today"
        current = _to_float(self.redis.get(key))
        self.redis.set(key, str(round(current + amount, 2)))

    def record_revenue_month(self, amount: float) -> None:
        key = "finance:revenue:month"
        current = _to_float(self.redis.get(key))
        self.redis.set(key, str(round(current + amount, 2)))

    def ensure_initialized(self) -> None:
        """Ensure finance keys exist (idempotent)."""
        if self.redis.get("finance:capital_initial") is None:
            self.redis.set("finance:capital_initial", str(BUDGET_CAP))
        if self.redis.get("finance:spent_total") is None:
            self.redis.set("finance:spent_total", "0")
        if self.redis.get("finance:remaining") is None:
            self.redis.set("finance:remaining", str(BUDGET_CAP))
        for cat in CATEGORIES:
            k = f"finance:spend:category:{cat}"
            if self.redis.get(k) is None:
                self.redis.set(k, "0")
        for k in ("finance:revenue:today", "finance:revenue:month"):
            if self.redis.get(k) is None:
                self.redis.set(k, "0")


def get_finance_agent(redis: t.Optional[UpstashRedis] = None) -> FinanceAgent:
    return FinanceAgent(redis=redis)


__all__ = ["FinanceAgent", "get_finance_agent", "BUDGET_CAP"]
