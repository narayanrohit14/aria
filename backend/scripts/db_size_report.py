#!/usr/bin/env python3
"""Print database and ARIA table sizes for Postgres."""

from __future__ import annotations

import os
import sys

import psycopg2


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required.")
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def main() -> int:
    conn = psycopg2.connect(get_database_url(), connect_timeout=30)
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
            print(f"database_size: {cursor.fetchone()[0]}")

            cursor.execute(
                """
                SELECT
                    relname,
                    pg_size_pretty(pg_total_relation_size(relid)) AS total_size
                FROM pg_catalog.pg_statio_user_tables
                WHERE relname LIKE 'aria_%'
                ORDER BY pg_total_relation_size(relid) DESC
                """
            )
            for table, size in cursor.fetchall():
                print(f"{table}: {size}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ARIA db size] ERROR: {exc}", file=sys.stderr)
        raise
