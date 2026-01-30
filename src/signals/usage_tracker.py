import logging
from datetime import datetime, date
from dataclasses import dataclass, field
from typing import Optional

from src.db import get_db

logger = logging.getLogger(__name__)

# Grok pricing (per 1M tokens) - sourced from models.dev Jan 2026
GROK_PRICING = {
    "grok-2-latest": {"input": 2.00, "output": 10.00},
    "grok-2": {"input": 2.00, "output": 10.00},
    "grok-3-mini": {"input": 0.30, "output": 0.50},
    "grok-3": {"input": 3.00, "output": 15.00},
    "grok-4": {"input": 3.00, "output": 15.00},
    "grok-4.1": {"input": 2.00, "output": 10.00},
    "grok-4-fast": {"input": 0.20, "output": 0.50},
    "grok-4-fast-reasoning": {"input": 0.20, "output": 0.50},
    "grok-4-fast-non-reasoning": {"input": 0.20, "output": 0.50},
    "grok-4-1-fast": {"input": 0.20, "output": 0.50},
    "grok-4-1-fast-reasoning": {"input": 0.20, "output": 0.50},
    "grok-4-1-fast-non-reasoning": {"input": 0.20, "output": 0.50},
    "grok-code-fast": {"input": 0.20, "output": 1.50},
    "grok-code-fast-1": {"input": 0.20, "output": 1.50},
    "default": {"input": 0.20, "output": 0.50},
}


@dataclass
class DailyUsage:
    date: str
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost: float = 0.0
    signals_generated: int = 0


@dataclass
class UsageTracker:
    total_cost: float = 0.0
    total_requests: int = 0

    def __post_init__(self):
        pass  # DB is always fresh, no load needed

    def record_request(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        signals_count: int = 0,
    ):
        """Record an API request."""
        pricing = GROK_PRICING.get(model, GROK_PRICING["default"])
        cost = (input_tokens * pricing["input"] / 1_000_000) + \
               (output_tokens * pricing["output"] / 1_000_000)

        today = str(date.today())
        try:
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO api_usage (date, requests, input_tokens, output_tokens,
                                             total_cost, signals_generated)
                       VALUES (%s, 1, %s, %s, %s, %s)
                       ON CONFLICT (date) DO UPDATE SET
                           requests = api_usage.requests + 1,
                           input_tokens = api_usage.input_tokens + EXCLUDED.input_tokens,
                           output_tokens = api_usage.output_tokens + EXCLUDED.output_tokens,
                           total_cost = api_usage.total_cost + EXCLUDED.total_cost,
                           signals_generated = api_usage.signals_generated + EXCLUDED.signals_generated""",
                    (today, input_tokens, output_tokens, cost, signals_count),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to record API usage: {e}")

        logger.info(
            f"API usage: {input_tokens} in, {output_tokens} out, ${cost:.4f}"
        )

    def reload(self):
        """No-op — DB is always fresh."""
        pass

    def get_today_summary(self) -> dict:
        """Get today's usage summary."""
        today = str(date.today())
        try:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT requests, input_tokens, output_tokens, total_cost, signals_generated "
                    "FROM api_usage WHERE date = %s",
                    (today,),
                ).fetchone()
                if row:
                    return {
                        "date": today,
                        "requests": row[0],
                        "input_tokens": row[1],
                        "output_tokens": row[2],
                        "cost": round(float(row[3]), 4),
                        "signals": row[4],
                    }
        except Exception as e:
            logger.warning(f"Failed to get today summary: {e}")
        return {
            "date": today,
            "requests": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost": 0.0,
            "signals": 0,
        }

    def get_total_summary(self) -> dict:
        """Get all-time usage summary."""
        try:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT COALESCE(SUM(requests), 0), COALESCE(SUM(total_cost), 0), COUNT(*) "
                    "FROM api_usage"
                ).fetchone()
                return {
                    "total_requests": row[0],
                    "total_cost": round(float(row[1]), 4),
                    "days_tracked": row[2],
                }
        except Exception as e:
            logger.warning(f"Failed to get total summary: {e}")
            return {"total_requests": 0, "total_cost": 0.0, "days_tracked": 0}


# Global tracker instance
_tracker: Optional[UsageTracker] = None


def get_tracker() -> UsageTracker:
    global _tracker
    if _tracker is None:
        _tracker = UsageTracker()
    return _tracker
