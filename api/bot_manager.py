"""Singleton BotManager for spawning/stopping the trading bot subprocess.

Orphan prevention: atexit hook kills child on normal exit. For hard kills,
the bot's own PID-lock and the data_provider's _bot_running() will detect
stale PIDs on next startup.
"""

from __future__ import annotations

import atexit
import logging
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
BOT_SCRIPT = PROJECT_ROOT / "src" / "main.py"

_instance = None


def get_bot_manager() -> "BotManager":
    global _instance
    if _instance is None:
        _instance = BotManager()
    return _instance


def _cleanup():
    """Module-level atexit: stop bot if running."""
    if _instance is not None:
        _instance.stop()


atexit.register(_cleanup)


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

        args = [sys.executable, "-u", str(BOT_SCRIPT)]
        if env.get("TRADING_MODE") == "live":
            args.append("--live")
            env["SKIP_LIVE_CONFIRM"] = "1"
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
        logger.info("Bot started (pid=%d)", self.process.pid)

    def stop(self):
        if self.process and self.is_running():
            pid = self.process.pid
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
                logger.info("Bot stopped (pid=%d)", pid)
            except subprocess.TimeoutExpired:
                self.process.kill()
                logger.warning("Bot killed (pid=%d)", pid)
        self.process = None
        self.start_time = None

    def uptime_seconds(self) -> float | None:
        if not self.is_running() or not self.start_time:
            return None
        return (datetime.now() - self.start_time).total_seconds()
