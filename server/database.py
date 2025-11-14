from __future__ import annotations

import contextlib
from typing import Dict, Iterator, List

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from psycopg.types.json import Json
from pgvector.psycopg import register_vector, Vector

from .config import get_settings

settings = get_settings()

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=settings.pg_dsn,
            min_size=settings.pg_pool_min_size,
            max_size=settings.pg_pool_max_size,
            kwargs={"row_factory": dict_row},
        )
    return _pool


@contextlib.contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    pool = get_pool()
    with pool.connection() as conn:
        register_vector(conn)
        yield conn


def init_memory_table() -> None:
    table = settings.memory_table
    sql = f"""
    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE IF NOT EXISTS {table} (
        id TEXT,
        sender_email TEXT,
        subject TEXT,
        snippet TEXT,
        body TEXT,
        email_type TEXT,
        priority TEXT,
        requires_reply BOOLEAN,
        tags JSONB,
        metadata JSONB,
        embedding VECTOR(768),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        PRIMARY KEY (id)
    );
    """
    with get_connection() as conn:
        conn.execute(sql)
        conn.commit()


def store_email_memory(records: List[Dict]) -> int:
    if not records:
        return 0

    from .embeddings import embed_texts  # local import to avoid cycle

    texts = [
        f"{rec.get('subject', '')} {rec.get('body') or rec.get('snippet') or ''}".strip()
        for rec in records
    ]
    embeddings = embed_texts(texts)
    insert_sql = f"""
    INSERT INTO {settings.memory_table}
        (id, sender_email, subject, snippet, body, email_type, priority, requires_reply, tags, metadata, embedding)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (id) DO UPDATE SET
        sender_email = EXCLUDED.sender_email,
        subject = EXCLUDED.subject,
        snippet = EXCLUDED.snippet,
        body = EXCLUDED.body,
        email_type = EXCLUDED.email_type,
        priority = EXCLUDED.priority,
        requires_reply = EXCLUDED.requires_reply,
        tags = EXCLUDED.tags,
        metadata = EXCLUDED.metadata,
        embedding = EXCLUDED.embedding,
        created_at = NOW();
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            for rec, emb in zip(records, embeddings):
                cur.execute(
                    insert_sql,
                    (
                        rec.get("id"),
                        rec.get("sender_email"),
                        rec.get("subject"),
                        rec.get("snippet"),
                        rec.get("body"),
                        rec.get("email_type"),
                        rec.get("priority"),
                        rec.get("requires_reply"),
                        Json(rec.get("tags") or []),
                        Json(rec.get("metadata") or {}),
                        Vector(emb),
                    ),
                )
        conn.commit()
    return len(records)


def get_weekly_metrics() -> Dict:
    table = settings.memory_table
    sql_counts = f"""
    SELECT
        COUNT(*) AS total_emails,
        COUNT(*) FILTER (WHERE email_type = 'meeting') AS meeting_count,
        COUNT(*) FILTER (WHERE email_type = 'newsletter') AS newsletter_count,
        COUNT(*) FILTER (WHERE requires_reply) AS requires_reply_count,
        COUNT(*) FILTER (WHERE NOT requires_reply OR requires_reply IS NULL) AS info_count
    FROM {table}
    WHERE created_at >= NOW() - INTERVAL '7 days';
    """
    sql_newsletters = f"""
    SELECT subject, sender_email, snippet
    FROM {table}
    WHERE email_type = 'newsletter'
      AND created_at >= NOW() - INTERVAL '7 days'
    LIMIT 20;
    """
    with get_connection() as conn:
        counts = conn.execute(sql_counts).fetchone() or {}
        newsletters = conn.execute(sql_newsletters).fetchall()
    counts["newsletter_samples"] = newsletters
    return counts


def fetch_recent_emails(days: int = 7, limit: int = 50) -> List[Dict]:
    table = settings.memory_table
    sql = f"""
    SELECT id, sender_email AS "from", subject, snippet, body, email_type, priority,
           requires_reply, tags, metadata, created_at
    FROM {table}
    WHERE created_at >= NOW() - INTERVAL '{days} days'
    ORDER BY created_at DESC
    LIMIT %s;
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    return rows
