from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal


@dataclass(frozen=True)
class Transaction:
    """
    Immutable domain object — no ORM, no DB logic, just data.
    Matches the Django model in django_app/models.py column-for-column.
    """
    tx_id:     str       # site's own transaction ID (PK)
    name:      str       # sender / counterparty name
    date:      date
    time:      time
    amount:    Decimal
    currency:  str       # e.g. 'SYP'
    direction: str       # '+' (incoming) | '-' (outgoing)
    notes:     str
