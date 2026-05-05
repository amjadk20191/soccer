# core/services/notification_service.py
import json
import time
import base64
import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings
from ..models import User,Notification
from ..selectors import UserDeviceSelector


class FCMTokenManager:
    _access_token: str = None
    _token_expiry: float = 0

    @classmethod
    def get_access_token(cls) -> str:
        # always refresh if expired or not set
        if not cls._access_token or time.time() >= cls._token_expiry:
            cls._access_token, cls._token_expiry = cls._fetch_access_token()
        return cls._access_token

    @classmethod
    def invalidate_token(cls):
        # force refresh on next call
        cls._access_token = None
        cls._token_expiry = 0

    @classmethod
    def _fetch_access_token(cls) -> tuple[str, float]:
        with open(settings.FIREBASE_CREDENTIALS_PATH) as f:
            credentials = json.load(f)
        jwt_token = cls._build_jwt(credentials)
        return cls._exchange_jwt_for_token(jwt_token)

    @staticmethod
    def _build_jwt(credentials: dict) -> str:
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
        ).rstrip(b'=').decode()

        now = int(time.time())
        payload = base64.urlsafe_b64encode(
            json.dumps({
                "iss": credentials['client_email'],
                "sub": credentials['client_email'],
                "aud": "https://oauth2.googleapis.com/token",
                "iat": now,
                "exp": now + 3600,
                "scope": "https://www.googleapis.com/auth/firebase.messaging",
            }).encode()
        ).rstrip(b'=').decode()

        message = f"{header}.{payload}"

        private_key = serialization.load_pem_private_key(
            credentials['private_key'].encode(),
            password=None,
        )
        signature = private_key.sign(message.encode(), padding.PKCS1v15(), hashes.SHA256())
        signature_b64 = base64.urlsafe_b64encode(signature).rstrip(b'=').decode()

        return f"{message}.{signature_b64}"

    @staticmethod
    def _exchange_jwt_for_token(jwt_token: str) -> tuple[str, float]:
        response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": jwt_token,
            },
            timeout=10,  # ← add timeout
        )
        response.raise_for_status()
        data = response.json()
        return data['access_token'], time.time() + data['expires_in'] - 60


class NotificationService:
    FCM_URL = f"https://fcm.googleapis.com/v1/projects/{settings.FIREBASE_PROJECT_ID}/messages:send"

    @classmethod
    def send_notification(
        cls,
        user: User,
        title: str,
        body: str,
        notification_type: str = 'system',
        helper_id: str = '',
        sender: User = None,
        data: dict = None,
    ) -> None:

        # ── Save to DB first ──────────────────────────────────
        Notification.objects.create(
            user=user,
            sender=sender,        # None for system notifications
            title=title,
            message=body,
            notification_type=notification_type,
            helper_id=str(helper_id),
        )

        # ── Send push notification ────────────────────────────
        tokens = UserDeviceSelector.get_user_tokens(user)
        if not tokens:
            print(f'[FCM] no tokens for user {user}, saved to DB only')
            return

        try:
            access_token = FCMTokenManager.get_access_token()
        except Exception as e:
            print(f'[FCM] failed to get access token: {e}')
            return

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        for token in tokens:
            payload = {
                "message": {
                    "token": token,
                    "notification": {"title": title, "body": body},
                    "data": {k: str(v) for k, v in (data or {}).items()},
                }
            }
            try:
                response = httpx.post(
                    cls.FCM_URL,
                    json=payload,
                    headers=headers,
                    timeout=10,
                )
                if response.status_code == 401:
                    print('[FCM] token expired, refreshing...')
                    FCMTokenManager.invalidate_token()
                    headers["Authorization"] = f"Bearer {FCMTokenManager.get_access_token()}"
                    response = httpx.post(cls.FCM_URL, json=payload, headers=headers, timeout=10)

                response.raise_for_status()
                print(f'[FCM] notification sent to {user} ✅')

            except Exception as e:
                print(f'[FCM] failed to send to token {token[:20]}...: {e}')
