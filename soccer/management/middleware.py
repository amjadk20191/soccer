import sys
import traceback
import threading
import textwrap
import httpx
from django.conf import settings
from django.core.signals import got_request_exception
from .models import RequestErrorLog


class ErrorLoggingMiddleware:

    SAFE_HEADERS = {
        "content-type", "accept", "accept-language",
        "accept-encoding", "host", "origin", "referer",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            request._cached_body = request.body
        except Exception:
            request._cached_body = b""

        # ✅ Store exc_info on the request the moment the exception fires —
        # before Django/DRF swallows it and converts it to a 500 response
        request._exc_info = (None, None, None)

        def _capture(sender, **kwargs):
            request._exc_info = sys.exc_info()

        got_request_exception.connect(_capture, weak=False)

        try:
            response = self.get_response(request)
        except Exception:
            # Unhandled — Django never caught it at all
            request._exc_info = sys.exc_info()
            log = self._save(request)
            if log:
                self._notify_telegram_async(log)
            raise
        finally:
            got_request_exception.disconnect(_capture)

        if response is not None and response.status_code >= 500:
            log = self._save(request)
            if log:
                self._notify_telegram_async(log)

        return response

    # ── Persist ───────────────────────────────────────────────────────────

    def _save(self, request):
        try:
            exc_type, exc_value, exc_tb = getattr(request, "_exc_info", (None, None, None))

            tb_text = (
                "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
                if exc_tb else ""
            )

            return RequestErrorLog.objects.create(
                method          = request.method,
                path            = request.path,
                query_params    = request.META.get("QUERY_STRING", ""),
                request_body    = self._body(request),
                request_headers = self._headers(request),
                ip_address      = self._ip(request),
                user_agent      = request.META.get("HTTP_USER_AGENT", ""),
                user_id         = self._user(request),
                exception_type  = exc_type.__name__ if exc_type  else "",
                exception_msg   = str(exc_value)    if exc_value else "",
                traceback       = tb_text,
                status_code     = 500,
            )
        except Exception:
            return None

    # ── Telegram ──────────────────────────────────────────────────────────

    def _notify_telegram_async(self, log: RequestErrorLog):
        thread = threading.Thread(
            target=self._send_telegram,
            args=(log,),
            daemon=True,
        )
        thread.start()

    def _send_telegram(self, log: RequestErrorLog):
        token   = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None)

        if not token or not chat_id:
            return

        tb_preview = textwrap.shorten(log.traceback, width=1500, placeholder="\n…[truncated]")

        message = (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🚨  *SERVER ERROR — 500*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

            f"🕐  *When*\n"
            f"┗ `{log.created_at.strftime('%Y-%m-%d  %H:%M:%S')} UTC`\n\n"

            f"📡  *Request*\n"
            f"┣ Method  →  `{log.method}`\n"
            f"┣ Path    →  `{log.path}`\n"
            f"┗ Query   →  `{log.query_params or '—'}`\n\n"

            f"👤  *Who*\n"
            f"┣ User    →  `{log.user_id or 'anonymous'}`\n"
            f"┣ IP      →  `{log.ip_address or '—'}`\n"
            f"┗ Agent   →  `{log.user_agent[:60] or '—'}`\n\n"

            f"💥  *Exception*\n"
            f"┣ Type    →  `{log.exception_type}`\n"
            f"┗ Msg     →  `{log.exception_msg}`\n\n"

            f"🔍  *Traceback*\n"
            f"```\n{tb_preview}\n```\n\n"

            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🆔  `{log.id}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

        try:
            with httpx.Client(timeout=5) as client:
                client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={
                        "chat_id":    chat_id,
                        "text":       message,
                        "parse_mode": "Markdown",
                    },
                )
        except Exception:
            pass

    # ── Helpers ───────────────────────────────────────────────────────────

    def _body(self, request) -> str:
        try:
            return getattr(request, "_cached_body", b"").decode("utf-8", errors="replace")[:10_000]
        except Exception:
            return ""

    def _headers(self, request) -> dict:
        headers = {}
        for key, value in request.META.items():
            if key.startswith("HTTP_"):
                name = key[5:].replace("_", "-").lower()
                if name in self.SAFE_HEADERS:
                    headers[name] = value
        return headers

    def _ip(self, request) -> str | None:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        return forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")

    def _user(self, request) -> str:
        try:
            user = getattr(request, "user", None)
            return str(user.pk) if user and user.is_authenticated else ""
        except Exception:
            return ""