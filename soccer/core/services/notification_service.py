# services/notification_service.py
import json
import time
import base64
import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings
from ..models import User
from ..selectors import UserDeviceSelector


class FCMTokenManager:
    _access_token: str = None
    _token_expiry: float = 0

    @classmethod
    def get_access_token(cls) -> str:
        if cls._access_token and time.time() < cls._token_expiry:
            return cls._access_token
        cls._access_token, cls._token_expiry = cls._fetch_access_token()
        return cls._access_token

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
            }
        )
        response.raise_for_status()
        data = response.json()
        return data['access_token'], time.time() + data['expires_in'] - 60


class NotificationService:
    FCM_URL = f"https://fcm.googleapis.com/v1/projects/{settings.FIREBASE_PROJECT_ID}/messages:send"

    @classmethod
    def send_notification(cls, user: User, title: str, body: str, data: dict = None) -> None:
        tokens = UserDeviceSelector.get_user_tokens(user)
        if not tokens:
            return

        headers = {
            "Authorization": f"Bearer {FCMTokenManager.get_access_token()}",
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
            httpx.post(cls.FCM_URL, json=payload, headers=headers)