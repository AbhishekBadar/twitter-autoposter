"""SQLite database for post queue and topic tracking."""

import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, List, Dict
from config import DB_PATH

logger = logging.getLogger(__name__)


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def get_db():
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                source TEXT NOT NULL,
                url TEXT,
                used INTEGER DEFAULT 0,
                score REAL DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                format TEXT NOT NULL,
                source_topic TEXT,
                status TEXT DEFAULT 'pending',
                telegram_message_id INTEGER,
                sheet_row INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
    logger.info("Database initialized")


# --- Topics ---

def save_topics(topics: List[Dict]) -> int:
    """Save researched topics. Returns count saved."""
    saved = 0
    with get_db() as conn:
        for t in topics:
            try:
                conn.execute(
                    "INSERT INTO topics (title, source, url, score) VALUES (?, ?, ?, ?)",
                    (t["title"], t["source"], t.get("url", ""), t.get("score", 0)),
                )
                saved += 1
            except sqlite3.IntegrityError:
                continue
    logger.info("Saved %d topics", saved)
    return saved


def get_unused_topics(limit: int = 20) -> List[Dict]:
    """Get top unused topics sorted by score."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM topics WHERE used = 0 ORDER BY score DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_topics_used(topic_ids: List[int]):
    """Mark topics as used after post generation."""
    with get_db() as conn:
        placeholders = ",".join("?" * len(topic_ids))
        conn.execute(
            f"UPDATE topics SET used = 1 WHERE id IN ({placeholders})", topic_ids
        )


# --- Posts ---

def save_post(content: str, fmt: str, source_topic: str) -> int:
    """Save a generated post. Returns post id."""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO posts (content, format, source_topic, status) VALUES (?, ?, ?, 'pending')",
            (content, fmt, source_topic),
        )
        return cursor.lastrowid


def get_pending_posts() -> List[Dict]:
    """Get all posts awaiting approval."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM posts WHERE status = 'pending' ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


def update_post_status(post_id: int, status: str):
    """Update post status: approved, rejected, edited."""
    with get_db() as conn:
        conn.execute("UPDATE posts SET status = ? WHERE id = ?", (status, post_id))


def update_post_content(post_id: int, content: str):
    """Update post content after edit."""
    with get_db() as conn:
        conn.execute("UPDATE posts SET content = ? WHERE id = ?", (content, post_id))


def set_telegram_message_id(post_id: int, message_id: int):
    """Link post to its Telegram message."""
    with get_db() as conn:
        conn.execute(
            "UPDATE posts SET telegram_message_id = ? WHERE id = ?",
            (message_id, post_id),
        )


def set_sheet_row(post_id: int, row: int):
    """Record which sheet row the post was written to."""
    with get_db() as conn:
        conn.execute("UPDATE posts SET sheet_row = ? WHERE id = ?", (row, post_id))


def get_post_by_telegram_id(message_id: int) -> Optional[Dict]:
    """Find post by its Telegram message ID."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM posts WHERE telegram_message_id = ?", (message_id,)
        ).fetchone()
    return dict(row) if row else None


def get_post_by_id(post_id: int) -> Optional[Dict]:
    """Find post by its database ID."""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    return dict(row) if row else None


def get_recent_posts(limit: int = 20) -> List[Dict]:
    """Get most recent posts for status display."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM posts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_today_stats() -> dict:
    """Get stats for today's posts."""
    today = datetime.now().strftime("%Y-%m-%d")
    with get_db() as conn:
        generated = conn.execute(
            "SELECT COUNT(*) FROM posts WHERE date(created_at) = ?", (today,)
        ).fetchone()[0]
        approved = conn.execute(
            "SELECT COUNT(*) FROM posts WHERE date(created_at) = ? AND status = 'approved'",
            (today,),
        ).fetchone()[0]
        rejected = conn.execute(
            "SELECT COUNT(*) FROM posts WHERE date(created_at) = ? AND status = 'rejected'",
            (today,),
        ).fetchone()[0]
    return {"generated": generated, "approved": approved, "rejected": rejected}
