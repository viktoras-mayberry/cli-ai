"""SQLite-backed conversation history log.

Every query sent through MAYAI is recorded in ~/.config/mayai/history.db.
The schema is intentionally simple and append-only — rows are never updated.

Table: conversations
  id            INTEGER PRIMARY KEY
  ts            TEXT    — ISO-8601 timestamp (UTC)
  provider      TEXT
  model         TEXT
  pattern       TEXT    — pattern name if one was active, else NULL
  session_name  TEXT    — named session if one was active, else NULL
  system_prompt TEXT
  user_message  TEXT    — the final user turn sent
  response      TEXT    — the full assistant response
  input_tokens  INTEGER — estimated
  output_tokens INTEGER — estimated
  cost_usd      REAL    — estimated, NULL if no pricing data
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

from .config import CONFIG_DIR

DB_PATH = CONFIG_DIR / "history.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT    NOT NULL,
    provider      TEXT    NOT NULL,
    model         TEXT    NOT NULL,
    pattern       TEXT,
    session_name  TEXT,
    system_prompt TEXT,
    user_message  TEXT    NOT NULL,
    response      TEXT    NOT NULL,
    input_tokens  INTEGER,
    output_tokens INTEGER,
    cost_usd      REAL
);
CREATE INDEX IF NOT EXISTS idx_ts       ON conversations(ts);
CREATE INDEX IF NOT EXISTS idx_provider ON conversations(provider);
"""


@contextmanager
def _db() -> Generator[sqlite3.Connection, None, None]:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
        yield conn
    finally:
        conn.close()


def log_exchange(
    *,
    provider: str,
    model: str,
    user_message: str,
    response: str,
    system_prompt: str = "",
    pattern: str = "",
    session_name: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float | None = None,
) -> None:
    """Insert one conversation turn into the log. Never raises — logs are best-effort."""
    try:
        ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with _db() as conn:
            conn.execute(
                """
                INSERT INTO conversations
                  (ts, provider, model, pattern, session_name,
                   system_prompt, user_message, response,
                   input_tokens, output_tokens, cost_usd)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    ts,
                    provider,
                    model,
                    pattern or None,
                    session_name or None,
                    system_prompt or None,
                    user_message,
                    response,
                    input_tokens or None,
                    output_tokens or None,
                    cost_usd,
                ),
            )
            conn.commit()
    except Exception:
        pass  # history is best-effort; never block the main flow


def search_history(
    query: str = "",
    provider: str = "",
    limit: int = 20,
) -> list[dict]:
    """Return recent history rows, optionally filtered."""
    try:
        with _db() as conn:
            conditions = []
            params: list = []

            if query:
                conditions.append(
                    "(user_message LIKE ? OR response LIKE ?)"
                )
                like = f"%{query}%"
                params += [like, like]

            if provider:
                conditions.append("provider = ?")
                params.append(provider)

            where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
            params.append(limit)

            rows = conn.execute(
                f"""
                SELECT id, ts, provider, model, pattern, session_name,
                       user_message, response, input_tokens, output_tokens, cost_usd
                FROM conversations
                {where}
                ORDER BY ts DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def get_stats() -> dict:
    """Return aggregate stats across all logged conversations."""
    try:
        with _db() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*)                          AS total_queries,
                    COALESCE(SUM(cost_usd), 0)        AS total_cost,
                    COALESCE(SUM(input_tokens), 0)    AS total_input_tokens,
                    COALESCE(SUM(output_tokens), 0)   AS total_output_tokens,
                    MIN(ts)                           AS first_query,
                    MAX(ts)                           AS last_query
                FROM conversations
                """
            ).fetchone()

            provider_rows = conn.execute(
                """
                SELECT provider, COUNT(*) AS cnt
                FROM conversations
                GROUP BY provider
                ORDER BY cnt DESC
                """
            ).fetchall()

            model_rows = conn.execute(
                """
                SELECT model, COUNT(*) AS cnt
                FROM conversations
                GROUP BY model
                ORDER BY cnt DESC
                LIMIT 5
                """
            ).fetchall()

            return {
                "total_queries": row["total_queries"],
                "total_cost_usd": row["total_cost"],
                "total_input_tokens": row["total_input_tokens"],
                "total_output_tokens": row["total_output_tokens"],
                "first_query": row["first_query"],
                "last_query": row["last_query"],
                "by_provider": [dict(r) for r in provider_rows],
                "top_models": [dict(r) for r in model_rows],
            }
    except Exception:
        return {}


def delete_history(before_ts: str | None = None) -> int:
    """Delete history rows. If before_ts given, only delete rows older than that ISO timestamp.
    Returns number of rows deleted."""
    try:
        with _db() as conn:
            if before_ts:
                cur = conn.execute(
                    "DELETE FROM conversations WHERE ts < ?", (before_ts,)
                )
            else:
                cur = conn.execute("DELETE FROM conversations")
            conn.commit()
            return cur.rowcount
    except Exception:
        return 0
