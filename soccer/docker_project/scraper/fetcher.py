"""
scraper/fetcher.py
──────────────────
Fetches transactions from shamcash.sy.

REAL API (confirmed from HAR)
──────────────────────────────
  POST https://api.shamcash.sy/v4/api/Transaction/history-logs
  Body: {"limit": 10, "next": {"tags": ["last-transactions"]}}
  Auth: HttpOnly cookies — no Authorization header needed
  Required headers: e: true  |  lang: ar  |  x-requested-with: XMLHttpRequest

SESSION EXPIRY DETECTION  ← KEY FIX
──────────────────────────────────────
The page NEVER redirects to /auth/login when the JWT expires.
Instead, api.shamcash.sy returns 401 on SOME endpoints — but NOT all:

  • myProfile, settings, accountInfo  → ALWAYS return 401, even after a
    fresh login (they need a different/higher auth level).
    The old code treated those 401s as session-expiry → forced a QR
    re-scan every single poll cycle. That was the main bug.

  • Transaction/history-logs → returns 401 ONLY when the session is truly
    expired. THIS is the only 401 that must trigger SessionExpiredError.

STRATEGIES (tried in order)
─────────────────────────────
  1. Direct API call via page.evaluate() — fastest, attaches cookies automatically.
  2. XHR intercept on navigation — fallback.
     Fixed: case-insensitive URL match ("transaction" vs "Transaction").
  3. DOM table / card scraping — last resort.
"""

import logging

from playwright.async_api import Page

from exceptions import SessionExpiredError
from scraper.parser import build_transaction
from models import Transaction

log = logging.getLogger(__name__)

_API_BASE    = "https://api.shamcash.sy"
_TX_ENDPOINT = f"{_API_BASE}/v4/api/Transaction/history-logs"

# Endpoints that legitimately return 401 even in a valid session.
# 401 on these must NOT trigger SessionExpiredError.
_IGNORED_401_FRAGMENTS = (
    "myprofile",
    "settings",
    "accountinfo",
    "/account",
    "/profile",
)


def _is_ignorable_401(url: str) -> bool:
    url_lower = url.lower()
    return any(frag in url_lower for frag in _IGNORED_401_FRAGMENTS)


def _is_history_logs(url: str) -> bool:
    url_lower = url.lower()
    return "transaction" in url_lower and "history" in url_lower


def _check_for_login_redirect(page: Page, context: str = "fetch") -> None:
    if "/auth/login" in page.url:
        raise SessionExpiredError(
            f"Redirected to /auth/login during {context} — session expired"
        )


# ── strategy 1 : direct API call via page.evaluate() ─────────────────────────

async def _fetch_via_direct_api(page: Page, transactions_url: str) -> list[dict]:
    """
    POST history-logs from inside the browser context so HttpOnly cookies
    are attached automatically. 401 here = truly expired session.
    """
    if "application/transaction" not in page.url:
        await page.goto(transactions_url, wait_until="networkidle")
        await page.wait_for_timeout(2_000)
        _check_for_login_redirect(page, "navigation")

    result = await page.evaluate("""
        async () => {
            const resp = await fetch("https://api.shamcash.sy/v4/api/Transaction/history-logs", {
                method: "POST",
                credentials: "include",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "e": "true",
                    "lang": "ar",
                    "x-requested-with": "XMLHttpRequest"
                },
                body: JSON.stringify({
                    "limit": 10,
                    "next": {"tags": ["last-transactions"]}
                })
            });
            const status = resp.status;
            let body = null;
            try { body = await resp.json(); } catch(e) {}
            return { status, body };
        }
    """)

    status = result.get("status")
    body   = result.get("body")

    log.debug("Direct API → status=%s", status)

    if status == 401:
        log.warning("history-logs returned 401 → session expired")
        raise SessionExpiredError(
            "POST history-logs returned 401 — JWT/session expired"
        )

    if not body:
        return []

    return _parse_api_body(body)


# ── strategy 2 : XHR intercept ───────────────────────────────────────────────

async def _fetch_via_intercept(page: Page, transactions_url: str) -> list[dict]:
    """
    Listen to all api.shamcash.sy responses during navigation.
    Only raise SessionExpiredError when history-logs itself returns 401.
    Ignore 401 on myProfile / settings / etc.
    """
    api_items: list[dict] = []
    session_expired = False

    async def on_response(response):
        nonlocal session_expired
        url = response.url

        if _API_BASE not in url:
            return

        if response.status == 401:
            if _is_history_logs(url):
                log.warning("Intercepted 401 on history-logs → session expired")
                session_expired = True
            else:
                log.debug("Ignoring expected 401 on: %s", url)
            return

        # Case-insensitive: real URL is "Transaction/history-logs"
        if not _is_history_logs(url) or response.status != 200:
            return

        try:
            data = await response.json()
        except Exception:
            return

        items = _extract_items(data)
        if items:
            api_items.extend(items)

    page.on("response", on_response)
    try:
        await page.goto(transactions_url, wait_until="networkidle")
        await page.wait_for_timeout(2_500)
    finally:
        page.remove_listener("response", on_response)

    if session_expired:
        raise SessionExpiredError("history-logs returned 401 — session expired")

    _check_for_login_redirect(page, "XHR intercept")

    return _parse_api_items(api_items) if api_items else []


