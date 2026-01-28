#!/usr/bin/env python3
"""
Live TUI Dashboard for Day Trading Bot
"""

import os
import sys
import time
import select
import subprocess
import termios
import threading
import tty
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from collections import deque

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from src.trading.alpaca_client import AlpacaClient
from src.trading.trade_history import get_trade_history
from src.signals.usage_tracker import get_tracker
from src.scheduler.trading_hours import format_market_status, now_et, MARKET_OPEN, MARKET_CLOSE, EARLY_CLOSE
from config.holidays import EARLY_CLOSE_DAYS
from src.trading.options.position_mgr import OptionsPositionManager, _get_positions_file

console = Console()

PROJECT_ROOT = Path(__file__).parent.parent
BOT_SCRIPT = PROJECT_ROOT / "src" / "main.py"


def get_log_file() -> Path:
    """Get mode-specific log file."""
    mode = os.environ.get("TRADING_MODE", "paper").lower()
    prefix = "live" if mode == "live" else "paper"
    return PROJECT_ROOT / "logs" / f"{prefix}_trading.log"


class KeyReader:
    """Non-blocking keyboard reader using raw terminal mode."""

    def __init__(self):
        self.keys = deque(maxlen=16)
        self._stop = threading.Event()
        self._old_settings = None
        self._thread = None

    def start(self):
        self._old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._old_settings:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self._old_settings)

    def get_key(self):
        """Pop next key event. Returns None if empty."""
        try:
            return self.keys.popleft()
        except IndexError:
            return None

    def _read_loop(self):
        while not self._stop.is_set():
            if select.select([sys.stdin], [], [], 0.1)[0]:
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    # Escape sequence — read rest if available
                    seq = ""
                    while select.select([sys.stdin], [], [], 0.05)[0]:
                        seq += sys.stdin.read(1)
                    if seq == "[A":
                        self.keys.append("up")
                    elif seq == "[B":
                        self.keys.append("down")
                    elif seq == "[5~":
                        self.keys.append("pgup")
                    elif seq == "[6~":
                        self.keys.append("pgdn")
                    elif seq == "[H" or seq == "[1~":
                        self.keys.append("home")
                    elif seq == "[F" or seq == "[4~":
                        self.keys.append("end")
                    elif seq == "":
                        self.keys.append("esc")
                elif ch == "\x0f":  # Ctrl+O
                    self.keys.append("ctrl-o")
                elif ch == "q":
                    self.keys.append("quit")


