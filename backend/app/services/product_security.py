from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.services.academy_content import COURSE_TITLE


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat()


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def auth_secret_configured() -> bool:
    secret = settings.jwt_secret_key.strip()
    return len(secret) >= 32 and not secret.lower().startswith(("replace-", "change-me", "your-secret"))


def certificate_signing_secret_configured() -> bool:
    secret = settings.certificate_signing_key.strip()
    return len(secret) >= 32 and not secret.lower().startswith(("replace-", "change-me", "your-secret"))


def exchange_encryption_configured() -> bool:
    key = settings.credential_encryption_key.strip()
    try:
        Fernet(key.encode("ascii"))
        return True
    except (ValueError, TypeError, UnicodeEncodeError):
        return False


class ProductStore:
    """Persistent store for identities, learning assessments, signed certificates, and secure integrations."""

    def __init__(self, db_path: str | None = None):
        path = db_path or os.getenv("NEXTRADE_DB_PATH", settings.nextrade_db_path)
        if path != ":memory:":
            Path(path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.db_path = path
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None, timeout=15)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        if path != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL")
        self._initialize()

    def _initialize(self) -> None:
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS product_users (
          id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
          password_hash TEXT NOT NULL, created_at TEXT NOT NULL, disabled INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS product_sessions (
          jti TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES product_users(id) ON DELETE CASCADE,
          expires_at TEXT NOT NULL, revoked_at TEXT, created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_product_sessions_user ON product_sessions(user_id, expires_at);
        CREATE TABLE IF NOT EXISTS academy_lesson_progress (
          user_id TEXT NOT NULL REFERENCES product_users(id) ON DELETE CASCADE,
          module_id INTEGER NOT NULL, lesson_id TEXT NOT NULL, completed_at TEXT NOT NULL,
          PRIMARY KEY(user_id, module_id, lesson_id)
        );
        CREATE TABLE IF NOT EXISTS academy_quiz_attempts (
          id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES product_users(id) ON DELETE CASCADE,
          kind TEXT NOT NULL CHECK(kind IN ('module','final')), module_id INTEGER,
          question_ids_json TEXT NOT NULL, answers_json TEXT, score REAL, passed INTEGER,
          started_at TEXT NOT NULL, submitted_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_academy_attempt_user ON academy_quiz_attempts(user_id, kind, module_id, started_at DESC);
        CREATE TABLE IF NOT EXISTS academy_certificates (
          id TEXT PRIMARY KEY, certificate_number TEXT NOT NULL UNIQUE,
          user_id TEXT NOT NULL REFERENCES product_users(id) ON DELETE RESTRICT,
          learner_name TEXT NOT NULL, course_title TEXT NOT NULL, final_score REAL NOT NULL,
          issued_at TEXT NOT NULL, signature TEXT NOT NULL, revoked_at TEXT
        );
        CREATE TABLE IF NOT EXISTS exchange_connections (
          id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES product_users(id) ON DELETE CASCADE,
          exchange TEXT NOT NULL, api_key_encrypted TEXT NOT NULL, api_secret_encrypted TEXT NOT NULL,
          key_fingerprint TEXT NOT NULL, permission_profile TEXT NOT NULL, status TEXT NOT NULL,
          created_at TEXT NOT NULL, last_checked_at TEXT NOT NULL, last_error TEXT,
          UNIQUE(user_id, exchange)
        );
        CREATE TABLE IF NOT EXISTS user_subscriptions (
          id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES product_users(id) ON DELETE CASCADE,
          store TEXT NOT NULL, product_id TEXT NOT NULL, token_hash TEXT NOT NULL UNIQUE,
          purchase_token_encrypted TEXT NOT NULL, tier TEXT NOT NULL, status TEXT NOT NULL, expires_at TEXT NOT NULL,
          last_verified_at TEXT NOT NULL, created_at TEXT NOT NULL,
          UNIQUE(user_id, store, product_id, token_hash)
        );
        CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user ON user_subscriptions(user_id, expires_at DESC);
        CREATE TABLE IF NOT EXISTS product_audit_log (
          id TEXT PRIMARY KEY, user_id TEXT, action TEXT NOT NULL, object_type TEXT NOT NULL,
          object_id TEXT, created_at TEXT NOT NULL, metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        """)
        subscription_columns = {row[1] for row in self.conn.execute("PRAGMA table_info(user_subscriptions)").fetchall()}
        if "purchase_token_encrypted" not in subscription_columns:
            self.conn.execute("ALTER TABLE user_subscriptions ADD COLUMN purchase_token_encrypted TEXT NOT NULL DEFAULT ''")

    def _audit(self, user_id: str | None, action: str, object_type: str, object_id: str | None, metadata: dict | None = None) -> None:
        self.conn.execute("INSERT INTO product_audit_log(id,user_id,action,object_type,object_id,created_at,metadata_json) VALUES(?,?,?,?,?,?,?)",
                          (str(uuid.uuid4()), user_id, action, object_type, object_id, iso_now(), json.dumps(metadata or {}, separators=(",", ":"))))

    def create_user(self, email: str, display_name: str, password_hash: str) -> dict[str, Any]:
        user_id, now = str(uuid.uuid4()), iso_now()
        self.conn.execute("INSERT INTO product_users(id,email,display_name,password_hash,created_at) VALUES(?,?,?,?,?)",
                          (user_id, email.lower().strip(), display_name.strip(), password_hash, now))
        self._audit(user_id, "user_registered", "user", user_id)
        return self.get_user(user_id) or {}

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM product_users WHERE email=?", (email.lower().strip(),)).fetchone()
        return dict(row) if row else None

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT id,email,display_name,created_at,disabled FROM product_users WHERE id=?", (user_id,)).fetchone()
        return dict(row) if row else None

    def create_session(self, user_id: str, jti: str, expires_at: datetime) -> None:
        self.conn.execute("INSERT INTO product_sessions(jti,user_id,expires_at,created_at) VALUES(?,?,?,?)",
                          (jti, user_id, expires_at.isoformat(), iso_now()))

    def validate_session(self, jti: str, user_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT s.*,u.email,u.display_name,u.disabled FROM product_sessions s JOIN product_users u ON u.id=s.user_id WHERE s.jti=? AND s.user_id=?",
                                 (jti, user_id)).fetchone()
        if not row or row["revoked_at"] or row["disabled"]:
            return None
        expiry = parse_datetime(row["expires_at"])
        if expiry is None or expiry <= utc_now():
            return None
        return {"id": user_id, "email": row["email"], "display_name": row["display_name"]}

    def revoke_session(self, jti: str) -> None:
        self.conn.execute("UPDATE product_sessions SET revoked_at=? WHERE jti=? AND revoked_at IS NULL", (iso_now(), jti))

    def complete_lesson(self, user_id: str, module_id: int, lesson_id: str) -> dict[str, Any]:
        timestamp = iso_now()
        self.conn.execute("INSERT INTO academy_lesson_progress(user_id,module_id,lesson_id,completed_at) VALUES(?,?,?,?) ON CONFLICT(user_id,module_id,lesson_id) DO UPDATE SET completed_at=excluded.completed_at",
                          (user_id, module_id, lesson_id, timestamp))
        self._audit(user_id, "lesson_completed", "lesson", lesson_id, {"module_id": module_id})
        return {"module_id": module_id, "lesson_id": lesson_id, "completed_at": timestamp}

    def completed_lessons(self, user_id: str) -> list[dict[str, Any]]:
        return [dict(row) for row in self.conn.execute("SELECT module_id,lesson_id,completed_at FROM academy_lesson_progress WHERE user_id=? ORDER BY module_id,lesson_id", (user_id,)).fetchall()]

    def create_quiz_attempt(self, user_id: str, kind: str, module_id: int | None, question_ids: list[str]) -> str:
        attempt_id = str(uuid.uuid4())
        self.conn.execute("INSERT INTO academy_quiz_attempts(id,user_id,kind,module_id,question_ids_json,started_at) VALUES(?,?,?,?,?,?)",
                          (attempt_id, user_id, kind, module_id, json.dumps(question_ids), iso_now()))
        return attempt_id

    def get_quiz_attempt(self, attempt_id: str, user_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM academy_quiz_attempts WHERE id=? AND user_id=?", (attempt_id, user_id)).fetchone()
        if not row:
            return None
        value = dict(row)
        value["question_ids"] = json.loads(value.pop("question_ids_json"))
        value["answers"] = json.loads(value.pop("answers_json")) if value.get("answers_json") else None
        return value

    def submit_quiz_attempt(self, attempt_id: str, user_id: str, answers: dict[str, int], score: float, passed: bool) -> bool:
        with self.conn:
            cursor = self.conn.execute("UPDATE academy_quiz_attempts SET answers_json=?,score=?,passed=?,submitted_at=? WHERE id=? AND user_id=? AND submitted_at IS NULL",
                                       (json.dumps(answers, separators=(",", ":")), score, int(passed), iso_now(), attempt_id, user_id))
            if cursor.rowcount == 1:
                self._audit(user_id, "quiz_submitted", "quiz_attempt", attempt_id, {"score": score, "passed": passed})
                return True
            return False

    def quiz_attempts(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT id,kind,module_id,score,passed,started_at,submitted_at FROM academy_quiz_attempts WHERE user_id=? ORDER BY started_at DESC", (user_id,)).fetchall()
        return [dict(row) for row in rows]

    def has_passed_module_quiz(self, user_id: str, module_id: int) -> bool:
        row = self.conn.execute("SELECT 1 FROM academy_quiz_attempts WHERE user_id=? AND kind='module' AND module_id=? AND passed=1 LIMIT 1", (user_id, module_id)).fetchone()
        return row is not None

    def has_passed_final_exam(self, user_id: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM academy_quiz_attempts WHERE user_id=? AND kind='final' AND passed=1 LIMIT 1", (user_id,)).fetchone()
        return row is not None

    def create_certificate(self, user_id: str, learner_name: str, final_score: float, signer) -> dict[str, Any]:
        existing = self.conn.execute("SELECT * FROM academy_certificates WHERE user_id=? AND revoked_at IS NULL ORDER BY issued_at DESC LIMIT 1", (user_id,)).fetchone()
        if existing:
            return dict(existing)
        certificate_id = str(uuid.uuid4())
        number = "NX-" + secrets.token_hex(6).upper()
        now = iso_now()
        signature = signer(number, user_id, learner_name, COURSE_TITLE, final_score, now)
        self.conn.execute("INSERT INTO academy_certificates(id,certificate_number,user_id,learner_name,course_title,final_score,issued_at,signature) VALUES(?,?,?,?,?,?,?,?)",
                          (certificate_id, number, user_id, learner_name, COURSE_TITLE, final_score, now, signature))
        self._audit(user_id, "certificate_issued", "certificate", certificate_id, {"certificate_number": number, "score": final_score})
        return dict(self.conn.execute("SELECT * FROM academy_certificates WHERE id=?", (certificate_id,)).fetchone())

    def get_certificate_for_user(self, user_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM academy_certificates WHERE user_id=? AND revoked_at IS NULL ORDER BY issued_at DESC LIMIT 1", (user_id,)).fetchone()
        return dict(row) if row else None

    def get_certificate_by_number(self, number: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM academy_certificates WHERE certificate_number=?", (number.upper(),)).fetchone()
        return dict(row) if row else None

    def update_exchange_check(self, user_id: str, exchange: str, status: str, last_error: str | None = None) -> None:
        self.conn.execute("UPDATE exchange_connections SET status=?,last_checked_at=?,last_error=? WHERE user_id=? AND exchange=?",
                          (status, iso_now(), last_error, user_id, exchange))

    def upsert_exchange(self, user_id: str, exchange: str, api_key_encrypted: str, api_secret_encrypted: str,
                        fingerprint: str, status: str, permission_profile: str, last_error: str | None = None) -> dict[str, Any]:
        now = iso_now()
        existing = self.conn.execute("SELECT id FROM exchange_connections WHERE user_id=? AND exchange=?", (user_id, exchange)).fetchone()
        connection_id = existing["id"] if existing else str(uuid.uuid4())
        self.conn.execute("""INSERT INTO exchange_connections(id,user_id,exchange,api_key_encrypted,api_secret_encrypted,key_fingerprint,permission_profile,status,created_at,last_checked_at,last_error)
          VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,exchange) DO UPDATE SET api_key_encrypted=excluded.api_key_encrypted,
          api_secret_encrypted=excluded.api_secret_encrypted,key_fingerprint=excluded.key_fingerprint,permission_profile=excluded.permission_profile,
          status=excluded.status,last_checked_at=excluded.last_checked_at,last_error=excluded.last_error""",
          (connection_id,user_id,exchange,api_key_encrypted,api_secret_encrypted,fingerprint,permission_profile,status,now,now,last_error))
        self._audit(user_id, "exchange_connected", "exchange_connection", connection_id, {"exchange": exchange, "status": status, "fingerprint": fingerprint})
        return self.get_exchange(user_id, exchange) or {}

    def get_exchange(self, user_id: str, exchange: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT id,exchange,key_fingerprint,permission_profile,status,created_at,last_checked_at,last_error FROM exchange_connections WHERE user_id=? AND exchange=?", (user_id, exchange)).fetchone()
        return dict(row) if row else None

    def get_exchange_secrets(self, user_id: str, exchange: str) -> dict[str, str] | None:
        row = self.conn.execute("SELECT api_key_encrypted,api_secret_encrypted FROM exchange_connections WHERE user_id=? AND exchange=?", (user_id, exchange)).fetchone()
        return dict(row) if row else None

    def list_exchanges(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT id,exchange,key_fingerprint,permission_profile,status,created_at,last_checked_at,last_error FROM exchange_connections WHERE user_id=? ORDER BY exchange", (user_id,)).fetchall()
        return [dict(row) for row in rows]

    def delete_exchange(self, user_id: str, exchange: str) -> bool:
        with self.conn:
            cursor = self.conn.execute("DELETE FROM exchange_connections WHERE user_id=? AND exchange=?", (user_id, exchange))
            if cursor.rowcount:
                self._audit(user_id, "exchange_disconnected", "exchange_connection", None, {"exchange": exchange})
                return True
            return False

    def upsert_subscription(self, user_id: str, store: str, product_id: str, token_hash: str,
                            purchase_token_encrypted: str, tier: str, status: str, expires_at: str) -> dict[str, Any]:
        now = iso_now()
        existing = self.conn.execute("SELECT id,user_id FROM user_subscriptions WHERE token_hash=?", (token_hash,)).fetchone()
        if existing and existing["user_id"] != user_id:
            raise PermissionError("Purchase token is already associated with another user")
        sub_id = existing["id"] if existing else str(uuid.uuid4())
        self.conn.execute("""INSERT INTO user_subscriptions(id,user_id,store,product_id,token_hash,purchase_token_encrypted,tier,status,expires_at,last_verified_at,created_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(token_hash) DO UPDATE SET purchase_token_encrypted=excluded.purchase_token_encrypted,
          status=excluded.status,tier=excluded.tier,expires_at=excluded.expires_at,last_verified_at=excluded.last_verified_at""",
          (sub_id,user_id,store,product_id,token_hash,purchase_token_encrypted,tier,status,expires_at,now,now))
        self._audit(user_id, "subscription_verified", "subscription", sub_id, {"store": store, "product_id": product_id, "tier": tier, "status": status})
        return self.subscription_entitlement(user_id)


    def subscription_records_for_user(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.conn.execute("SELECT id,store,product_id,token_hash,purchase_token_encrypted,tier,status,expires_at,last_verified_at FROM user_subscriptions WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
        return [dict(row) for row in rows]

    def update_subscription_status(self, subscription_id: str, user_id: str, status: str, expires_at: str | None = None) -> None:
        if expires_at:
            self.conn.execute("UPDATE user_subscriptions SET status=?,expires_at=?,last_verified_at=? WHERE id=? AND user_id=?",
                              (status, expires_at, iso_now(), subscription_id, user_id))
        else:
            self.conn.execute("UPDATE user_subscriptions SET status=?,last_verified_at=? WHERE id=? AND user_id=?",
                              (status, iso_now(), subscription_id, user_id))

    def subscription_entitlement(self, user_id: str) -> dict[str, Any]:
        rows = self.conn.execute("SELECT tier,status,expires_at,product_id,store,last_verified_at FROM user_subscriptions WHERE user_id=? ORDER BY expires_at DESC", (user_id,)).fetchall()
        now = utc_now()
        active = []
        for row in rows:
            expiry = parse_datetime(row["expires_at"])
            if row["status"] in {"active", "grace_period", "canceled"} and expiry and expiry > now:
                active.append(dict(row))
        order = {"free": 0, "pro": 1, "premium": 2}
        best = max(active, key=lambda item: order.get(item["tier"], 0)) if active else None
        return {"tier": best["tier"] if best else "free", "active": bool(best),
                "expires_at": best["expires_at"] if best else None,
                "store": best["store"] if best else None,
                "product_id": best["product_id"] if best else None,
                "last_verified_at": best["last_verified_at"] if best else None,
                "checked_at": iso_now()}


class AuthService:
    def __init__(self, store: ProductStore):
        self.store = store
        self.hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)

    def register(self, email: str, display_name: str, password: str) -> tuple[dict[str, Any], str, str]:
        email = email.strip().lower()
        display_name = display_name.strip()
        if len(email) > 254 or "@" not in email or email.startswith("@") or email.endswith("@"):
            raise ValueError("Enter a valid email address")
        if len(display_name) < 2 or len(display_name) > 80:
            raise ValueError("Display name must be between 2 and 80 characters")
        if len(password) < 10 or len(password) > 256:
            raise ValueError("Password must contain 10 to 256 characters")
        if not auth_secret_configured():
            raise RuntimeError("Set NEXTRADE_JWT_SECRET to a random secret of at least 32 characters before using accounts")
        user = self.store.create_user(email, display_name, self.hasher.hash(password))
        token, jti = self._issue_token(user["id"])
        return self.store.get_user(user["id"]) or user, token, jti

    def login(self, email: str, password: str) -> tuple[dict[str, Any], str, str] | None:
        if not auth_secret_configured():
            raise RuntimeError("Set NEXTRADE_JWT_SECRET to a random secret of at least 32 characters before using accounts")
        user = self.store.get_user_by_email(email)
        if not user or user.get("disabled"):
            return None
        try:
            valid = self.hasher.verify(user["password_hash"], password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            valid = False
        if not valid:
            return None
        token, jti = self._issue_token(user["id"])
        return self.store.get_user(user["id"]) or {}, token, jti

    def _issue_token(self, user_id: str) -> tuple[str, str]:
        jti = secrets.token_urlsafe(24)
        issued = utc_now()
        expiry = issued + timedelta(hours=12)
        payload = {"sub": user_id, "jti": jti, "iat": issued, "exp": expiry, "iss": "nextrade-api", "aud": "nextrade-mobile"}
        token = jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")
        self.store.create_session(user_id, jti, expiry)
        return token, jti

    def validate(self, token: str) -> tuple[dict[str, Any], str] | None:
        if not auth_secret_configured():
            return None
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"], audience="nextrade-mobile", issuer="nextrade-api")
        except jwt.PyJWTError:
            return None
        user_id, jti = payload.get("sub"), payload.get("jti")
        if not isinstance(user_id, str) or not isinstance(jti, str):
            return None
        user = self.store.validate_session(jti, user_id)
        return (user, jti) if user else None

    @staticmethod
    def revoke(jti: str, store: ProductStore) -> None:
        store.revoke_session(jti)


def _fernet() -> Fernet:
    if not exchange_encryption_configured():
        raise RuntimeError("Configure NEXTRADE_CREDENTIAL_ENCRYPTION_KEY with a generated Fernet key")
    return Fernet(settings.credential_encryption_key.encode("ascii"))


def encrypt_exchange_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_exchange_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Stored exchange credential cannot be decrypted; check encryption key continuity") from exc


def certificate_signature(certificate_number: str, user_id: str, learner_name: str, course_title: str,
                          final_score: float, issued_at: str) -> str:
    if not certificate_signing_secret_configured():
        raise RuntimeError("Certificate signing is unavailable until NEXTRADE_CERTIFICATE_SIGNING_KEY is configured")
    message = "|".join((certificate_number, user_id, learner_name, course_title, f"{final_score:.2f}", issued_at)).encode("utf-8")
    return hmac.new(settings.certificate_signing_key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_certificate_signature(certificate: dict[str, Any]) -> bool:
    expected = certificate_signature(certificate["certificate_number"], certificate["user_id"], certificate["learner_name"],
                                     certificate["course_title"], float(certificate["final_score"]), certificate["issued_at"])
    return hmac.compare_digest(expected, certificate["signature"])
