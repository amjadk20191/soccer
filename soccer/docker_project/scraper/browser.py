"""
scraper/browser.py  (v7.2)
──────────────────────────
QR scan detection uses TWO parallel signals — whichever fires first wins:

  Signal A — Session/check interception:
    The login page JS polls POST /v4/api/Session/check while the QR is shown.
    • Not scanned : {"succeeded": false, "result": 1231, ...}  (175 bytes)
    • Scanned     : {"succeeded": true,  "data": {...}}         (896 bytes)
    We intercept every response and set qr_confirmed when succeeded=true.

  Signal B — URL navigation to /application/:
    After a successful scan the JS navigates to /application/home, which
    307-redirects to /ar/application/home.  We watch for /application/ in
    the URL as a guaranteed fallback.

Either signal resolving is enough to proceed. This fixes the v7.1 hang:
  • The async response handler could fail silently (body already consumed,
    JSON parse error, Playwright version quirk) leaving qr_confirmed unset.
  • The page still navigated to /application/home (confirmed by the HAR),
    so Signal B always fires even if Signal A doesn't.

BUGS FIXED vs v6
─────────────────
  Bug 1  Stale cookies in headed browser hide QR → clean context, no storage_state.
  Bug 2  wait_for_url fired on stale-cookie /ar redirect (false positive)
         → now requires /application/ which only appears after real login.
  Bug 3  ensure_logged_in accepted /ar (homepage) as "logged in"
         → require /application/ in the URL.
  Bug 4  Session could be saved without verifying it works
         → session saved only after a confirmed-successful signal.

NOTE: myProfile / settings return 401 even in a valid session — the fetcher
ignores those; only history-logs 401 triggers SessionExpiredError.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    Response,
)

from exceptions import (
    AuthenticationError,
    LoginTimeoutError,
    SessionExpiredError,
)

log = logging.getLogger(__name__)

_QR_TIMEOUT_S     = 300          # 5 minutes to scan the QR (seconds)
_QR_TIMEOUT_MS    = 300_000      # same in ms for Playwright's wait_for_url
_SESSION_CHECK    = "session/check"   # lowercase — compared against url.lower()
_DASHBOARD_MARKER = "/application/"  # present only after a real login


class BrowserSession:

    def __init__(self, session_file: str, base_url: str) -> None:
        self._session_file = session_file
        self._base_url     = base_url
        self._playwright: Optional[Playwright]     = None
        self._browser:    Optional[Browser]        = None
        self._context:    Optional[BrowserContext] = None
        self._page:       Optional[Page]           = None

    # ── context manager ───────────────────────────────────────────────────────

    async def __aenter__(self) -> "BrowserSession":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        await self._new_context()
        return self

    async def __aexit__(self, *_) -> None:
        if self._browser:    await self._browser.close()
        if self._playwright: await self._playwright.stop()

    async def _new_context(self, *, no_storage: bool = False) -> None:
        if self._context:
            await self._context.close()
        kwargs: dict = {}
        if not no_storage and os.path.exists(self._session_file):
            kwargs["storage_state"] = self._session_file
        self._context = await self._browser.new_context(**kwargs)
        self._page    = await self._context.new_page()

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("BrowserSession not entered — use `async with`")
        return self._page

    # ── public API ────────────────────────────────────────────────────────────

    async def ensure_logged_in(self, login_url: str, tx_url: str = "") -> None:
        """
        Probe the transactions page.
        Valid session   → /ar/application/transaction  (/application/ present).
        Expired session → redirected to /ar by Next.js middleware.
        """
        if os.path.exists(self._session_file):
            if os.path.getsize(self._session_file) == 0:
                log.warning("Session file is empty — removing")
                os.remove(self._session_file)
                await self._new_context()

        probe_url = tx_url or f"{self._base_url}/ar/application/transaction"

        try:
            await self._page.goto(probe_url, wait_until="networkidle")
            await self._page.wait_for_timeout(2_000)
        except Exception as exc:
            raise AuthenticationError(f"Could not reach {probe_url}: {exc}") from exc

        current = self._page.url

        if _DASHBOARD_MARKER in current:
            log.info("Session valid — no QR scan needed")
            print("[✓] Session restored — no QR scan needed\n")
            return

        log.info("Not authenticated (landed at %s) — starting QR login", current)
        await self._do_qr_login(login_url)

    async def relogin_if_needed(self, login_url: str) -> None:
        if "/auth/login" in self._page.url:
            log.warning("Page drifted to /auth/login — session expired")
            raise SessionExpiredError("Browser redirected to /auth/login")

    async def handle_relogin(self, login_url: str) -> None:
        """Called by main.py after catching SessionExpiredError."""
        await self._new_context(no_storage=True)
        await self._do_qr_login(login_url)

    # ── QR login ──────────────────────────────────────────────────────────────

    async def _do_qr_login(self, login_url: str) -> None:
        """
        Open a headed Chromium window. Wait for QR scan using two parallel
        signals, whichever fires first:
          A) Session/check response with succeeded=true
          B) Page URL navigates to /application/

        v7.1 used only Signal A, but the async response handler could fail
        silently (body already consumed, etc.), leaving qr_confirmed never set
        and the browser open for the full 5-minute timeout.  Signal B is always
        reliable because the HAR confirms the browser navigates to
        /application/home immediately after a successful scan.
        """
        print("\n" + "=" * 60)
        print("  Opening ShamCash login page in a browser window.")
        print("  Scan the QR code with your Android ShamCash app.")
        print(f"\n  URL: {login_url}")
        print("=" * 60 + "\n")

        headed_pw      = await async_playwright().start()
        headed_browser = await headed_pw.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )

        # Bug 1 fix: NO storage_state — stale cookies would instantly redirect
        # /ar/auth/login → /ar, hiding the QR entirely.
        headed_context = await headed_browser.new_context()
        headed_page    = await headed_context.new_page()

        # Signal A: Session/check succeeded=true
        qr_via_api = asyncio.Event()

        async def _on_response(response: Response) -> None:
            try:
                if _SESSION_CHECK not in response.url.lower():
                    return
                if response.status != 200:
                    return
                body = await response.json()
                if body.get("succeeded"):
                    log.info("Signal A: Session/check succeeded=true")
                    qr_via_api.set()
            except Exception as exc:
                log.debug("_on_response error (non-fatal): %s", exc)

        headed_page.on("response", _on_response)

        try:
            await headed_page.goto(login_url, wait_until="networkidle")
            await headed_page.wait_for_timeout(3_000)   # let QR canvas render

            print("[→] Browser open — scan the QR with your phone...\n")

            # Run Signal A and Signal B concurrently.
            # Signal B (URL change) is always reliable — it's the last step in
            # the login flow regardless of whether Signal A fires.
            task_api = asyncio.create_task(qr_via_api.wait())
            task_url = asyncio.create_task(
                headed_page.wait_for_url(
                    lambda url: _DASHBOARD_MARKER in url,
                    timeout=_QR_TIMEOUT_MS,
                )
            )

            done, pending = await asyncio.wait(
                [task_api, task_url],
                timeout=_QR_TIMEOUT_S,
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel whichever signal didn't fire
            for task in pending:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

            if not done:
                raise LoginTimeoutError("QR code was not scanned within 5 minutes")

            # Check if the completed task raised an exception
            for task in done:
                exc = task.exception()
                if exc is not None:
                    raise LoginTimeoutError(f"QR wait failed: {exc}") from exc

            which = "Session/check API" if task_api in done else "URL navigation"
            log.info("QR scan confirmed via %s — saving session", which)

            # Give the frontend JS a moment to finish setting cookies
            await headed_page.wait_for_timeout(1_500)

            os.makedirs(os.path.dirname(self._session_file) or ".", exist_ok=True)
            await headed_context.storage_state(path=self._session_file)
            log.info("Session saved → %s", self._session_file)

        except LoginTimeoutError:
            raise
        except AuthenticationError:
            raise
        except Exception as exc:
            raise LoginTimeoutError(f"QR login error: {exc}") from exc
        finally:
            headed_page.remove_listener("response", _on_response)
            await headed_browser.close()
            await headed_pw.stop()

        print(f"[✓] Logged in! Session saved → {self._session_file}\n")

        # Reload saved session into the headless background context
        await self._new_context()
        try:
            await self._page.goto(self._base_url, wait_until="networkidle")
        except Exception as exc:
            raise AuthenticationError(
                f"Could not reach {self._base_url} after login: {exc}"
            ) from exc
