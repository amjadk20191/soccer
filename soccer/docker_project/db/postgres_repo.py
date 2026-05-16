from typing import Sequence

import psycopg2
import psycopg2.extras

from db.base import TransactionRepository
from models import Transaction


class PostgresTransactionRepository(TransactionRepository):
    """
    Adapter for PostgreSQL.

    • Uses INSERT … ON CONFLICT (tx_id) DO NOTHING so re-scraping is safe.
    • RETURNING tx_id lets us count exactly how many rows were new.
    • execute_values batches the whole list in a single round-trip.
    • Column types match what Django's PostgreSQL backend generates exactly.
    """

    def __init__(self, dsn: str, table: str) -> None:
        self._conn  = psycopg2.connect(dsn)
        self._table = table
        self._ensure_table()

    # ── schema bootstrap ─────────────────────────────────────────────────────

    def _ensure_table(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS "{self._table}" (
                    tx_id      VARCHAR(50)     NOT NULL PRIMARY KEY,
                    name       VARCHAR(255)    NOT NULL,
                    date       DATE            NOT NULL,
                    time       TIME            NOT NULL,
                    amount     NUMERIC(15, 2)  NOT NULL,
                    currency   VARCHAR(10)     NOT NULL DEFAULT 'SYP',
                    direction  CHAR(1)         NOT NULL,
                    notes      TEXT            NOT NULL DEFAULT '',
                    scraped_at TIMESTAMPTZ     NOT NULL DEFAULT NOW()
                )
            """)
        self._conn.commit()

    # ── repository interface ─────────────────────────────────────────────────

    def save_many(self, transactions: Sequence[Transaction]) -> int:
        if not transactions:
            return 0

        rows = [
            (
                tx.tx_id,
                tx.name,
                tx.date,      # psycopg2 maps date → DATE natively
                tx.time,      # psycopg2 maps time → TIME natively
                tx.amount,    # psycopg2 maps Decimal → NUMERIC natively
                tx.currency,
                tx.direction,
                tx.notes,
            )
            for tx in transactions
        ]

        with self._conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                f"""
                INSERT INTO "{self._table}"
                    (tx_id, name, date, time, amount, currency, direction, notes)
                VALUES %s
                ON CONFLICT (tx_id) DO NOTHING
                RETURNING tx_id
                """,
                rows,
            )
            inserted = len(cur.fetchall())

        self._conn.commit()
        return inserted

    def close(self) -> None:
        self._conn.close()
