import logging
import requests
from typing import Optional
from datetime import datetime

from config import settings

logger = logging.getLogger(__name__)


class DiscordNotifier:
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or settings.DISCORD_WEBHOOK_URL
        self.enabled = bool(self.webhook_url)

    def _send(self, content: str = None, embeds: list = None) -> bool:
        if not self.enabled:
            logger.debug("Discord notifications disabled")
            return False

        try:
            payload = {}
            if content:
                payload["content"] = content
            if embeds:
                payload["embeds"] = embeds

            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Discord notification failed: {e}")
            return False

    def trade_executed(
        self,
        symbol: str,
        direction: str,
        qty: int,
        price: float,
        stop_loss: float,
        take_profit: float,
        score: float,
    ):
        """Notify trade execution."""
        color = 0x00FF00 if direction == "buy" else 0xFF0000  # green/red
        embed = {
            "title": f"🔔 Trade Executed: {symbol}",
            "color": color,
            "fields": [
                {"name": "Direction", "value": direction.upper(), "inline": True},
                {"name": "Quantity", "value": str(qty), "inline": True},
                {"name": "Price", "value": f"${price:.2f}", "inline": True},
                {"name": "Stop Loss", "value": f"${stop_loss:.2f}", "inline": True},
                {"name": "Take Profit", "value": f"${take_profit:.2f}", "inline": True},
                {"name": "Score", "value": f"{score:.1f}", "inline": True},
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._send(embeds=[embed])

    def position_closed(
        self,
        symbol: str,
        direction: str,
        qty: int,
        entry_price: float,
        exit_price: float,
        pnl: float,
        pnl_pct: float,
        reason: str,
    ):
        """Notify position close."""
        color = 0x00FF00 if pnl > 0 else 0xFF0000
        emoji = "✅" if pnl > 0 else "❌"
        embed = {
            "title": f"{emoji} Position Closed: {symbol}",
            "color": color,
            "fields": [
                {"name": "Direction", "value": direction.upper(), "inline": True},
                {"name": "Quantity", "value": str(qty), "inline": True},
                {"name": "Entry", "value": f"${entry_price:.2f}", "inline": True},
                {"name": "Exit", "value": f"${exit_price:.2f}", "inline": True},
                {"name": "P/L", "value": f"${pnl:.2f} ({pnl_pct:+.1f}%)", "inline": True},
                {"name": "Reason", "value": reason, "inline": True},
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._send(embeds=[embed])

    def daily_summary(self, stats: dict):
        """Send daily trading summary."""
        pnl = stats.get("daily_pnl", 0)
        color = 0x00FF00 if pnl >= 0 else 0xFF0000

        embed = {
            "title": "📊 Daily Trading Summary",
            "color": color,
            "fields": [
                {"name": "Date", "value": stats.get("date", ""), "inline": True},
                {"name": "P/L", "value": f"${pnl:.2f} ({stats.get('daily_pnl_pct', 0):+.2f}%)", "inline": True},
                {"name": "Trades", "value": str(stats.get("trades", 0)), "inline": True},
                {"name": "Win Rate", "value": f"{stats.get('win_rate', 0):.1f}%", "inline": True},
                {"name": "W/L", "value": f"{stats.get('wins', 0)}/{stats.get('losses', 0)}", "inline": True},
                {"name": "Max DD", "value": f"{stats.get('max_drawdown', 0):.2f}%", "inline": True},
                {"name": "Equity", "value": f"${stats.get('current_equity', 0):,.2f}", "inline": False},
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._send(embeds=[embed])

    def alert(self, title: str, message: str, level: str = "info"):
        """Send general alert."""
        colors = {
            "info": 0x0099FF,
            "warning": 0xFFCC00,
            "error": 0xFF0000,
            "success": 0x00FF00,
        }
        emojis = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "🚨",
            "success": "✅",
        }
        embed = {
            "title": f"{emojis.get(level, 'ℹ️')} {title}",
            "description": message,
            "color": colors.get(level, 0x0099FF),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._send(embeds=[embed])

    def daily_loss_limit_hit(self, loss_pct: float, equity: float):
        """Alert when daily loss limit is hit."""
        self.alert(
            "Daily Loss Limit Hit",
            f"Trading halted. Loss: {loss_pct:.1%}\nCurrent equity: ${equity:,.2f}",
            level="error",
        )

    def signal_found(
        self,
        symbol: str,
        direction: str,
        score: float,
        rationale: str,
    ):
        """Notify new signal found (for monitoring)."""
        color = 0x00AAFF
        embed = {
            "title": f"🔍 Signal Found: {symbol}",
            "color": color,
            "fields": [
                {"name": "Direction", "value": direction.upper(), "inline": True},
                {"name": "Score", "value": f"{score:.1f}", "inline": True},
                {"name": "Rationale", "value": rationale[:200] if rationale else "N/A", "inline": False},
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._send(embeds=[embed])