# ── strategy 3 : DOM table / card fallback ───────────────────────────────────

async def _fetch_via_dom(page: Page, transactions_url: str) -> list[dict]:
    if "application/transaction" not in page.url:
        await page.goto(transactions_url, wait_until="networkidle")
        await page.wait_for_timeout(1_500)

    _check_for_login_redirect(page, "DOM scrape")

    raw_list = []

    # Desktop table
    rows = await page.query_selector_all("table tbody tr")
    for row in rows:
        cells = await row.query_selector_all("td")
        if len(cells) < 4:
            continue
        name_el = await cells[0].query_selector("span.font-semibold")
        if name_el:
            name = (await name_el.inner_text()).strip()
        else:
            lines = (await cells[0].inner_text()).strip().splitlines()
            name  = next((ln.strip() for ln in lines if ln.strip()), "")

        raw_id     = (await cells[1].inner_text()).strip().lstrip("#")
        date_raw   = (await cells[2].inner_text()).strip()
        amount_raw = (await cells[3].inner_text()).strip()
        notes      = (await cells[4].inner_text()).strip() if len(cells) >= 5 else ""

        if raw_id:
            raw_list.append({
                "id": raw_id, "name": name,
                "date_raw": date_raw, "amount_raw": amount_raw, "notes": notes,
            })

    if raw_list:
        return raw_list

    # Mobile cards
    cards = await page.query_selector_all(".block.md\\:hidden .flex.flex-col")
    for card in cards:
        spans = await card.query_selector_all("span")
        texts = [(await s.inner_text()).strip() for s in spans]
        tx_id = amount_raw = date_raw = name = ""
        for t in texts:
            if t.startswith("#") and t[1:].split()[0].isdigit():
                tx_id = t.lstrip("#")
            elif t and t[0] in ("+", "-") and any(c.isdigit() for c in t):
                amount_raw = t
            elif " - " in t and len(t) > 15:
                date_raw = t
            elif t and not name:
                name = t
        if tx_id:
            raw_list.append({
                "id": tx_id, "name": name,
                "date_raw": date_raw, "amount_raw": amount_raw, "notes": "",
            })

    return raw_list


# ── parsing helpers ───────────────────────────────────────────────────────────

def _extract_items(data) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "data", "transactions", "items", "logs"):
            val = data.get(key)
            if isinstance(val, list):
                return val
    return []


def _parse_api_items(api_items: list) -> list[dict]:
    raw_list = []
    for tx in api_items:
        raw_amount = str(tx.get("amount") or tx.get("value") or "")
        sign_field = str(tx.get("type") or tx.get("direction") or "")

        if raw_amount and raw_amount[0] not in ("+", "-"):
            if any(k in sign_field.lower() for k in ("in", "receive", "credit")):
                raw_amount = "+" + raw_amount
            elif any(k in sign_field.lower() for k in ("out", "send", "debit")):
                raw_amount = "-" + raw_amount

        currency   = tx.get("currency", "SYP")
        amount_raw = f"{raw_amount} {currency}".strip()

        raw_list.append({
            "id":         str(tx.get("id") or tx.get("ref") or ""),
            "name":       (tx.get("from") or tx.get("sender")
                           or tx.get("from_user") or tx.get("name") or "N/A"),
            "date_raw":   (tx.get("date") or tx.get("created_at")
                           or tx.get("timestamp") or ""),
            "amount_raw": amount_raw,
            "notes":      tx.get("note") or tx.get("description") or "",
        })
    return raw_list


def _parse_api_body(body) -> list[dict]:
    items = _extract_items(body)
    return _parse_api_items(items) if items else []


# ── public entry point ────────────────────────────────────────────────────────

async def fetch_transactions(page: Page, transactions_url: str) -> list[Transaction]:
    """
    Try three strategies in order.
    Raises SessionExpiredError ONLY when Transaction/history-logs returns 401.
    """
    for strat_name, strategy in (
        ("direct-api",    lambda: _fetch_via_direct_api(page, transactions_url)),
        ("xhr-intercept", lambda: _fetch_via_intercept(page, transactions_url)),
        ("dom-scrape",    lambda: _fetch_via_dom(page, transactions_url)),
    ):
        try:
            raw_list = await strategy()
        except SessionExpiredError:
            raise
        except Exception as exc:
            log.warning("Strategy %s failed: %s — trying next", strat_name, exc)
            continue

        if raw_list:
            transactions = [build_transaction(r) for r in raw_list]
            result = [tx for tx in transactions if tx is not None]
            log.info("Strategy %s → %d transactions", strat_name, len(result))
            return result

    return []
