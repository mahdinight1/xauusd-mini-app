from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings


class ExchangeConnectionError(RuntimeError):
    pass


class BinanceReadOnlyConnector:
    """Validate Binance HMAC credentials and reject keys with trading/withdraw permissions."""

    def __init__(self, base_url: str = "https://api.binance.com", timeout: float = 8.0, transport=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport

    async def _signed_get(self, path: str, api_key: str, api_secret: str) -> dict[str, Any]:
        timestamp = int(time.time() * 1000)
        params = {"timestamp": timestamp, "recvWindow": 5000}
        query = urlencode(params)
        signature = hmac.new(api_secret.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
        params["signature"] = signature
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout, transport=self.transport) as client:
            response = await client.get(path, params=params, headers={"X-MBX-APIKEY": api_key})
        if response.status_code == 401 or response.status_code == 403:
            raise ExchangeConnectionError("Exchange rejected the credentials or they lack permission to read key restrictions")
        if response.status_code >= 500:
            raise ExchangeConnectionError("Exchange service is temporarily unavailable")
        if response.status_code >= 400:
            raise ExchangeConnectionError("Exchange rejected the request; verify the key, secret, IP allowlist, and server clock")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ExchangeConnectionError("Exchange returned an invalid response") from exc
        if not isinstance(payload, dict):
            raise ExchangeConnectionError("Exchange returned an invalid response")
        return payload

    async def validate_read_only(self, api_key: str, api_secret: str) -> dict[str, Any]:
        if not api_key.strip() or not api_secret.strip() or any(char.isspace() for char in api_key + api_secret):
            raise ValueError("API key and secret must be non-empty and contain no whitespace")
        restrictions = await self._signed_get("/sapi/v1/account/apiRestrictions", api_key, api_secret)
        if restrictions.get("enableReading") is not True:
            raise ExchangeConnectionError("The API key does not have account-read permission enabled")
        # Fail closed: only an explicit false value proves that privileged permissions are disabled.
        if restrictions.get("enableSpotAndMarginTrading") is not False:
            raise ExchangeConnectionError("Rejected: permission response does not prove Spot/Margin trading is disabled")
        if restrictions.get("enableWithdrawals") is not False:
            raise ExchangeConnectionError("Rejected: permission response does not prove withdrawals are disabled")
        # Verify that account data is accessible, but never return balances to logs or persist the response.
        account = await self._signed_get("/api/v3/account", api_key, api_secret)
        if not isinstance(account.get("balances"), list):
            raise ExchangeConnectionError("Exchange did not return account data for this read-only key")
        return {"exchange": "binance", "permission_profile": "read_only_no_trade_no_withdraw",
                "verified_at": datetime.now(timezone.utc).isoformat(), "account_data_access": True}


class GooglePlayVerificationError(RuntimeError):
    pass


class GooglePlaySubscriptionVerifier:
    """Verifies subscription purchase tokens against the Google Play Developer API."""
    SCOPE = "https://www.googleapis.com/auth/androidpublisher"

    def __init__(self, package_name: str | None = None, service_account_path: str | None = None,
                 pro_product_id: str | None = None, premium_product_id: str | None = None):
        self.package_name = (package_name if package_name is not None else settings.google_play_package_name).strip()
        self.service_account_path = (service_account_path if service_account_path is not None else settings.google_play_service_account_path).strip()
        self.product_tiers = {
            (pro_product_id if pro_product_id is not None else settings.google_play_pro_product_id): "pro",
            (premium_product_id if premium_product_id is not None else settings.google_play_premium_product_id): "premium",
        }

    @property
    def configured(self) -> bool:
        import os
        return bool(self.package_name and self.service_account_path and os.path.isfile(self.service_account_path)
                    and any(self.product_tiers.keys()))

    def verify(self, product_id: str, purchase_token: str) -> dict[str, Any]:
        import requests
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        if not self.configured:
            raise GooglePlayVerificationError(
                "Google Play verification is not configured. Set GOOGLE_PLAY_PACKAGE_NAME and GOOGLE_PLAY_SERVICE_ACCOUNT_PATH."
            )
        tier = self.product_tiers.get(product_id)
        if tier is None:
            raise ValueError("Unknown subscription product ID")
        try:
            credentials = service_account.Credentials.from_service_account_file(self.service_account_path, scopes=[self.SCOPE])
            credentials.refresh(Request())
            encoded_package = self.package_name
            encoded_token = __import__("urllib.parse", fromlist=["quote"]).quote(purchase_token, safe="")
            url = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{encoded_package}/purchases/subscriptionsv2/tokens/{encoded_token}"
            response = requests.get(url, headers={"Authorization": f"Bearer {credentials.token}"}, timeout=12)
            if response.status_code in (400, 404):
                raise ValueError("Google Play did not recognize this purchase token")
            response.raise_for_status()
            payload = response.json()
        except ValueError:
            raise
        except Exception as exc:
            # Avoid propagating service-account details, tokens, or raw provider bodies.
            raise GooglePlayVerificationError(f"Google Play verification failed ({type(exc).__name__})") from exc
        if not isinstance(payload, dict):
            raise GooglePlayVerificationError("Google Play returned an invalid subscription response")
        line_items = payload.get("lineItems") or []
        matching = [item for item in line_items if isinstance(item, dict) and item.get("productId") == product_id]
        if not matching:
            raise ValueError("Purchase token does not belong to the submitted product ID")
        expiry_text = max((str(item.get("expiryTime", "")) for item in matching), default="")
        try:
            expiry = datetime.fromisoformat(expiry_text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise GooglePlayVerificationError("Google Play response did not include a valid subscription expiry") from exc
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        state = str(payload.get("subscriptionState", "SUBSCRIPTION_STATE_UNSPECIFIED"))
        state_map = {
            "SUBSCRIPTION_STATE_ACTIVE": "active",
            "SUBSCRIPTION_STATE_IN_GRACE_PERIOD": "grace_period",
            "SUBSCRIPTION_STATE_CANCELED": "canceled",
            "SUBSCRIPTION_STATE_EXPIRED": "expired",
            "SUBSCRIPTION_STATE_ON_HOLD": "on_hold",
            "SUBSCRIPTION_STATE_PAUSED": "paused",
            "SUBSCRIPTION_STATE_PENDING": "pending",
            "SUBSCRIPTION_STATE_PENDING_PURCHASE_CANCELED": "expired",
        }
        status = state_map.get(state, "unknown")
        if status in {"active", "grace_period", "canceled"} and expiry <= datetime.now(timezone.utc):
            status = "expired"
        if status not in {"active", "grace_period", "canceled"} or expiry <= datetime.now(timezone.utc):
            raise ValueError(f"Subscription is not active (state={status})")
        # Acknowledge verified subscriptions if Google reports pending acknowledgement.
        if payload.get("acknowledgementState") == "ACKNOWLEDGEMENT_STATE_PENDING":
            subscription_id = __import__("urllib.parse", fromlist=["quote"]).quote(product_id, safe="")
            ack_url = f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{encoded_package}/purchases/subscriptions/{subscription_id}/tokens/{encoded_token}:acknowledge"
            ack = requests.post(ack_url, headers={"Authorization": f"Bearer {credentials.token}"}, json={}, timeout=12)
            if ack.status_code >= 400:
                raise GooglePlayVerificationError("Subscription verified but acknowledgement failed; retry verification after checking Play API access")
        return {"product_id": product_id, "tier": tier, "status": status, "expires_at": expiry.astimezone(timezone.utc).isoformat(),
                "store": "google_play", "verification_source": "Google Play Developer API", "verified_at": datetime.now(timezone.utc).isoformat()}
