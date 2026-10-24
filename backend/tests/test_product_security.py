from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.main import app
from app.services.academy_content import MODULES, FINAL_PASS_PERCENT
from app.services.integrations import BinanceReadOnlyConnector
from app.services.product_security import AuthService, ProductStore, encrypt_exchange_secret, decrypt_exchange_secret, digest

client = TestClient(app)


@pytest.fixture
def secure_runtime(monkeypatch, tmp_path):
    from app.core.config import settings
    from app import main

    monkeypatch.setattr(settings, "jwt_secret_key", "nextrade-test-secret-not-for-production-4b8e9ac7")
    monkeypatch.setattr(settings, "certificate_signing_key", "nextrade-test-certificate-key-not-production-8d4be11f")
    monkeypatch.setattr(settings, "credential_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "environment", "development")
    store = ProductStore(str(tmp_path / "secure-test.sqlite3"))
    monkeypatch.setattr(main, "product_store", store)
    monkeypatch.setattr(main, "auth_service", AuthService(store))
    return store


def register(secure_runtime, email="student@example.com"):
    response = client.post("/v1/auth/register", json={
        "display_name": "Course Student", "email": email, "password": "Strong-password-123"
    })
    assert response.status_code == 201, response.text
    return response.json()


def auth_headers(auth_payload):
    return {"Authorization": f"Bearer {auth_payload['access_token']}"}


def grant_test_tier(store, user_id: str, tier: str):
    purchase_token = f"test-entitlement-{tier}-{user_id}"
    return store.upsert_subscription(
        user_id, "test_store", f"test_{tier}", digest(purchase_token),
        encrypt_exchange_secret(purchase_token), tier, "active",
        (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    )


def test_auth_register_login_and_server_revocable_session(secure_runtime):
    result = register(secure_runtime)
    assert result["token_type"] == "bearer"
    me = client.get("/v1/auth/me", headers=auth_headers(result))
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "student@example.com"
    logout = client.post("/v1/auth/logout", headers=auth_headers(result))
    assert logout.status_code == 200
    assert client.get("/v1/auth/me", headers=auth_headers(result)).status_code == 401
    login = client.post("/v1/auth/login", json={"email": "student@example.com", "password": "Strong-password-123"})
    assert login.status_code == 200
    assert login.json()["user"]["id"] == result["user"]["id"]


def test_academy_requires_auth_and_returns_no_answers(secure_runtime):
    response = client.get("/v1/academy/modules")
    assert response.status_code == 401
    auth = register(secure_runtime)
    modules = client.get("/v1/academy/modules", headers=auth_headers(auth))
    assert modules.status_code == 200
    module = modules.json()["modules"][0]
    assert len(module["lessons"]) == 3
    assert module["locked"] is False
    pro_module = modules.json()["modules"][3]
    assert pro_module["locked"] is True
    assert pro_module["required_tier"] == "pro"
    assert "content" not in pro_module["lessons"][0]
    denied = client.post("/v1/academy/modules/4/lessons/m4-l1/complete", headers=auth_headers(auth), json={"completed": True})
    assert denied.status_code == 403
    started = client.post("/v1/academy/modules/1/quiz/start", headers=auth_headers(auth))
    assert started.status_code == 409  # lessons must be completed first
    lesson = module["lessons"][0]
    marked = client.post(f"/v1/academy/modules/1/lessons/{lesson['id']}/complete", headers=auth_headers(auth), json={"completed": True})
    assert marked.status_code == 200


def test_academy_final_exam_certificate_and_public_verification(secure_runtime):
    from app.services.academy_content import COURSE_TITLE

    auth = register(secure_runtime)
    grant_test_tier(secure_runtime, auth["user"]["id"], "premium")
    headers = auth_headers(auth)
    question_map = {question["id"]: question for module in MODULES for question in module["questions"]}
    for module in MODULES:
        module_id = module["id"]
        for lesson in module["lessons"]:
            response = client.post(f"/v1/academy/modules/{module_id}/lessons/{lesson['id']}/complete", headers=headers, json={"completed": True})
            assert response.status_code == 200
        start = client.post(f"/v1/academy/modules/{module_id}/quiz/start", headers=headers)
        assert start.status_code == 200, start.text
        attempt = start.json()
        answers = {question["id"]: question_map[question["id"]]["answer"] for question in attempt["questions"]}
        submitted = client.post(f"/v1/academy/quiz/{attempt['attempt_id']}/submit", headers=headers, json={"answers": answers})
        assert submitted.status_code == 200, submitted.text
        assert submitted.json()["passed"] is True

    final = client.post("/v1/academy/final-exam/start", headers=headers)
    assert final.status_code == 200, final.text
    attempt = final.json()
    assert len(attempt["questions"]) == 20
    answers = {question["id"]: question_map[question["id"]]["answer"] for question in attempt["questions"]}
    submitted = client.post(f"/v1/academy/final-exam/{attempt['attempt_id']}/submit", headers=headers, json={"answers": answers})
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["passed"] is True
    certificate = submitted.json()["certificate"]
    assert certificate["course_title"] == COURSE_TITLE
    verified = client.get(f"/v1/academy/certificates/verify/{certificate['certificate_number']}")
    assert verified.status_code == 200
    assert verified.json()["verified"] is True
    assert verified.json()["status"] == "valid"
    assert "not a government license" in verified.json()["scope_notice"]
    printable = client.get(f"/v1/academy/certificates/view/{certificate['certificate_number']}")
    assert printable.status_code == 200
    assert "Print / Save as PDF" in printable.text
    assert certificate["certificate_number"] in printable.text
    progress = client.get("/v1/academy/progress", headers=headers).json()
    assert "signature" not in progress["certificate"]
    assert "user_id" not in progress["certificate"]
    certificate_detail = client.get("/v1/academy/certificates/me", headers=headers).json()
    assert certificate_detail["printable_url"].endswith(f"/v1/academy/certificates/view/{certificate['certificate_number']}")


def test_certificate_cannot_be_issued_before_all_prerequisites(secure_runtime):
    auth = register(secure_runtime)
    headers = auth_headers(auth)
    response = client.post("/v1/academy/final-exam/start", headers=headers)
    assert response.status_code == 403  # paid entitlement is required
    grant_test_tier(secure_runtime, auth["user"]["id"], "premium")
    response = client.post("/v1/academy/final-exam/start", headers=headers)
    assert response.status_code == 409  # lessons/quizzes still required
    mine = client.get("/v1/academy/certificates/me", headers=headers)
    assert mine.status_code == 200
    assert mine.json()["issued"] is False


def test_credential_encryption_and_exchange_permissions_are_not_exposed(secure_runtime, monkeypatch):
    from app import main

    class FakeConnector:
        async def validate_read_only(self, api_key, api_secret):
            assert api_key == "A" * 24
            assert api_secret == "B" * 32
            return {"permission_profile": "read_only_no_trade_no_withdraw", "verified_at": datetime.now(timezone.utc).isoformat()}

    monkeypatch.setattr(main, "binance_connector", FakeConnector())
    encrypted = encrypt_exchange_secret("example-secret-value")
    assert encrypted != "example-secret-value"
    assert decrypt_exchange_secret(encrypted) == "example-secret-value"
    auth = register(secure_runtime)
    connected = client.post("/v1/exchanges/binance/connect", headers=auth_headers(auth), json={"api_key": "A" * 24, "api_secret": "B" * 32})
    assert connected.status_code == 200, connected.text
    body = connected.json()
    assert body["real_orders_enabled"] is False
    assert "api_secret" not in str(body).lower()
    listed = client.get("/v1/exchanges/connections", headers=auth_headers(auth))
    assert listed.status_code == 200
    assert listed.json()["items"][0]["permission_profile"] == "read_only_no_trade_no_withdraw"
    assert client.delete("/v1/exchanges/binance", headers=auth_headers(auth)).status_code == 200


def test_exchange_credentials_require_https_in_production(secure_runtime, monkeypatch):
    from app.core.config import settings
    from app import main

    class FakeConnector:
        async def validate_read_only(self, api_key, api_secret):
            raise AssertionError("must reject before contacting the exchange")

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(main, "binance_connector", FakeConnector())
    auth = register(secure_runtime)
    response = client.post("/v1/exchanges/binance/connect", headers=auth_headers(auth), json={"api_key": "A" * 24, "api_secret": "B" * 32})
    assert response.status_code == 400
    assert "HTTPS" in response.json()["detail"]


def test_google_play_subscription_verification_is_server_side_and_token_owned(secure_runtime, monkeypatch):
    from app import main
    from app.core.config import settings
    monkeypatch.setattr(settings, "billing_mode", "google_play")

    class FakeVerifier:
        configured = True

        def verify(self, product_id, purchase_token):
            assert purchase_token == "verified-store-token-for-test-123456789"
            assert product_id == "nextrade_pro_monthly"
            return {"product_id": product_id, "tier": "pro", "status": "active",
                    "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                    "verified_at": datetime.now(timezone.utc).isoformat(), "store": "google_play"}

    monkeypatch.setattr(main, "google_play_verifier", FakeVerifier())
    first = register(secure_runtime)
    token = "verified-store-token-for-test-123456789"
    response = client.post("/v1/subscriptions/google-play/verify", headers=auth_headers(first), json={"product_id": "nextrade_pro_monthly", "purchase_token": token})
    assert response.status_code == 200, response.text
    assert response.json()["entitlement"]["tier"] == "pro"
    stored = secure_runtime.subscription_records_for_user(first["user"]["id"])[0]
    assert stored["purchase_token_encrypted"] != token
    assert decrypt_exchange_secret(stored["purchase_token_encrypted"]) == token
    refreshed = client.get("/v1/subscriptions/me", headers=auth_headers(first))
    assert refreshed.status_code == 200
    assert refreshed.json()["tier"] == "pro"
    second = register(secure_runtime, email="another@example.com")
    conflict = client.post("/v1/subscriptions/google-play/verify", headers=auth_headers(second), json={"product_id": "nextrade_pro_monthly", "purchase_token": token})
    assert conflict.status_code == 409
    assert client.get("/v1/subscriptions/me", headers=auth_headers(second)).json()["tier"] == "free"


def test_unconfigured_google_play_never_grants_paid_entitlement(secure_runtime, monkeypatch):
    from app import main
    from app.core.config import settings
    monkeypatch.setattr(settings, "billing_mode", "google_play")
    from app.services.integrations import GooglePlayVerificationError

    class Unconfigured:
        configured = False

        def verify(self, product_id, purchase_token):
            raise GooglePlayVerificationError("Google Play verification is not configured")

    monkeypatch.setattr(main, "google_play_verifier", Unconfigured())
    auth = register(secure_runtime)
    response = client.post("/v1/subscriptions/google-play/verify", headers=auth_headers(auth), json={"product_id": "nextrade_pro_monthly", "purchase_token": "store-token-123456789-abcdefghi"})
    assert response.status_code == 503
    assert client.get("/v1/subscriptions/me", headers=auth_headers(auth)).json()["tier"] == "free"


def test_binance_connector_fails_closed_when_privileged_permissions_are_not_explicitly_disabled():
    import asyncio
    import httpx
    from app.services.integrations import BinanceReadOnlyConnector, ExchangeConnectionError

    calls = []
    def handler(request):
        calls.append(request.url.path)
        if request.url.path == "/sapi/v1/account/apiRestrictions":
            return httpx.Response(200, json={"enableReading": True})
        return httpx.Response(200, json={"balances": []})

    connector = BinanceReadOnlyConnector(transport=httpx.MockTransport(handler))
    with pytest.raises(ExchangeConnectionError, match="does not prove Spot/Margin trading is disabled"):
        asyncio.run(connector.validate_read_only("public-key", "private-secret"))
    assert calls == ["/sapi/v1/account/apiRestrictions"]


def test_binance_connector_accepts_only_explicit_read_only_permissions():
    import asyncio
    import httpx
    from app.services.integrations import BinanceReadOnlyConnector

    def handler(request):
        if request.url.path == "/sapi/v1/account/apiRestrictions":
            return httpx.Response(200, json={"enableReading": True, "enableSpotAndMarginTrading": False, "enableWithdrawals": False})
        return httpx.Response(200, json={"balances": []})

    connector = BinanceReadOnlyConnector(transport=httpx.MockTransport(handler))
    result = asyncio.run(connector.validate_read_only("public-key", "private-secret"))
    assert result["permission_profile"] == "read_only_no_trade_no_withdraw"
    assert result["account_data_access"] is True


def test_subscription_plans_expose_tiered_academy_access_without_hardcoded_prices():
    response = client.get("/v1/subscriptions/plans")
    assert response.status_code == 200
    payload = response.json()
    plans = {item["tier"]: item for item in payload["plans"]}
    assert "modules 1-3" in " ".join(plans["free"]["benefits"]).lower()
    assert "modules 1-8" in " ".join(plans["pro"]["benefits"]).lower()
    assert "all 12 academy modules" in " ".join(plans["premium"]["benefits"]).lower()
    assert "prices" in payload and "hardcoded" in payload["prices"].lower()

def test_pro_entitlement_unlocks_intermediate_not_premium_modules(secure_runtime):
    auth = register(secure_runtime)
    grant_test_tier(secure_runtime, auth["user"]["id"], "pro")
    modules = client.get("/v1/academy/modules", headers=auth_headers(auth)).json()["modules"]
    assert all(module["locked"] is False for module in modules[:8])
    assert modules[8]["locked"] is True
    assert modules[8]["required_tier"] == "premium"


def test_example_jwt_secret_is_rejected_as_unconfigured(secure_runtime, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "jwt_secret_key", "replace-this-with-a-random-secret-at-least-32-characters")
    response = client.post("/v1/auth/register", json={
        "display_name": "Placeholder Test", "email": "placeholder@example.com", "password": "Strong-password-123"
    })
    assert response.status_code == 503

def test_certificate_signing_uses_independent_secret(secure_runtime, monkeypatch):
    from app.core.config import settings
    from app.services.product_security import certificate_signature, verify_certificate_signature
    data = {"certificate_number": "NX-TESTCERT", "user_id": "user-1", "learner_name": "Learner",
            "course_title": "Course", "final_score": 90.0, "issued_at": "2026-10-24T00:00:00+00:00", "revoked_at": None}
    data["signature"] = certificate_signature(data["certificate_number"], data["user_id"], data["learner_name"],
                                               data["course_title"], data["final_score"], data["issued_at"])
    assert verify_certificate_signature(data) is True
    monkeypatch.setattr(settings, "jwt_secret_key", "a-different-jwt-signing-key-not-used-for-certificates-0001")
    assert verify_certificate_signature(data) is True
    monkeypatch.setattr(settings, "certificate_signing_key", "a-different-certificate-key-not-the-original-0000001")
    assert verify_certificate_signature(data) is False


def test_demo_billing_grants_temporary_server_entitlement_without_payment(secure_runtime, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "billing_mode", "demo")
    auth = register(secure_runtime)
    headers = auth_headers(auth)

    unauthenticated = client.post("/v1/subscriptions/demo/activate", json={"tier": "pro"})
    assert unauthenticated.status_code == 401

    plans = client.get("/v1/subscriptions/plans").json()
    assert plans["billing_mode"] == "demo"
    assert plans["demo_duration_days"] == 30
    assert "no payment is collected" in plans["prices"].lower()
    assert plans["plans"][1]["product_id"] is None

    response = client.post("/v1/subscriptions/demo/activate", headers=headers, json={"tier": "pro"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["demo"] is True
    assert payload["payment_collected"] is False
    assert payload["payment_status"] == "not_charged"
    assert payload["checkout_status"] == "simulated_success"
    assert payload["duration_days"] == 30
    assert payload["entitlement"]["tier"] == "pro"
    assert payload["entitlement"]["store"] == "demo"
    assert payload["entitlement"]["active"] is True
    modules = client.get("/v1/academy/modules", headers=headers).json()["modules"]
    assert all(module["locked"] is False for module in modules[:8])
    assert modules[8]["locked"] is True

    records = secure_runtime.subscription_records_for_user(auth["user"]["id"])
    assert len(records) == 1
    assert records[0]["store"] == "demo"
    assert records[0]["purchase_token_encrypted"] == "DEMO_NO_PAYMENT_TOKEN"


def test_repeating_active_demo_subscription_does_not_extend_expiry(secure_runtime, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "billing_mode", "demo")
    auth = register(secure_runtime)
    headers = auth_headers(auth)

    first = client.post("/v1/subscriptions/demo/activate", headers=headers, json={"tier": "pro"})
    assert first.status_code == 200
    expiry_before = first.json()["entitlement"]["expires_at"]
    second = client.post("/v1/subscriptions/demo/activate", headers=headers, json={"tier": "pro"})
    assert second.status_code == 200
    assert second.json()["already_active"] is True
    assert second.json()["entitlement"]["expires_at"] == expiry_before

    upgrade = client.post("/v1/subscriptions/demo/activate", headers=headers, json={"tier": "premium"})
    assert upgrade.status_code == 200
    assert upgrade.json()["entitlement"]["tier"] == "premium"
    assert len(secure_runtime.subscription_records_for_user(auth["user"]["id"])) == 2
    premium_modules = client.get("/v1/academy/modules", headers=headers).json()["modules"]
    assert all(module["locked"] is False for module in premium_modules)


def test_real_google_play_verification_is_blocked_in_demo_billing_mode(secure_runtime, monkeypatch):
    from app.core.config import settings
    from app import main
    monkeypatch.setattr(settings, "billing_mode", "demo")

    class MustNotVerify:
        configured = True
        def verify(self, product_id, purchase_token):
            raise AssertionError("Google Play verifier must not run in demo mode")

    monkeypatch.setattr(main, "google_play_verifier", MustNotVerify())
    auth = register(secure_runtime)
    response = client.post("/v1/subscriptions/google-play/verify", headers=auth_headers(auth), json={
        "product_id": "nextrade_pro_monthly", "purchase_token": "store-token-123456789-abcdefghi"
    })
    assert response.status_code == 403
    assert client.get("/v1/subscriptions/me", headers=auth_headers(auth)).json()["tier"] == "free"


def test_demo_subscription_activation_is_disabled_outside_demo_mode(secure_runtime, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "billing_mode", "google_play")
    auth = register(secure_runtime)
    response = client.post("/v1/subscriptions/demo/activate", headers=auth_headers(auth), json={"tier": "premium"})
    assert response.status_code == 403
    assert client.get("/v1/subscriptions/me", headers=auth_headers(auth)).json()["tier"] == "free"
