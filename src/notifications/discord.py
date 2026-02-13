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
        rationale: str = "",
    ):
        """Notify trade execution — the money shot."""
        is_long = direction in ("buy", "long")
        arrow = "🟢 LONG" if is_long else "🔴 SHORT"
        risk_pct = abs(price - stop_loss) / price * 100
        reward_pct = abs(take_profit - price) / price * 100
        position_value = qty * price

        embed = {
            "title": f"{arrow}  {symbol}",
            "color": 0x00CC66 if is_long else 0xCC3333,
            "description": rationale[:200] if rationale else None,
            "fields": [
                {"name": "Entry", "value": f"${price:.2f}", "inline": True},
                {"name": "Size", "value": f"{qty} × ${price:.2f} = **${position_value:,.0f}**", "inline": True},
                {"name": "Score", "value": f"**{score:.0f}**/100", "inline": True},
                {"name": "Stop", "value": f"${stop_loss:.2f} (-{risk_pct:.1f}%)", "inline": True},
                {"name": "Target", "value": f"${take_profit:.2f} (+{reward_pct:.1f}%)", "inline": True},
                {"name": "R:R", "value": f"1:{reward_pct/risk_pct:.1f}" if risk_pct > 0 else "—", "inline": True},
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }
        # Remove None description
        if not embed["description"]:
            del embed["description"]
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
        hold_time: str = "",
    ):
        """Notify position close with full context."""
        won = pnl > 0
        emoji = "💰" if pnl > 50 else "✅" if won else "🛑" if pnl < -100 else "❌"
        color = 0x00CC66 if won else 0xCC3333

        desc = f"**${entry_price:.2f}** → **${exit_price:.2f}**"
        if hold_time:
            desc += f"  •  held {hold_time}"

        embed = {
            "title": f"{emoji}  Closed {symbol}  —  ${pnl:+,.2f} ({pnl_pct:+.1f}%)",
            "color": color,
            "description": desc,
            "fields": [
                {"name": "Reason", "value": reason.replace("_", " ").title(), "inline": True},
                {"name": "Qty", "value": str(qty), "inline": True},
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._send(embeds=[embed])

    def position_trimmed(
        self,
        symbol: str,
        qty_sold: int,
        qty_remaining: int,
        price: float,
        pnl: float = 0,
        reason: str = "",
    ):
        """Notify partial close with useful context."""
        embed = {
            "title": f"✂️  Trimmed {symbol}  —  sold {qty_sold} @ ${price:.2f}",
            "color": 0xFFAA00,
            "description": f"Remaining: {qty_remaining} shares" + (f"  •  {reason.replace('_', ' ')}" if reason else ""),
            "timestamp": datetime.utcnow().isoformat(),
        }
        if pnl:
            embed["fields"] = [{"name": "Realized", "value": f"${pnl:+,.2f}", "inline": True}]
        self._send(embeds=[embed])

    def position_added(
        self,
        symbol: str,
        qty_added: int,
        price: float,
        total_qty: int,
    ):
        """Notify position add with context."""
        embed = {
            "title": f"➕  Added {symbol}  —  +{qty_added} @ ${price:.2f}",
            "color": 0x0099FF,
            "description": f"Total position: {total_qty} shares (${total_qty * price:,.0f})",
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._send(embeds=[embed])

    def daily_summary(self, stats: dict):
        """Send daily trading summary — the one notification that matters."""
        pnl = stats.get("daily_pnl", 0)
        pnl_pct = stats.get("daily_pnl_pct", 0)
        won = pnl >= 0
        emoji = "📈" if pnl > 100 else "📊" if won else "📉"
        color = 0x00CC66 if won else 0xCC3333

        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        total = stats.get("trades", 0)
        wr = stats.get("win_rate", 0)
        equity = stats.get("current_equity", 0)

        # Build a clean summary line
        summary = f"**${pnl:+,.2f}** ({pnl_pct:+.1f}%)"

        embed = {
            "title": f"{emoji}  End of Day  —  {stats.get('date', '')}",
            "color": color,
            "description": summary,
            "fields": [
                {"name": "Trades", "value": f"{total} ({wins}W / {losses}L)", "inline": True},
                {"name": "Win Rate", "value": f"{wr:.0f}%", "inline": True},
                {"name": "Equity", "value": f"${equity:,.0f}", "inline": True},
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }
        if stats.get("max_drawdown", 0) > 1:
            embed["fields"].append(
                {"name": "Max Drawdown", "value": f"{stats['max_drawdown']:.1f}%", "inline": True}
            )
        self._send(embeds=[embed])

    def alert(self, title: str, message: str, level: str = "info"):
        """Send general alert — only for important stuff."""
        colors = {
            "info": 0x0099FF,
            "warning": 0xFFCC00,
            "error": 0xFF0000,
            "success": 0x00CC66,
        }
        emojis = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "🚨",
            "success": "✅",
        }
        embed = {
            "title": f"{emojis.get(level, 'ℹ️')}  {title}",
            "description": message,
            "color": colors.get(level, 0x0099FF),
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._send(embeds=[embed])

    def daily_loss_limit_hit(self, loss_pct: float, equity: float):
        """Alert when daily loss limit is hit."""
        self.alert(
            "TRADING HALTED — Daily Loss Limit",
            f"Loss: **{loss_pct:.1%}**\nEquity: **${equity:,.0f}**\nBot will resume tomorrow.",
            level="error",
        )

    def signal_found(
        self,
        symbol: str,
        direction: str,
        score: float,
        rationale: str,
    ):
        """Only notify high-quality near-miss signals (scored 60+ but didn't trade).
        
        Skip low-score rejects — nobody needs to know about a 52-score signal.
        """
        if score < 60:
            return  # Don't spam with low-quality rejects
        
        arrow = "↗" if direction in ("buy", "long") else "↘"
        embed = {
            "title": f"🔍  {arrow} {symbol}  —  score {score:.0f} (skipped)",
            "color": 0x444466,
            "description": rationale[:150] if rationale else "No rationale",
            "timestamp": datetime.utcnow().isoformat(),
        }
        self._send(embeds=[embed])