class BotManager:
    def __init__(self):
        self.process = None
        self.start_time = None

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self):
        if self.is_running():
            return
        env = os.environ.copy()
        env["PYTHONPATH"] = str(PROJECT_ROOT)
        env["PYTHONUNBUFFERED"] = "1"

        # Use --live if TRADING_MODE is live
        args = [sys.executable, "-u", str(BOT_SCRIPT)]
        if env.get("TRADING_MODE") == "live":
            args.append("--live")
            env["SKIP_LIVE_CONFIRM"] = "1"  # Already confirmed in watch.sh
        else:
            args.append("--paper")

        self.process = subprocess.Popen(
            args,
            cwd=str(PROJECT_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.start_time = datetime.now()

    def stop(self):
        if self.process and self.is_running():
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None

    def get_status(self) -> str:
        if not self.is_running():
            return "[red]STOPPED[/]"
        uptime = datetime.now() - self.start_time
        mins = int(uptime.total_seconds() // 60)
        secs = int(uptime.total_seconds() % 60)
        return f"[green]RUNNING[/] [dim]{mins}:{secs:02d}[/]"


def _time_until(now: datetime, target_time) -> str:
    """Format countdown to a target time today."""
    target = now.replace(hour=target_time.hour, minute=target_time.minute, second=0, microsecond=0)
    diff = (target - now).total_seconds()
    if diff < 0:
        return ""
    h = int(diff // 3600)
    m = int((diff % 3600) // 60)
    if h > 0:
        return f"{h}h{m:02d}m"
    return f"{m}m"


def _get_market_session() -> str:
    """Return current market session label + style."""
    now = now_et()
    t = now.time()
    if now.weekday() >= 5:
        return "[dim]Weekend[/]"
    close = EARLY_CLOSE if now.date() in EARLY_CLOSE_DAYS else MARKET_CLOSE
    pre_market = datetime.strptime("04:00", "%H:%M").time()
    after_close = datetime.strptime("20:00", "%H:%M").time()

    if MARKET_OPEN <= t < close:
        countdown = _time_until(now, close)
        return f"[green bold]Market Open[/] [dim]closes {countdown}[/]"
    elif pre_market <= t < MARKET_OPEN:
        countdown = _time_until(now, MARKET_OPEN)
        return f"[yellow]Pre-Market[/] [dim]opens {countdown}[/]"
    elif close <= t < after_close:
        return "[yellow]After Hours[/]"
    else:
        return "[dim]Overnight[/]"


class Dashboard:
    def __init__(self, bot_manager: BotManager):
        self.alpaca = AlpacaClient()
        self.log_lines = deque(maxlen=200)
        self.last_log_pos = 0
        self.bot = bot_manager
        self.last_cycle_time: datetime = None
        self.fullscreen_logs = False
        self.log_scroll_offset = 0  # 0 = pinned to bottom (newest)

    def get_terminal_size(self):
        try:
            return os.get_terminal_size()
        except:
            return (120, 40)

    def make_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body", ratio=1),
            Layout(name="footer", size=1),
        )
        layout["body"].split_row(
            Layout(name="main", ratio=3),
            Layout(name="sidebar", ratio=1, minimum_size=35),
        )
        layout["main"].split_column(
            Layout(name="positions", ratio=1),
            Layout(name="options", ratio=1),
            Layout(name="orders", ratio=1),
            Layout(name="logs", ratio=1),
        )
        layout["sidebar"].split_column(
            Layout(name="account", size=16),
            Layout(name="stats", size=10),
            Layout(name="config", size=16),
            Layout(name="api", ratio=1),
        )
        return layout

    def get_header(self) -> Panel:
        now = now_et()
        market = format_market_status()
        session = _get_market_session()
        bot = self.bot.get_status()
        mode = "[green]PAPER[/]" if settings.is_paper_mode() else "[red bold]LIVE[/]"

        # Detect last cycle from logs to estimate next run
        self._update_last_cycle_time()
        next_run = ""
        if self.last_cycle_time:
            from datetime import timedelta
            next_at = self.last_cycle_time + timedelta(minutes=settings.SCAN_INTERVAL_MINUTES)
            remaining = (next_at - datetime.now()).total_seconds()
            if remaining > 0:
                m = int(remaining // 60)
                s = int(remaining % 60)
                next_run = f" | Next run [bold]{m}:{s:02d}[/]"
            else:
                next_run = " | Next run [bold]now[/]"

        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="center", ratio=2)
        grid.add_column(justify="right", ratio=1)
        grid.add_row(
            f"[bold cyan]Marketmind[/] {mode} {bot}{next_run}",
            f"{session} | [yellow]{market}[/]",
            f"{now.strftime('%a %b %d')} [bold]{now.strftime('%I:%M:%S %p')}[/] ET",
        )
        return Panel(grid, style="on dark_blue", padding=(0, 1))

    def _update_last_cycle_time(self):
        """Scan recent logs for last trading cycle start."""
        for line in reversed(list(self.log_lines)):
            if "Starting trading cycle" in line:
                try:
                    ts = line.split("|")[0].strip()
                    t = datetime.strptime(ts, "%H:%M:%S").time()
                    self.last_cycle_time = datetime.combine(datetime.now().date(), t)
                except (ValueError, IndexError):
                    pass
                return

    def get_positions_panel(self) -> Panel:
        positions = self.alpaca.get_positions()
        orders = self.alpaca.get_open_orders()
        trade_history = get_trade_history()

        table = Table(expand=True, box=None, padding=(0, 1), show_header=True)
        table.add_column("Symbol", style="cyan bold", width=22)
        table.add_column("Qty", justify="right", width=5)
        table.add_column("Entry", justify="right", width=9)
        table.add_column("Now", justify="right", width=9)
        table.add_column("P/L", justify="right", width=10)
        table.add_column("%", justify="right", width=7)
        table.add_column("Reason", ratio=1, no_wrap=True)

        total_pl = 0
        total_value = 0

        if positions:
            for p in positions:
                pl = p["unrealized_pl"]
                pl_pct = p["unrealized_plpc"] * 100
                value = p["market_value"]
                total_pl += pl
                total_value += value
                pl_color = "green" if pl >= 0 else "red"
                name = self.alpaca.get_asset_name(p["symbol"])
                padded = p["symbol"].ljust(5)
                symbol_col = f"{padded} [dim]{name}[/]"

                # Get trade rationale
                trade_info = trade_history.get_trade_info(p["symbol"])
                if trade_info:
                    rationale = trade_info.get("grok_rationale", "")
                    score = trade_info.get("score", 0)
                    reason_col = f"[dim]{rationale}[/]"
                else:
                    reason_col = "[dim]—[/]"

                table.add_row(
                    symbol_col,
                    f"{p['qty']:.0f}",
                    f"${p['avg_entry']:.2f}",
                    f"${p['current_price']:.2f}",
                    f"[{pl_color}]${pl:+,.2f}[/]",
                    f"[{pl_color}]{pl_pct:+.1f}%[/]",
                    reason_col,
                )
        else:
            table.add_row("[dim]No positions[/]", "", "", "", "", "", "")

        # Summary row
        if positions:
            table.add_row("", "", "", "", "", "", "")
            pl_color = "green" if total_pl >= 0 else "red"
            table.add_row(
                f"[bold]TOTAL ({len(positions)})[/]",
                "", "", "",
                f"[bold {pl_color}]${total_pl:+,.2f}[/]",
                "",
                f"[dim]${total_value:,.0f} value[/]",
            )

        title = f"[bold]Positions[/]"
        if orders:
            title += f" [dim]({len(orders)} orders)[/]"

        return Panel(table, title=title, border_style="green", padding=(0, 1))

    def get_options_panel(self) -> Panel:
        """Show options positions."""
        table = Table(expand=True, box=None, padding=(0, 1), show_header=True)
        table.add_column("Strategy", style="cyan", width=10)
        table.add_column("Underlying", width=6)
        table.add_column("Contract", ratio=1, no_wrap=True)
        table.add_column("Cost/Credit", justify="right", width=12)
        table.add_column("Max Loss", justify="right", width=10)
        table.add_column("Max Profit", justify="right", width=10)

        positions_file = _get_positions_file()
        options_data = []
        if positions_file.exists():
            try:
                import json
                data = json.loads(positions_file.read_text())
                for key, val in data.get("positions", {}).items():
                    if val.get("status", "").startswith("open"):
                        options_data.append(val)
            except Exception:
                pass

        if options_data:
            for pos in options_data:
                strat = pos.get("strategy", "?")[:10]
                underlying = pos.get("underlying", "?")
                contracts = pos.get("contracts", [])
                contract_str = contracts[0][:20] if contracts else "?"
                ndc = pos.get("net_debit_credit", 0)
                ndc_color = "red" if ndc > 0 else "green"
                table.add_row(
                    strat,
                    underlying,
                    f"[dim]{contract_str}[/]",
                    f"[{ndc_color}]${ndc:+,.0f}[/]",
                    f"[red]${pos.get('max_loss', 0):,.0f}[/]",
                    f"[green]${pos.get('max_profit', 0):,.0f}[/]",
                )
        else:
            table.add_row("[dim]No options positions[/]", "", "", "", "", "")

        return Panel(
            table,
            title=f"[bold]Options ({len(options_data)})[/]",
            border_style="magenta",
            padding=(0, 1),
        )

    def get_orders_panel(self) -> Panel:
        orders = self.alpaca.get_open_orders()

        table = Table(expand=True, box=None, padding=(0, 1), show_header=True)
        table.add_column("Symbol", style="cyan bold", width=8)
        table.add_column("Side", width=5)
        table.add_column("Qty", justify="right", width=6)
        table.add_column("Type", width=8)
        table.add_column("Stop", justify="right", width=10)
        table.add_column("Limit", justify="right", width=10)
        table.add_column("Status", width=12)

        if orders:
            for o in orders:
                side_color = "green" if "buy" in o["side"].lower() else "red"
                stop_str = f"${o['stop_price']:.2f}" if o.get("stop_price") else "—"
                limit_str = f"${o['limit_price']:.2f}" if o.get("limit_price") else "—"
                table.add_row(
                    o["symbol"].ljust(5),
                    f"[{side_color}]{o['side'].upper()}[/]",
                    f"{o['qty']:.0f}",
                    o["type"],
                    stop_str,
                    limit_str,
                    f"[dim]{o['status']}[/]",
                )
        else:
            table.add_row("[dim]No open orders[/]", "", "", "", "", "", "")

        return Panel(table, title=f"[bold]Open Orders ({len(orders)})[/]", border_style="cyan", padding=(0, 1))

    def get_account_panel(self) -> Panel:
        account = self.alpaca.get_account()
        if not account:
            return Panel("[red]Error[/]", title="Account")

        equity = account.get("equity", 0)
        cash = account.get("cash", 0)
        buying_power = account.get("buying_power", 0)
        long_val = account.get("long_market_value", 0)
        short_val = account.get("short_market_value", 0)
        daily_change = account.get("daily_change", 0)
        daily_change_pct = account.get("daily_change_pct", 0)
        last_equity = account.get("last_equity", 0)
        init_margin = account.get("initial_margin", 0)
        maint_margin = account.get("maintenance_margin", 0)

        pl_color = "green" if daily_change >= 0 else "red"

        # Blocked warnings
        blocked = ""
        if account.get("trading_blocked"):
            blocked = " [red bold]TRADING BLOCKED[/]"
        if account.get("account_blocked"):
            blocked = " [red bold]ACCOUNT BLOCKED[/]"

        table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
        table.add_column("Label", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Equity", f"[bold]${equity:,.2f}[/]")
        table.add_row("Prev Close", f"${last_equity:,.2f}")
        table.add_row("Daily P/L", f"[bold {pl_color}]${daily_change:+,.2f} ({daily_change_pct:+.2f}%)[/]")
        table.add_row("", "")
        table.add_row("Cash", f"${cash:,.2f}")
        table.add_row("Buying Power", f"${buying_power:,.2f}")
        table.add_row("Long Value", f"${long_val:,.2f}")
        if short_val:
            table.add_row("Short Value", f"[red]${short_val:,.2f}[/]")
        table.add_row("", "")
        table.add_row("Init Margin", f"${init_margin:,.2f}")
        table.add_row("Maint Margin", f"${maint_margin:,.2f}")

        title = f"[bold]Account[/]{blocked}"
        return Panel(table, title=title, border_style="blue", padding=(0, 1))

    def get_stats_panel(self) -> Panel:
        positions = self.alpaca.get_positions()
        orders = self.alpaca.get_open_orders()
        account = self.alpaca.get_account()

        winners = sum(1 for p in positions if p["unrealized_pl"] > 0)
        losers = len(positions) - winners

        # Day trades display
        day_trades_remaining = account.get("day_trades_remaining", 0)
        day_trade_count = account.get("day_trade_count", 0)
        if settings.is_paper_mode() or day_trades_remaining >= 100:
            dt_display = "[dim]unlimited[/]"
        else:
            dt_color = "green" if day_trades_remaining >= 2 else "yellow" if day_trades_remaining == 1 else "red"
            dt_display = f"[{dt_color}]{day_trades_remaining} left[/] [dim]({day_trade_count} used)[/]"

        table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
        table.add_column("Label", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Positions", f"{len(positions)}/{settings.MAX_CONCURRENT_POSITIONS}")
        table.add_row("Winners", f"[green]{winners}[/]")
        table.add_row("Losers", f"[red]{losers}[/]")
        table.add_row("Open Orders", f"{len(orders)}")
        table.add_row("Day Trades", dt_display)

        return Panel(table, title="[bold]Stats[/]", border_style="yellow", padding=(0, 1))

    def get_config_panel(self) -> Panel:
        table = Table(box=None, show_header=False, padding=(0, 0), expand=True)
        table.add_column("Label", style="dim", width=14)
        table.add_column("Value", justify="right")

        # Risk
        table.add_row("[bold]Risk[/]", "")
        table.add_row("Max Position", f"{settings.MAX_POSITION_PCT:.0%}")
        table.add_row("Stop Loss", f"{settings.STOP_LOSS_PCT:.0%}")
        table.add_row("Take Profit", f"{settings.TAKE_PROFIT_PCT:.0%}")
        table.add_row("Daily Loss Lim", f"{settings.DAILY_LOSS_LIMIT_PCT:.0%}")
        # Trading
        table.add_row("[bold]Trading[/]", "")
        table.add_row("Min Score", f"{settings.MIN_SCORE_THRESHOLD}")
        table.add_row("Scan Interval", f"{settings.SCAN_INTERVAL_MINUTES}m")
        table.add_row("Max Hold", f"{settings.MAX_HOLD_HOURS}h")
        table.add_row("Stale Exit", f"{settings.STALE_POSITION_HOURS}h")
        table.add_row("Short Selling", "Yes" if settings.ALLOW_SHORT_SELLING else "No")
        table.add_row("Backtest Days", f"{settings.BACKTEST_DAYS}")
        # PDT
        table.add_row("[bold]Day Trade[/]", "")
        table.add_row("DT Limit", f"{settings.DAY_TRADE_LIMIT}/5d")
        table.add_row("Min DT Score", f"{settings.MIN_SCORE_FOR_DAY_TRADE}")
        table.add_row("Reserve DTs", f"{settings.RESERVE_DAY_TRADES}")
        # Options
        table.add_row("[bold]Options[/]", "")
        table.add_row("Options", "On" if settings.OPTIONS_ENABLED else "Off")
        table.add_row("Max Opts Pos", f"{settings.OPTIONS_MAX_POSITION_PCT:.0%}")
        table.add_row("Min Score Dir", f"{settings.OPTIONS_MIN_SCORE_DIRECTIONAL}")
        table.add_row("Min Score Sprd", f"{settings.OPTIONS_MIN_SCORE_SPREAD}")
        table.add_row("DTE Range", f"{settings.OPTIONS_DTE_MIN}-{settings.OPTIONS_DTE_MAX}d")
        table.add_row("Max Concurrent", f"{settings.OPTIONS_MAX_CONCURRENT}")

        return Panel(table, title="[bold]Config[/]", border_style="dim", padding=(0, 1))

    def get_api_panel(self) -> Panel:
        tracker = get_tracker()
        today = tracker.get_today_summary()
        total = tracker.get_total_summary()

        table = Table(box=None, show_header=False, padding=(0, 1), expand=True)
        table.add_column("Label", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("[bold]Today[/]", "")
        table.add_row("Requests", f"{today['requests']}")
        table.add_row("Signals", f"{today['signals']}")
        table.add_row("Cost", f"${today['cost']:.4f}")
        table.add_row("", "")
        table.add_row("[bold]All Time[/]", "")
        table.add_row("Requests", f"{total['total_requests']}")
        table.add_row("Cost", f"${total['total_cost']:.4f}")

        return Panel(table, title="[bold]Grok API[/]", border_style="magenta", padding=(0, 1))

    def get_logs_panel(self, fullscreen: bool = False) -> Panel:
        self._read_logs()
        _, rows = self.get_terminal_size()

        if fullscreen:
            lines_to_show = max(5, rows - 6)  # header(3) + footer(1) + panel border(2)
        else:
            lines_to_show = max(5, (rows - 20) // 2)

        all_lines = list(self.log_lines)
        total = len(all_lines)

        if fullscreen and self.log_scroll_offset > 0:
            end = max(0, total - self.log_scroll_offset)
            start = max(0, end - lines_to_show)
            visible = all_lines[start:end]
        else:
            visible = all_lines[-lines_to_show:]

        text = Text()
        for line in visible:
            time_part, msg = self._clean_log(line, fullscreen=fullscreen)
            if "ERROR" in line or "ERR" in line:
                style = "red"
            elif "WARN" in line:
                style = "yellow"
            elif "===" in line:
                style = "bold cyan"
            else:
                style = "white"
            if time_part:
                text.append(time_part, style="dim")
                text.append(" ")
            text.append(msg + "\n", style=style)

        title = "[bold]Activity[/]"
        if fullscreen:
            pos = total - self.log_scroll_offset
            title += f" [dim]({pos}/{total} | Ctrl+O/Esc: exit | Up/Down/PgUp/PgDn: scroll | End: bottom)[/]"

        return Panel(text, title=title, border_style="white", padding=(0, 1))

    def _clean_log(self, line: str, fullscreen: bool = False) -> str:
        parts = line.split("|", 2)
        if len(parts) >= 3:
            time_part = parts[0].strip()
            try:
                t = datetime.strptime(time_part, "%H:%M:%S")
                time_part = t.strftime("%I:%M:%S %p").lstrip("0")
            except ValueError:
                pass
            msg = parts[2].strip()
            if not fullscreen:
                cols, _ = self.get_terminal_size()
                max_len = int(cols * 0.55)
                if len(msg) > max_len:
                    msg = msg[:max_len - 3] + "..."
            return (time_part, msg)
        if not fullscreen:
            return (None, line[:80] if len(line) > 80 else line)
        return (None, line)

    def _read_logs(self):
        log_file = get_log_file()
        if not log_file.exists():
            return
        try:
            with open(log_file, "r") as f:
                f.seek(self.last_log_pos)
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("\x1b"):  # Skip ANSI-only lines
                        self.log_lines.append(line)
                self.last_log_pos = f.tell()
        except:
            pass

    def get_footer(self) -> Panel:
        if self.fullscreen_logs:
            hint = "[dim]Ctrl+O/Esc: back | Up/Down: scroll | PgUp/PgDn: page | End: bottom | q: quit[/]"
        else:
            hint = "[dim]Ctrl+O: expand logs | q: quit | Refresh: 2s[/]"
        return Panel(hint, style="dim", padding=(0, 0))

    def handle_key(self, key: str):
        """Handle a key event. Returns 'quit' to exit."""
        if key == "quit":
            return "quit"
        if key == "ctrl-o":
            self.fullscreen_logs = not self.fullscreen_logs
            self.log_scroll_offset = 0
        elif key == "esc" and self.fullscreen_logs:
            self.fullscreen_logs = False
            self.log_scroll_offset = 0
        elif self.fullscreen_logs:
            total = len(self.log_lines)
            _, rows = self.get_terminal_size()
            page_size = max(5, rows - 6)
            max_offset = max(0, total - page_size)
            if key == "up":
                self.log_scroll_offset = min(self.log_scroll_offset + 1, max_offset)
            elif key == "down":
                self.log_scroll_offset = max(self.log_scroll_offset - 1, 0)
            elif key == "pgup":
                self.log_scroll_offset = min(self.log_scroll_offset + page_size, max_offset)
            elif key == "pgdn":
                self.log_scroll_offset = max(self.log_scroll_offset - page_size, 0)
            elif key == "home":
                self.log_scroll_offset = max_offset
            elif key == "end":
                self.log_scroll_offset = 0
        return None

    def generate_display(self) -> Layout:
        if self.fullscreen_logs:
            layout = Layout()
            layout.split_column(
                Layout(name="header", size=3),
                Layout(name="logs", ratio=1),
                Layout(name="footer", size=1),
            )
            layout["header"].update(self.get_header())
            layout["logs"].update(self.get_logs_panel(fullscreen=True))
            layout["footer"].update(self.get_footer())
            return layout

        layout = self.make_layout()
        layout["header"].update(self.get_header())
        layout["positions"].update(self.get_positions_panel())
        layout["options"].update(self.get_options_panel())
        layout["orders"].update(self.get_orders_panel())
        layout["logs"].update(self.get_logs_panel())
        layout["account"].update(self.get_account_panel())
        layout["stats"].update(self.get_stats_panel())
        layout["config"].update(self.get_config_panel())
        layout["api"].update(self.get_api_panel())
        layout["footer"].update(self.get_footer())
        return layout


def main():
    import atexit
    import signal as sig

    bot = BotManager()
    keys = KeyReader()

    # Ensure bot + terminal are cleaned up on any exit
    def cleanup():
        keys.stop()
        if bot.is_running():
            bot.stop()

    atexit.register(cleanup)
    sig.signal(sig.SIGTERM, lambda *_: cleanup())

    bot.start()
    keys.start()

    dashboard = Dashboard(bot)

    log_file = get_log_file()
    if log_file.exists():
        lines = log_file.read_text().split("\n")[-100:]
        for line in lines:
            if line.strip():
                dashboard.log_lines.append(line.strip())
        dashboard.last_log_pos = log_file.stat().st_size

    try:
        with Live(dashboard.generate_display(), refresh_per_second=0.5, screen=True) as live:
            while True:
                if not bot.is_running():
                    bot.start()
                # Process all pending keys
                while True:
                    key = keys.get_key()
                    if key is None:
                        break
                    result = dashboard.handle_key(key)
                    if result == "quit":
                        raise KeyboardInterrupt
                time.sleep(0.2)
                live.update(dashboard.generate_display())
    except KeyboardInterrupt:
        pass
    finally:
        keys.stop()
        console.print("\n[yellow]Stopping bot...[/]")
        bot.stop()
        console.print("[green]Bot stopped.[/]")


if __name__ == "__main__":
    main()
