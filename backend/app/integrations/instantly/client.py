import hmac
import hashlib

import httpx

from app.config import settings

INSTANTLY_BASE = "https://api.instantly.ai/api/v2"


class InstantlyClient:

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.INSTANTLY_API_KEY
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def add_lead_to_campaign(
        self,
        campaign_id: str,
        email: str,
        first_name: str,
        subject: str,
        body: str,
    ) -> dict:
        """
        Agrega un lead a una campaña de Instantly con email personalizado.
        Instantly lo encola y lo envía según el schedule de la campaña
        (warmup, timing, throttling incluidos).
        """
        payload = {
            "campaign_id": campaign_id,
            "email": email,
            "first_name": first_name,
            "personalization": {
                "subject": subject,
                "body": body,
            },
            "skip_if_in_workspace": True,  # dedup: no reenviar si ya está
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                f"{INSTANTLY_BASE}/lead",
                json=payload,
                headers=self.headers,
            )
            r.raise_for_status()
            return r.json()

    async def verify_webhook_signature(
        self,
        payload: bytes,
        signature: str,
    ) -> bool:
        """
        Verifica que el webhook viene de Instantly.
        Instantly firma con HMAC-SHA256 usando el webhook secret.
        """
        expected = hmac.new(
            settings.INSTANTLY_WEBHOOK_SECRET.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
