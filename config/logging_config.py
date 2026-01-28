import logging
import os
import sys
from datetime import datetime
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def get_mode_prefix() -> str:
    """Get log file prefix based on trading mode."""
    mode = os.environ.get("TRADING_MODE", "paper").lower()
    return "live" if mode == "live" else "paper"


class ColorFormatter(logging.Formatter):
    """Colored console output."""

    COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "INFO": "\033[32m",      # green
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",     # red
        "CRITICAL": "\033[35m",  # magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        # Create a copy to avoid affecting other handlers (race condition fix)
        import copy
        record_copy = copy.copy(record)
        color = self.COLORS.get(record_copy.levelname, "")
        record_copy.levelname = f"{color}{record_copy.levelname:8}{self.RESET}"
        return super().format(record_copy)


def setup_logging(level=logging.INFO, log_file=None):
    """Configure logging with console and file handlers."""

    # Root logger
    root = logging.getLogger()
    root.setLevel(level)

    # Clear existing handlers
    root.handlers.clear()

    # Console handler (colored, realtime, clean format)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(ColorFormatter(
        "%(asctime)s │ %(message)s",
        datefmt="%H:%M:%S"
    ))
    root.addHandler(console)

    # File handler (detailed, persistent) - mode-specific
    mode = get_mode_prefix()
    log_file = log_file or LOG_DIR / f"{mode}_trading_{datetime.now():%Y%m%d}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    root.addHandler(file_handler)

    # Also log to trading.log for TUI (cleaner format) - mode-specific
    main_log = LOG_DIR / f"{mode}_trading.log"
    main_handler = logging.FileHandler(main_log)
    main_handler.setLevel(level)
    main_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(message)s",
        datefmt="%H:%M:%S"
    ))
    root.addHandler(main_handler)

    # Quiet noisy libs
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("yfinance").setLevel(logging.WARNING)

    return root
