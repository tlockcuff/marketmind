"""PostgreSQL logging handler — writes log records to the logs table."""

import logging
import os


class PostgresHandler(logging.Handler):
    """Logging handler that writes records to the DB logs table."""

    def __init__(self, level=logging.INFO):
        super().__init__(level)
        self._mode = os.environ.get("TRADING_MODE", "paper").lower()
        if self._mode == "live":
            self._mode = "live"
        else:
            self._mode = "paper"

    def emit(self, record):
        try:
            from src.db import get_db
            msg = self.format(record)
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO logs (mode, level, logger_name, message) VALUES (%s, %s, %s, %s)",
                    (self._mode, record.levelname, record.name, msg),
                )
                conn.commit()
        except Exception:
            pass  # Never let logging errors crash the app


def get_logs(n: int = 100) -> list[str]:
    """Read recent logs from DB."""
    import datetime
    mode = os.environ.get("TRADING_MODE", "paper").lower()
    if mode != "live":
        mode = "paper"
    try:
        from src.db import get_db
        with get_db() as conn:
            rows = conn.execute(
                """SELECT created_at, level, message FROM logs
                   WHERE mode = %s ORDER BY id DESC LIMIT %s""",
                (mode, n),
            ).fetchall()
            # Reverse to chronological order
            lines = []
            for r in reversed(rows):
                if r[0]:
                    # Convert UTC to local time
                    local_ts = r[0].astimezone()
                    ts = local_ts.strftime("%H:%M:%S")
                else:
                    ts = ""
                lines.append(f"{ts} | {r[1]:5} | {r[2]}")
            return lines
    except Exception:
        return []
