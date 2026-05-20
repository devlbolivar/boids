import hmac
import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_add_lead_to_campaign_sends_correct_payload():
    from app.integrations.instantly.client import InstantlyClient

    with patch("app.integrations.instantly.client.httpx.AsyncClient") as mock_http:
        mock_response = MagicMock()
        mock_response.json.return_value = {"id": "inst_lead_123"}
        mock_response.raise_for_status = MagicMock()

        mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_http.return_value)
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http.return_value.post = AsyncMock(return_value=mock_response)

        client = InstantlyClient(api_key="test_key")
        result = await client.add_lead_to_campaign(
            campaign_id="camp_123",
            email="cto@startup.cl",
            first_name="Carlos",
            subject="Test subject",
            body="Test body",
        )

    assert result["id"] == "inst_lead_123"
    call_kwargs = mock_http.return_value.post.call_args.kwargs
    payload = call_kwargs["json"]
    assert payload["email"] == "cto@startup.cl"
    assert payload["campaign_id"] == "camp_123"
    assert payload["personalization"]["subject"] == "Test subject"
    assert payload["skip_if_in_workspace"] is True


@pytest.mark.asyncio
async def test_webhook_signature_verification_valid():
    from app.integrations.instantly.client import InstantlyClient
    from app.config import settings

    secret = "test_webhook_secret"
    payload = b'{"event_type": "reply_received"}'
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    with patch.object(settings, "INSTANTLY_WEBHOOK_SECRET", secret):
        client = InstantlyClient(api_key="key")
        valid = await client.verify_webhook_signature(payload, sig)

    assert valid is True


@pytest.mark.asyncio
async def test_webhook_signature_verification_invalid():
    from app.integrations.instantly.client import InstantlyClient
    from app.config import settings

    secret = "test_webhook_secret"
    payload = b'{"event_type": "reply_received"}'

    with patch.object(settings, "INSTANTLY_WEBHOOK_SECRET", secret):
        client = InstantlyClient(api_key="key")
        invalid = await client.verify_webhook_signature(payload, "wrong_sig")

    assert invalid is False
