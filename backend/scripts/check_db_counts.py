#!/usr/bin/env python3
"""Print row counts for ARIA dataset tables in Postgres."""

from __future__ import annotations

import os
import sys
import time

import psycopg2
from psycopg2 import OperationalError, sql


TABLES = (
    "aria_users",
    "aria_cards",
    "aria_transactions",
    "aria_mcc_codes",
    "aria_fraud_labels",
)
MAX_RETRIES = int(os.getenv("ARIA_DB_COUNT_MAX_RETRIES", "6"))


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required.")
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def connect():
    return psycopg2.connect(
        get_database_url(),
        connect_timeout=30,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
        application_name="aria_count_check",
    )


def main() -> int:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            conn = connect()
            try:
                with conn.cursor() as cursor:
                    for table in TABLES:
                        cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
                        count = cursor.fetchone()[0]
                        print(f"{table}: {count:,}")
                return 0
            finally:
                conn.close()
        except OperationalError as exc:
            if attempt >= MAX_RETRIES:
                raise
            sleep_seconds = min(90, 5 * attempt)
            print(
                f"[ARIA counts] Connection failed on attempt {attempt}/{MAX_RETRIES}: {exc}. "
                f"Retrying in {sleep_seconds}s.",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(sleep_seconds)

    raise RuntimeError(f"Count check failed after {MAX_RETRIES} attempts")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ARIA counts] ERROR: {exc}", file=sys.stderr)
        raise
