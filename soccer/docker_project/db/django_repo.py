"""
db/django_repo.py
─────────────────
Repository that writes through Django's ORM.

Django is bootstrapped once on first use via _setup_django().
The model is resolved dynamically from DJANGO_APP_LABEL + DJANGO_MODEL_NAME
so you never hard-code an import path here.

Raises
──────
DatabaseError  on any Django / DB-level error
"""

from __future__ import annotations

import logging
import os
from typing import Sequence

from exceptions import DatabaseError
from models import Transaction as ScraperTransaction
from db.base import TransactionRepository

log = logging.getLogger(__name__)

_django_ready = False


def _setup_django() -> None:
    global _django_ready
    if _django_ready:
        return

    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")
    if not settings_module:
        raise DatabaseError(
            "DJANGO_SETTINGS_MODULE is not set. "
            "Add it to your .env, e.g.  DJANGO_SETTINGS_MODULE=myproject.settings"
        )

    try:
        import django
        django.setup()
        _django_ready = True
        log.info("Django bootstrapped with settings: %s", settings_module)
    except Exception as exc:
        raise DatabaseError(
            f"django.setup() failed — check DJANGO_SETTINGS_MODULE: {exc}"
        ) from exc


def _get_model(app_label: str, model_name: str):
    """
    Resolve the Django model class at runtime.
    Equivalent to  from <app_label>.models import <model_name>
    but works without a hard-coded import.
    """
    from django.apps import apps          # noqa: PLC0415
    try:
        return apps.get_model(app_label, model_name)
    except LookupError as exc:
        raise DatabaseError(
            f"Django model '{app_label}.{model_name}' not found. "
            f"Check DJANGO_APP_LABEL and DJANGO_MODEL_NAME in your .env."
        ) from exc


class DjangoTransactionRepository(TransactionRepository):
    """
    Writes transactions through Django's ORM using bulk_create with
    ignore_conflicts=True  —  safe to re-scrape without duplicates.

    Expects the Django model to have at least these fields
    (names are configurable via DJANGO_MODEL_FIELD_* env vars):

        tx_id      CharField / primary_key or unique
        name       CharField
        date       DateField
        time       TimeField
        amount     DecimalField
        currency   CharField
        direction  CharField  ('+' or '-')
        notes      TextField
    """

    # Default field-name mapping  (override via env if your model uses different names)
    _FIELD_MAP = {
        "tx_id":     os.getenv("DJANGO_FIELD_TX_ID",    "tx_id"),
        "name":      os.getenv("DJANGO_FIELD_NAME",     "name"),
        "date":      os.getenv("DJANGO_FIELD_DATE",     "date"),
        "time":      os.getenv("DJANGO_FIELD_TIME",     "time"),
        "amount":    os.getenv("DJANGO_FIELD_AMOUNT",   "amount"),
        "currency":  os.getenv("DJANGO_FIELD_CURRENCY", "currency"),
        "direction": os.getenv("DJANGO_FIELD_DIRECTION","direction"),
        "notes":     os.getenv("DJANGO_FIELD_NOTES",    "notes"),
    }

    def __init__(self, app_label: str, model_name: str) -> None:
        _setup_django()
        self._Model = _get_model(app_label, model_name)
        log.info(
            "DjangoTransactionRepository ready → %s.%s  (table: %s)",
            app_label, model_name,
            self._Model._meta.db_table,
        )

    # ── repository interface ──────────────────────────────────────────────────

    def save_many(self, transactions: Sequence[ScraperTransaction]) -> int:
        if not transactions:
            return 0

        fm = self._FIELD_MAP

        # Build Django model instances from our scraper Transaction dataclass
        instances = []
        for tx in transactions:
            kwargs = {
                fm["tx_id"]:     tx.tx_id,
                fm["name"]:      tx.name,
                fm["date"]:      tx.date,        # already a datetime.date
                fm["time"]:      tx.time,        # already a datetime.time
                fm["amount"]:    tx.amount,      # already a Decimal
                fm["currency"]:  tx.currency,
                fm["direction"]: tx.direction,
                fm["notes"]:     tx.notes,
            }
            instances.append(self._Model(**kwargs))

        try:
            created = self._Model.objects.bulk_create(
                instances,
                ignore_conflicts=True,   # skip rows whose tx_id already exists
            )
            return len(created)
        except Exception as exc:
            raise DatabaseError(
                f"bulk_create failed on {self._Model._meta.db_table}: {exc}"
            ) from exc

    def close(self) -> None:
        pass   # Django manages its own connection pool