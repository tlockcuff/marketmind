"""PostgreSQL connection pool singleton."""

import logging
import os
from pathlib import Path

import psycopg
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

from typing import Optional

_pool: Optional[ConnectionPool] = None


def get_pool() -> ConnectionPool:
    """Return the global connection pool, creating it on first call."""
    global _pool
    if _pool is None:
        dsn = os.environ.get("DATABASE_URL", "postgresql://trader:trader@192.168.1.2:5556/daytrading")
        _pool = ConnectionPool(dsn, min_size=1, max_size=5, open=True)
    return _pool


def get_db() -> psycopg.Connection:
    """Get a connection from the pool. Use as context manager:
        with get_db() as conn:
            conn.execute(...)
    """
    return get_pool().connection()


def init_db():
    """Run schema.sql to create tables (idempotent)."""
    schema_path = Path(__file__).parent.parent / "schema.sql"
    sql = schema_path.read_text()
    with get_db() as conn:
        conn.execute(sql)
        conn.commit()
    logger.info("Database schema initialized")


def wipe_data(mode: str = None):
    """Truncate all data tables. If mode given, only delete rows for that mode.
    Used for paper account resets."""
    with get_db() as conn:
        if mode:
            # Mode-specific tables
            for table in ("trades", "rejected_signals", "options_positions", "logs"):
                conn.execute(f"DELETE FROM {table} WHERE mode = %s", (mode,))
            # Shared tables (always wipe on reset)
            for table in ("api_usage", "symbol_cache", "daily_stats",
                          "config_overrides", "daily_target", "congress_cache",
                          "bot_instances"):
                conn.execute(f"DELETE FROM {table}")
        else:
            for table in ("trades", "rejected_signals", "api_usage",
                          "symbol_cache", "options_positions", "daily_stats",
                          "config_overrides", "daily_target", "congress_cache",
                          "bot_instances", "logs"):
                conn.execute(f"TRUNCATE {table} RESTART IDENTITY CASCADE")
        conn.commit()
    logger.info(f"Database wiped (mode={mode or 'all'})")


def close_pool():
    """Shut down the connection pool."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
