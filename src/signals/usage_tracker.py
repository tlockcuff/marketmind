import json
import logging
from datetime import datetime, date
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger(__name__)

USAGE_FILE = Path(__file__).parent.parent.parent / "logs" / "api_usage.json"

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
    daily: dict = field(default_factory=dict)
    total_cost: float = 0.0
    total_requests: int = 0

    def __post_init__(self):
        self._load()

    def _load(self):
        """Load usage data from file."""
        if USAGE_FILE.exists():
            try:
                data = json.loads(USAGE_FILE.read_text())
                self.daily = data.get("daily", {})
                self.total_cost = data.get("total_cost", 0.0)
                self.total_requests = data.get("total_requests", 0)
            except Exception as e:
                logger.warning(f"Failed to load usage data: {e}")

    def _save(self):
        """Save usage data to file."""
        try:
            USAGE_FILE.parent.mkdir(exist_ok=True)
            data = {
                "daily": self.daily,
                "total_cost": self.total_cost,
                "total_requests": self.total_requests,
                "last_updated": datetime.now().isoformat(),
            }
            USAGE_FILE.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save usage data: {e}")

    def _get_today(self) -> DailyUsage:
        """Get or create today's usage record."""
        today = str(date.today())
        if today not in self.daily:
            self.daily[today] = asdict(DailyUsage(date=today))
        return self.daily[today]

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

        today = self._get_today()
        today["requests"] += 1
        today["input_tokens"] += input_tokens
        today["output_tokens"] += output_tokens
        today["total_cost"] += cost
        today["signals_generated"] += signals_count

        self.total_cost += cost
        self.total_requests += 1

        logger.info(
            f"API usage: {input_tokens} in, {output_tokens} out, "
            f"${cost:.4f} (today: ${today['total_cost']:.4f}, total: ${self.total_cost:.4f})"
        )

        self._save()

    def reload(self):
        """Reload usage data from disk (for dashboard cross-process reads)."""
        self._load()

    def get_today_summary(self) -> dict:
        """Get today's usage summary."""
        self.reload()
        today = self._get_today()
        return {
            "date": today["date"],
            "requests": today["requests"],
            "input_tokens": today["input_tokens"],
            "output_tokens": today["output_tokens"],
            "cost": round(today["total_cost"], 4),
            "signals": today["signals_generated"],
        }

    def get_total_summary(self) -> dict:
        """Get all-time usage summary."""
        self.reload()
        return {
            "total_requests": self.total_requests,
            "total_cost": round(self.total_cost, 4),
            "days_tracked": len(self.daily),
        }


# Global tracker instance
_tracker: Optional[UsageTracker] = None


def get_tracker() -> UsageTracker:
    global _tracker
    if _tracker is None:
        _tracker = UsageTracker()
    return _tracker
