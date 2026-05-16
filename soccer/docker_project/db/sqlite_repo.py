import sqlite3
from typing import Sequence

from db.base import TransactionRepository
from models import Transaction


class SQLiteTransactionRepository(TransactionRepository):
    """
    Adapter for SQLite.

    • Uses INSERT OR IGNORE so duplicate tx_id rows are silently skipped.
    • CREATE TABLE IF NOT EXISTS lets you run the scraper standalone (without
      first running Django migrations), while still being harmless when the
      Django-managed table already exists.
    • Column types mirror what Django's SQLite backend generates.
    """

    def __init__(self, db_path: str, table: str) -> None:
        self._conn  = sqlite3.connect(db_path, check_same_thread=False)
        self._table = table
        self._ensure_table()

    # ── schema bootstrap ─────────────────────────────────────────────────────

    def _ensure_table(self) -> None:
        self._conn.execute(f"""
            CREATE TABLE IF NOT EXISTS "{self._table}" (
                tx_id     TEXT         NOT NULL PRIMARY KEY,
                name      TEXT         NOT NULL,
                date      TEXT         NOT NULL,
                time      TEXT         NOT NULL,
                amount    TEXT         NOT NULL,
                currency  TEXT         NOT NULL DEFAULT 'SYP',
                direction TEXT         NOT NULL,
                notes     TEXT         NOT NULL DEFAULT '',
                scraped_at TEXT        NOT NULL DEFAULT (datetime('now'))
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
                tx.date.isoformat(),
                tx.time.isoformat(),
                str(tx.amount),
                tx.currency,
                tx.direction,
                tx.notes,
            )
            for tx in transactions
        ]

        cursor = self._conn.executemany(
            f"""
            INSERT OR IGNORE INTO "{self._table}"
                (tx_id, name, date, time, amount, currency, direction, notes)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        self._conn.commit()
        return cursor.rowcount  # rows actually inserted (skips are excluded)

    def close(self) -> None:
        self._conn.close()
