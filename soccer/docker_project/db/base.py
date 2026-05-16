from abc import ABC, abstractmethod
from typing import Sequence

from models import Transaction


class TransactionRepository(ABC):
    """
    Port (in hexagonal-architecture terms).
    The scraper talks ONLY to this interface — never to a concrete DB driver.
    """

    @abstractmethod
    def save_many(self, transactions: Sequence[Transaction]) -> int:
        """
        Upsert-style insert: skip rows whose tx_id already exists.
        Returns the number of rows actually inserted (new ones only).
        """
        ...

    @abstractmethod
    def close(self) -> None: ...

    # ── context-manager support ──────────────────────────────────────────────
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
