#!/usr/bin/env python3
"""
Seed the full ARIA sample dataset into Postgres.

The script streams CSV files with PostgreSQL COPY and loads the large fraud
labels JSON in batches so the full dataset is not held in memory.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
import zlib
from io import StringIO
from pathlib import Path

import psycopg2
from psycopg2 import OperationalError, sql


ROOT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT_DIR / "backend" / "data" / "sample-data"

CSV_FILES = {
    "aria_users": DATA_DIR / "users_data.csv",
    "aria_cards": DATA_DIR / "cards_data.csv",
    "aria_transactions": DATA_DIR / "transactions_data.csv",
}
MCC_FILE = DATA_DIR / "mcc_codes.json"
FRAUD_FILE = DATA_DIR / "train_fraud_labels.json"

FRAUD_PAIR_RE = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"')
CSV_BATCH_SIZE = int(os.getenv("ARIA_SEED_CSV_BATCH_SIZE", "100000"))
FRAUD_BATCH_SIZE = int(os.getenv("ARIA_SEED_FRAUD_BATCH_SIZE", "100000"))
MAX_RETRIES = int(os.getenv("ARIA_SEED_MAX_RETRIES", "6"))
SEED_MODE = os.getenv("ARIA_SEED_MODE", "full").lower()
REPRESENTATIVE_TX_LIMIT = int(os.getenv("ARIA_SEED_REPRESENTATIVE_TX_LIMIT", "500000"))
TRANSACTION_ROW_ESTIMATE = int(os.getenv("ARIA_SEED_TRANSACTION_ROW_ESTIMATE", "13305915"))


CREATE_TABLES = [
    """
    CREATE TABLE IF NOT EXISTS aria_users (
        id BIGINT PRIMARY KEY,
        current_age INTEGER,
        retirement_age INTEGER,
        birth_year INTEGER,
        birth_month INTEGER,
        gender TEXT,
        address TEXT,
        latitude DOUBLE PRECISION,
        longitude DOUBLE PRECISION,
        per_capita_income NUMERIC,
        yearly_income NUMERIC,
        total_debt NUMERIC,
        credit_score INTEGER,
        num_credit_cards INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS aria_cards (
        id BIGINT PRIMARY KEY,
        client_id BIGINT,
        card_brand TEXT,
        card_type TEXT,
        card_number TEXT,
        expires TEXT,
        cvv TEXT,
        has_chip BOOLEAN,
        num_cards_issued INTEGER,
        credit_limit NUMERIC,
        acct_open_date TEXT,
        year_pin_last_changed INTEGER,
        card_on_dark_web BOOLEAN
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS aria_transactions (
        id BIGINT PRIMARY KEY,
        transaction_date TIMESTAMP,
        client_id BIGINT,
        card_id BIGINT,
        amount NUMERIC,
        use_chip TEXT,
        merchant_id BIGINT,
        merchant_city TEXT,
        merchant_state TEXT,
        zip TEXT,
        mcc INTEGER,
        errors TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS aria_mcc_codes (
        mcc_code INTEGER PRIMARY KEY,
        description TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS aria_fraud_labels (
        transaction_id BIGINT PRIMARY KEY,
        label TEXT NOT NULL,
        is_fraud BOOLEAN NOT NULL
    )
    """,
]

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_aria_cards_client_id ON aria_cards (client_id)",
    "CREATE INDEX IF NOT EXISTS idx_aria_transactions_client_id ON aria_transactions (client_id)",
    "CREATE INDEX IF NOT EXISTS idx_aria_transactions_card_id ON aria_transactions (card_id)",
    "CREATE INDEX IF NOT EXISTS idx_aria_transactions_mcc ON aria_transactions (mcc)",
    "CREATE INDEX IF NOT EXISTS idx_aria_fraud_labels_is_fraud ON aria_fraud_labels (is_fraud)",
]


def log(message: str) -> None:
    print(f"[ARIA seed] {message}", flush=True)


def get_database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required. Export your Railway Postgres URL before running.")
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
        application_name="aria_seed",
    )


def with_retries(label: str, operation):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return operation()
        except OperationalError as exc:
            if attempt >= MAX_RETRIES:
                raise
            sleep_seconds = min(90, 5 * attempt)
            log(
                f"{label} failed on attempt {attempt}/{MAX_RETRIES}: {exc}. "
                f"Retrying in {sleep_seconds}s."
            )
            time.sleep(sleep_seconds)
    raise RuntimeError(f"{label} failed after {MAX_RETRIES} attempts")


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Required dataset file is missing: {path}")


def read_csv_header(path: Path) -> list[str]:
    require_file(path)
    with path.open(newline="", encoding="utf-8") as file:
        reader = csv.reader(file)
        return next(reader)


def load_fraud_label_map() -> dict[str, str]:
    require_file(FRAUD_FILE)
    log(f"Reading fraud label map from {FRAUD_FILE}")
    with FRAUD_FILE.open(encoding="utf-8") as file:
        raw = json.load(file)
    labels = raw.get("target", raw) if isinstance(raw, dict) else {}
    log(f"Loaded {len(labels):,} fraud labels into memory for representative sampling")
    return labels


def choose_representative_transaction_ids(limit: int) -> tuple[set[str], dict[str, str]]:
    labels = load_fraud_label_map()
    fraud_ids = {transaction_id for transaction_id, label in labels.items() if label == "Yes"}
    selected_ids = set(fraud_ids)
    target_limit = max(limit, len(selected_ids))
    non_fraud_target = max(0, target_limit - len(fraud_ids))
    hash_threshold = int((non_fraud_target / TRANSACTION_ROW_ESTIMATE) * 1_000_000)

    log(
        f"Selecting representative transactions: all {len(fraud_ids):,} fraud-positive "
        f"labels plus non-fraud context up to {target_limit:,} rows"
    )

    with CSV_FILES["aria_transactions"].open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            transaction_id = row["id"]
            if transaction_id in selected_ids:
                continue
            if len(selected_ids) >= target_limit:
                continue
            if zlib.crc32(transaction_id.encode("utf-8")) % 1_000_000 < hash_threshold:
                selected_ids.add(transaction_id)

    selected_labels = {
        transaction_id: labels[transaction_id]
        for transaction_id in selected_ids
        if transaction_id in labels
    }
    log(
        f"Representative selection complete: {len(selected_ids):,} transactions, "
        f"{sum(1 for label in selected_labels.values() if label == 'Yes'):,} fraud-positive labels"
    )
    return selected_ids, selected_labels


def create_schema(conn) -> None:
    log("Creating tables and indexes if needed")
    with conn.cursor() as cursor:
        for statement in CREATE_TABLES:
            cursor.execute(statement)
        for statement in CREATE_INDEXES:
            cursor.execute(statement)
    conn.commit()


def q(identifier: str) -> sql.Identifier:
    return sql.Identifier(identifier)


def create_stage_table(cursor, stage_name: str, columns: list[str]) -> None:
    column_defs = sql.SQL(", ").join(
        sql.SQL("{} TEXT").format(q(column)) for column in columns
    )
    cursor.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(q(stage_name)))
    cursor.execute(sql.SQL("CREATE TEMP TABLE {} ({})").format(q(stage_name), column_defs))


def copy_csv_to_stage(cursor, stage_name: str, columns: list[str], path: Path) -> None:
    copy_sql = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER TRUE)").format(
        q(stage_name),
        sql.SQL(", ").join(q(column) for column in columns),
    )
    with path.open("r", encoding="utf-8", newline="") as file:
        cursor.copy_expert(copy_sql.as_string(cursor.connection), file)


def copy_dict_batch_to_stage(
    cursor,
    stage_name: str,
    columns: list[str],
    rows: list[dict[str, str]],
) -> None:
    copy_sql = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT CSV)").format(
        q(stage_name),
        sql.SQL(", ").join(q(column) for column in columns),
    )
    data = StringIO()
    writer = csv.writer(data)
    for row in rows:
        writer.writerow([row.get(column, "") for column in columns])
    data.seek(0)
    cursor.copy_expert(copy_sql.as_string(cursor.connection), data)


def load_users(conn) -> None:
    path = CSV_FILES["aria_users"]
    columns = read_csv_header(path)
    log(f"Loading users from {path}")
    with conn.cursor() as cursor:
        create_stage_table(cursor, "stage_aria_users", columns)
        copy_csv_to_stage(cursor, "stage_aria_users", columns, path)
        cursor.execute(
            """
            INSERT INTO aria_users (
                id, current_age, retirement_age, birth_year, birth_month, gender, address,
                latitude, longitude, per_capita_income, yearly_income, total_debt,
                credit_score, num_credit_cards
            )
            SELECT
                NULLIF(id, '')::BIGINT,
                NULLIF(current_age, '')::INTEGER,
                NULLIF(retirement_age, '')::INTEGER,
                NULLIF(birth_year, '')::INTEGER,
                NULLIF(birth_month, '')::INTEGER,
                NULLIF(gender, ''),
                NULLIF(address, ''),
                NULLIF(latitude, '')::DOUBLE PRECISION,
                NULLIF(longitude, '')::DOUBLE PRECISION,
                NULLIF(regexp_replace(per_capita_income, '[$,]', '', 'g'), '')::NUMERIC,
                NULLIF(regexp_replace(yearly_income, '[$,]', '', 'g'), '')::NUMERIC,
                NULLIF(regexp_replace(total_debt, '[$,]', '', 'g'), '')::NUMERIC,
                NULLIF(credit_score, '')::INTEGER,
                NULLIF(num_credit_cards, '')::INTEGER
            FROM stage_aria_users
            ON CONFLICT (id) DO NOTHING
            """
        )
        log(f"Users inserted or already present: {cursor.rowcount:,}")
    conn.commit()


def load_cards(conn) -> None:
    path = CSV_FILES["aria_cards"]
    columns = read_csv_header(path)
    log(f"Loading cards from {path}")
    with conn.cursor() as cursor:
        create_stage_table(cursor, "stage_aria_cards", columns)
        copy_csv_to_stage(cursor, "stage_aria_cards", columns, path)
        cursor.execute(
            """
            INSERT INTO aria_cards (
                id, client_id, card_brand, card_type, card_number, expires, cvv, has_chip,
                num_cards_issued, credit_limit, acct_open_date, year_pin_last_changed,
                card_on_dark_web
            )
            SELECT
                NULLIF(id, '')::BIGINT,
                NULLIF(client_id, '')::BIGINT,
                NULLIF(card_brand, ''),
                NULLIF(card_type, ''),
                NULLIF(card_number, ''),
                NULLIF(expires, ''),
                NULLIF(cvv, ''),
                lower(NULLIF(has_chip, '')) IN ('yes', 'true', '1'),
                NULLIF(num_cards_issued, '')::INTEGER,
                NULLIF(regexp_replace(credit_limit, '[$,]', '', 'g'), '')::NUMERIC,
                NULLIF(acct_open_date, ''),
                NULLIF(year_pin_last_changed, '')::INTEGER,
                lower(NULLIF(card_on_dark_web, '')) IN ('yes', 'true', '1')
            FROM stage_aria_cards
            ON CONFLICT (id) DO NOTHING
            """
        )
        log(f"Cards inserted or already present: {cursor.rowcount:,}")
    conn.commit()


def load_transactions(conn, selected_ids: set[str] | None = None) -> None:
    path = CSV_FILES["aria_transactions"]
    columns = read_csv_header(path)
    if selected_ids is None:
        log(
            f"Loading transactions from {path} in batches of {CSV_BATCH_SIZE:,}. "
            "This can take a while for the full file."
        )
    else:
        log(
            f"Loading {len(selected_ids):,} representative transactions from {path} "
            f"in batches of {CSV_BATCH_SIZE:,}."
        )
    total_seen = 0
    total_inserted = 0
    batch: list[dict[str, str]] = []

    def insert_batch(rows: list[dict[str, str]], processed: int) -> int:
        def operation() -> int:
            with connect() as batch_conn:
                with batch_conn.cursor() as cursor:
                    create_stage_table(cursor, "stage_aria_transactions", columns)
                    copy_dict_batch_to_stage(cursor, "stage_aria_transactions", columns, rows)
                    cursor.execute(
                        """
                        INSERT INTO aria_transactions (
                            id, transaction_date, client_id, card_id, amount, use_chip, merchant_id,
                            merchant_city, merchant_state, zip, mcc, errors
                        )
                        SELECT
                            NULLIF(id, '')::BIGINT,
                            NULLIF(date, '')::TIMESTAMP,
                            NULLIF(client_id, '')::BIGINT,
                            NULLIF(card_id, '')::BIGINT,
                            NULLIF(regexp_replace(amount, '[$,]', '', 'g'), '')::NUMERIC,
                            NULLIF(use_chip, ''),
                            NULLIF(merchant_id, '')::BIGINT,
                            NULLIF(merchant_city, ''),
                            NULLIF(merchant_state, ''),
                            NULLIF(zip, ''),
                            NULLIF(mcc, '')::INTEGER,
                            NULLIF(errors, '')
                        FROM stage_aria_transactions
                        ON CONFLICT (id) DO NOTHING
                        """
                    )
                    inserted = cursor.rowcount
                batch_conn.commit()
                return inserted

        return with_retries(f"Transaction batch ending at row {processed:,}", operation)

    def flush_batch() -> None:
        nonlocal total_inserted
        if not batch:
            return
        total_inserted += insert_batch(batch, total_seen)
        log(f"Transactions processed: {total_seen:,}; inserted this run: {total_inserted:,}")
        batch.clear()

    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if selected_ids is not None and row["id"] not in selected_ids:
                continue
            batch.append(row)
            total_seen += 1
            if len(batch) >= CSV_BATCH_SIZE:
                flush_batch()

    flush_batch()

    log(f"Transactions inserted or already present: {total_inserted:,}")


def load_mcc_codes(conn) -> None:
    import json

    require_file(MCC_FILE)
    log(f"Loading MCC codes from {MCC_FILE}")
    with MCC_FILE.open(encoding="utf-8") as file:
        rows = json.load(file)

    with conn.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO aria_mcc_codes (mcc_code, description)
            VALUES (%s, %s)
            ON CONFLICT (mcc_code) DO NOTHING
            """,
            [(int(code), description) for code, description in rows.items()],
        )
        log(f"MCC codes inserted or already present: {cursor.rowcount:,}")
    conn.commit()


def iter_fraud_label_pairs(path: Path):
    require_file(path)
    buffer = ""
    with path.open("r", encoding="utf-8") as file:
        while True:
            chunk = file.read(1024 * 1024)
            if not chunk:
                break
            buffer += chunk
            last_end = 0
            for match in FRAUD_PAIR_RE.finditer(buffer):
                last_end = match.end()
                yield match.group(1), match.group(2)
            buffer = buffer[last_end:]

    for match in FRAUD_PAIR_RE.finditer(buffer):
        yield match.group(1), match.group(2)


def copy_fraud_batch(cursor, batch: list[tuple[str, str]]) -> None:
    data = StringIO()
    for transaction_id, label in batch:
        is_fraud = "true" if label == "Yes" else "false"
        data.write(f"{transaction_id}\t{label}\t{is_fraud}\n")
    data.seek(0)
    cursor.copy_expert(
        "COPY stage_aria_fraud_labels (transaction_id, label, is_fraud) FROM STDIN WITH (FORMAT TEXT)",
        data,
    )


def load_fraud_labels(
    conn,
    batch_size: int = FRAUD_BATCH_SIZE,
    selected_labels: dict[str, str] | None = None,
) -> None:
    if selected_labels is None:
        log(f"Loading fraud labels from {FRAUD_FILE}")
        label_iterable = iter_fraud_label_pairs(FRAUD_FILE)
    else:
        log(f"Loading {len(selected_labels):,} representative fraud labels")
        label_iterable = selected_labels.items()

    total = 0
    total_inserted = 0
    batch: list[tuple[str, str]] = []

    def insert_batch(rows: list[tuple[str, str]], processed: int) -> int:
        def operation() -> int:
            with connect() as batch_conn:
                with batch_conn.cursor() as cursor:
                    cursor.execute(
                        """
                        CREATE TEMP TABLE stage_aria_fraud_labels (
                            transaction_id BIGINT,
                            label TEXT,
                            is_fraud BOOLEAN
                        )
                        """
                    )
                    copy_fraud_batch(cursor, rows)
                    cursor.execute(
                        """
                        INSERT INTO aria_fraud_labels (transaction_id, label, is_fraud)
                        SELECT transaction_id, label, is_fraud
                        FROM stage_aria_fraud_labels
                        ON CONFLICT (transaction_id) DO NOTHING
                        """
                    )
                    inserted = cursor.rowcount
                batch_conn.commit()
                return inserted

        return with_retries(f"Fraud label batch ending at row {processed:,}", operation)

    for transaction_id, label in label_iterable:
        if transaction_id == "target":
            continue
        batch.append((transaction_id, label))
        if len(batch) >= batch_size:
            total += len(batch)
            total_inserted += insert_batch(batch, total)
            log(f"Fraud labels processed: {total:,}; inserted this run: {total_inserted:,}")
            batch.clear()

    if batch:
        total += len(batch)
        total_inserted += insert_batch(batch, total)

    log(f"Fraud labels inserted or already present: {total_inserted:,}")


def print_counts(conn) -> None:
    with conn.cursor() as cursor:
        for table in (
            "aria_users",
            "aria_cards",
            "aria_transactions",
            "aria_mcc_codes",
            "aria_fraud_labels",
        ):
            cursor.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(q(table)))
            count = cursor.fetchone()[0]
            log(f"{table}: {count:,} rows")


def main() -> int:
    for path in (*CSV_FILES.values(), MCC_FILE, FRAUD_FILE):
        require_file(path)

    selected_ids: set[str] | None = None
    selected_labels: dict[str, str] | None = None
    if SEED_MODE == "representative":
        selected_ids, selected_labels = choose_representative_transaction_ids(REPRESENTATIVE_TX_LIMIT)
    elif SEED_MODE != "full":
        raise RuntimeError("ARIA_SEED_MODE must be either 'full' or 'representative'.")

    conn = connect()
    try:
        create_schema(conn)
        load_users(conn)
        load_cards(conn)
        load_transactions(conn, selected_ids=selected_ids)
        load_mcc_codes(conn)
        load_fraud_labels(conn, selected_labels=selected_labels)
        print_counts(conn)
        log("Seed complete")
        return 0
    except Exception:
        if not conn.closed:
            conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ARIA seed] ERROR: {exc}", file=sys.stderr)
        raise
