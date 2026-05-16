#!/usr/bin/env python3
"""
main.py  —  shamcash.sy transaction scraper  (v6)

LOGIN FLOW
──────────
- First run   : A real Chromium window opens at shamcash.sy/ar/auth/login.
                Scan the QR with your Android ShamCash app.
                Window closes automatically. Session saved to SESSION_FILE.

- Later runs  : Session restored from SESSION_FILE — no QR scan needed.

- If session  : Another browser window opens for re-scan, then resumes.
  expires       (The 2-minute access token is refreshed by the site's own
                 refresh logic; we only re-scan when the full session dies.)

KEY FIX in v6
─────────────
myProfile / settings always return 401 — even in a valid session.
v5 treated those 401s as session-expiry → forced a QR scan every cycle.
v6 only treats 401 on Transaction/history-logs as session-expiry.
"""

import asyncio
import logging
import os
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from config import load_config
from db import create_repository
from exceptions import (
    AuthenticationError,
    DatabaseError,
    LoginTimeoutError,
    ParseError,
    ScrapingError,
    SessionExpiredError,
)
from models import Transaction
from scraper import BrowserSession, fetch_transactions

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
    datefmt= "%H:%M:%S",
)
log = logging.getLogger(__name__)

_MAX_SCRAPE_FAILURES = 5


def _fmt(tx: Transaction) -> str:
    label = "IN " if tx.direction == "+" else "OUT"
    return (
        f"  [{label}]  "
        f"id:{tx.tx_id:<12}  "
        f"from:{tx.name:<30}  "
        f"amount:{str(tx.amount):<10} {tx.currency:<4}  "
        f"date:{tx.date}  time:{tx.time}"
    )


def _print_batch(transactions: list[Transaction], new_count: int) -> None:
    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'═' * 80}")
    print(f"  {len(transactions)} transaction(s)  │  {new_count} new  │  {now}")
    print(f"{'═' * 80}")
    for tx in transactions:
        print(_fmt(tx))
    print(f"{'═' * 80}\n")


async def main() -> None:
    cfg       = load_config()
    login_url = f"{cfg.base_url}/ar/auth/login"
    tx_url    = f"{cfg.base_url}/ar/application/transaction"

    async with BrowserSession(cfg.session_file, cfg.base_url) as session:
        await _run(session, cfg, login_url, tx_url)


async def _run(session: BrowserSession, cfg, login_url: str, tx_url: str) -> None:

    # ── initial login / session restore ──────────────────────────────────────
    try:
        await session.ensure_logged_in(login_url, tx_url)
    except AuthenticationError as exc:
        log.critical("Cannot reach site: %s", exc)
        print(f"\n[✗] {exc}\n    Check BASE_URL and network.\n")
        return
    except LoginTimeoutError:
        print("\n[✗] QR scan timed out. Restart and try again.\n")
        return

    # ── database ──────────────────────────────────────────────────────────────
    try:
        repo = create_repository(cfg.database_url, cfg.db_table)
    except DatabaseError as exc:
        log.critical("DB init failed: %s", exc)
        print(f"\n[✗] Database error: {exc}\n")
        return

    with repo:
        print(f"[→] Polling every {cfg.poll_interval}s  (Ctrl+C to stop)\n")
        scrape_failures = 0

        while True:
            try:
                # Fetch — raises SessionExpiredError if history-logs → 401
                transactions = await fetch_transactions(session.page, tx_url)
                scrape_failures = 0

                # Belt-and-suspenders URL check
                await session.relogin_if_needed(login_url)

                # Save to DB
                try:
                    new_count = repo.save_many(transactions)
                    _print_batch(transactions, new_count)
                except DatabaseError as exc:
                    log.error("DB write failed (retry next cycle): %s", exc)
                    print(f"[!] DB error: {exc}")

            except SessionExpiredError:
                print("\n[!] Session expired — please scan the QR code again.\n")
                try:
                    await session.handle_relogin(login_url)
                    scrape_failures = 0
                except LoginTimeoutError:
                    print("[!] Re-login timed out — will retry next cycle.")
                except AuthenticationError as exc:
                    log.error("Re-login failed: %s", exc)
                    print(f"[!] {exc}  — retrying in 30 s")
                    await asyncio.sleep(30)

            except ScrapingError as exc:
                scrape_failures += 1
                print(f"[!] Scrape failed ({scrape_failures}/{_MAX_SCRAPE_FAILURES}): {exc}")
                if scrape_failures >= _MAX_SCRAPE_FAILURES:
                    log.critical("Too many consecutive scrape failures — stopping")
                    print(
                        f"\n[✗] Scraping failed {_MAX_SCRAPE_FAILURES} times in a row.\n"
                        "    Page structure may have changed.\n"
                    )
                    return

            except ParseError as exc:
                log.warning("Parse error (row skipped): %s", exc)
                print(f"[~] Parse warning: {exc}")

            except KeyboardInterrupt:
                print("\n[→] Stopped by user.")
                return

            except Exception as exc:
                log.exception("Unexpected error: %s", exc)
                print(f"[!] Unexpected error: {exc!r}  — retrying in 10 s")
                await asyncio.sleep(10)
                continue

            await asyncio.sleep(cfg.poll_interval)


if __name__ == "__main__":
    asyncio.run(main())
