"""
db/factory.py
─────────────
Picks the right repository based on environment variables.

Priority
────────
1.  DJANGO_SETTINGS_MODULE is set  →  DjangoTransactionRepository
        Uses the real Django ORM / model.
        Requires: DJANGO_APP_LABEL, DJANGO_MODEL_NAME

2.  DATABASE_URL starts with postgresql://  →  PostgresTransactionRepository
        Raw psycopg2 writes to Postgres.
        Requires: DATABASE_URL, DB_TABLE

3.  Anything else (default)  →  SQLiteTransactionRepository
        Raw sqlite3 writes to the path in DATABASE_URL.
        Requires: DATABASE_URL  (e.g. sqlite:///data/db.sqlite3 or a plain path)

Raises
──────
DatabaseError  if required env vars are missing or the connection fails
"""

from __future__ import annotations

import os
from contextlib import contextmanager

from db.base import TransactionRepository
from exceptions import DatabaseError


def create_repository(database_url: str, db_table: str) -> TransactionRepository:
    """
    Return the appropriate repository instance.

    Call inside  `with create_repository(...) as repo:`
    so .close() is always called.
    """
    # ── 1. Django ORM ─────────────────────────────────────────────────────────
    if os.environ.get("DJANGO_SETTINGS_MODULE"):
        app_label  = os.environ.get("DJANGO_APP_LABEL")
        model_name = os.environ.get("DJANGO_MODEL_NAME", "Transaction")

        if not app_label:
            raise DatabaseError(
                "DJANGO_SETTINGS_MODULE is set but DJANGO_APP_LABEL is missing. "
                "Add  DJANGO_APP_LABEL=<your_app_name>  to your .env"
            )

        from db.django_repo import DjangoTransactionRepository
        return DjangoTransactionRepository(app_label, model_name)

    # ── 2. PostgreSQL ─────────────────────────────────────────────────────────
    if database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
        from db.postgres_repo import PostgresTransactionRepository
        return PostgresTransactionRepository(database_url, db_table)

    # ── 3. SQLite (default) ───────────────────────────────────────────────────
    # Accept both  sqlite:///path/to/db.sqlite3  and  a plain file path
    db_path = (
        database_url
        .removeprefix("sqlite:///")
        .removeprefix("sqlite://")
    )
    from db.sqlite_repo import SQLiteTransactionRepository
    return SQLiteTransactionRepository(db_path, db_table)


@contextmanager
def repo_context(database_url: str, db_table: str):
    """
    Context manager wrapper so `with repo_context(...) as repo:` works.
    Guarantees repo.close() even if an exception is raised.
    """
    repo = create_repository(database_url, db_table)
    try:
        yield repo
    finally:
        repo.close()