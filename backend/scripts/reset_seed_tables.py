#!/usr/bin/env python3
"""Drop ARIA seed tables from Postgres to recover space after a partial load."""

from __future__ import annotations

import os
import sys

import psycopg2
from psycopg2 import sql


TABLES = (
    "aria_fraud_labels",
    "aria_transactions",
    "aria_mcc_codes",
    "aria_cards",
    "aria_users",
)


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required.")
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql://", 1)
    return database_url


def main() -> int:
    if os.getenv("ARIA_CONFIRM_RESET") != "yes":
        raise RuntimeError("Set ARIA_CONFIRM_RESET=yes to drop ARIA seed tables.")

    conn = psycopg2.connect(get_database_url(), connect_timeout=30)
    try:
        with conn.cursor() as cursor:
            for table in TABLES:
                cursor.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table)))
                print(f"dropped {table}")
        conn.commit()
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ARIA reset] ERROR: {exc}", file=sys.stderr)
        raise
