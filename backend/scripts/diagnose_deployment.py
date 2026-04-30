#!/usr/bin/env python3
"""Railway deployment diagnostics for ARIA.

This script intentionally reports whether secrets are present without printing
their values.
"""

from __future__ import annotations

import importlib
import os
import sys
from dataclasses import dataclass
from urllib.parse import urlparse

import psycopg2
from psycopg2.extensions import connection as PgConnection


SEEDED_TABLES = [
    "aria_users",
    "aria_cards",
    "aria_transactions",
    "aria_mcc_codes",
    "aria_fraud_labels",
]

APP_TABLES = [
    "audit_sessions",
    "audit_findings",
    "transaction_analyses",
    "model_metrics",
]


@dataclass
class Check:
    name: str
    passed: bool
    detail: str


def mask_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.hostname:
        return "<invalid url>"
    username = parsed.username or "<user>"
    host = parsed.hostname
    port = f":{parsed.port}" if parsed.port else ""
    database = parsed.path or ""
    return f"{parsed.scheme}://{username}:***@{host}{port}{database}"


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not url:
        raise RuntimeError("DATABASE_URL or POSTGRES_URL is not set.")
    return (
        url.replace("postgresql+asyncpg://", "postgresql://", 1)
        .replace("postgres+asyncpg://", "postgresql://", 1)
        .replace("postgres://", "postgresql://", 1)
    )


def table_exists(conn: PgConnection, table_name: str) -> bool:
    with conn.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s)", (table_name,))
        return cursor.fetchone()[0] is not None


def row_count(conn: PgConnection, table_name: str) -> int:
    with conn.cursor() as cursor:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        return int(cursor.fetchone()[0])


def scalar(conn: PgConnection, query: str) -> int:
    with conn.cursor() as cursor:
        cursor.execute(query)
        return int(cursor.fetchone()[0] or 0)


def check_env_presence(name: str) -> Check:
    value = os.getenv(name)
    return Check(name, bool(value), "set" if value else "missing")


def run() -> list[Check]:
    checks: list[Check] = []

    try:
        db_url = get_database_url()
        checks.append(Check("DATABASE_URL", True, mask_url(db_url)))
    except Exception as exc:
        checks.append(Check("DATABASE_URL", False, str(exc)))
        return checks

    conn: PgConnection | None = None
    try:
        conn = psycopg2.connect(db_url)
        checks.append(Check("database_connect", True, "connection passed"))

        for table in SEEDED_TABLES + APP_TABLES:
            if not table_exists(conn, table):
                checks.append(Check(f"table:{table}", False, "missing"))
                continue
            count = row_count(conn, table)
            checks.append(Check(f"table:{table}", True, f"{count:,} rows"))

        try:
            transactions = scalar(conn, "SELECT COUNT(*) FROM aria_transactions")
            fraud_labels = scalar(conn, "SELECT COUNT(*) FROM aria_fraud_labels")
            fraud_cases = scalar(conn, "SELECT COUNT(*) FROM aria_fraud_labels WHERE is_fraud IS TRUE")
            fraud_rate = fraud_cases / fraud_labels if fraud_labels else 0.0
            risk = "HIGH" if fraud_rate >= 0.02 or fraud_cases >= 100 else "MEDIUM" if transactions else "UNKNOWN"
            checks.append(
                Check(
                    "dashboard_query",
                    transactions > 0 and fraud_labels > 0,
                    (
                        f"risk={risk}; transactions={transactions:,}; "
                        f"fraud_cases={fraud_cases:,}; fraud_rate={fraud_rate:.4%}"
                    ),
                )
            )
        except Exception as exc:
            checks.append(Check("dashboard_query", False, str(exc)))
    except Exception as exc:
        checks.append(Check("database_connect", False, str(exc)))
    finally:
        if conn is not None:
            conn.close()

    for name in ["LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]:
        checks.append(check_env_presence(name))

    livekit_url = os.getenv("LIVEKIT_URL", "")
    if livekit_url:
        checks.append(
            Check(
                "LIVEKIT_URL_scheme",
                livekit_url.startswith("wss://"),
                "must start with wss://",
            )
        )

    try:
        importlib.import_module("backend.api.main")
        checks.append(Check("api_import", True, "backend.api.main imported"))
    except Exception as exc:
        checks.append(Check("api_import", False, str(exc)))

    return checks


def main() -> int:
    checks = run()
    passed = 0
    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"[{status}] {check.name}: {check.detail}")
        if check.passed:
            passed += 1

    print(f"{passed}/{len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
