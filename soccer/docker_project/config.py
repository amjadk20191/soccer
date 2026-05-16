import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    database_url:  str   # sqlite:///db.sqlite3  |  postgresql://user:pass@host/db
    poll_interval: int   # seconds between scrape cycles
    session_file:  str   # Playwright session persistence
    base_url:      str
    db_table:      str   # Django generates: <app_label>_<model_name>


def load_config() -> Config:
    return Config(
        database_url  = os.getenv("DATABASE_URL",   "sqlite:///db.sqlite3"),
        poll_interval = int(os.getenv("POLL_INTERVAL", "60")),
        session_file  = os.getenv("SESSION_FILE",   "shamcash_session.json"),
        base_url      = os.getenv("BASE_URL",       "https://shamcash.sy"),
        db_table      = os.getenv("DB_TABLE",       "transactions_transaction"),
    )