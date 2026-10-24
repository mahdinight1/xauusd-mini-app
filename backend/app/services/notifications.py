from __future__ import annotations

import asyncio
import os
from typing import Any

from app.core.config import settings


def fcm_is_configured() -> bool:
    path = os.getenv("FCM_SERVICE_ACCOUNT_PATH", settings.fcm_service_account_path).strip()
    project_id = os.getenv("FCM_PROJECT_ID", settings.fcm_project_id).strip()
    return bool(path and os.path.isfile(path) and project_id)


def _send_fcm_sync(token: str, title: str, body: str, data: dict[str, Any] | None = None) -> tuple[bool, str | None]:
    """Send through Firebase Admin SDK if configured. Credentials remain server-only."""
    path = os.getenv("FCM_SERVICE_ACCOUNT_PATH", settings.fcm_service_account_path).strip()
    project_id = os.getenv("FCM_PROJECT_ID", settings.fcm_project_id).strip()
    if not path or not os.path.isfile(path) or not project_id:
        return False, "FCM is not configured; set FCM_SERVICE_ACCOUNT_PATH and FCM_PROJECT_ID."
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
        try:
            app = firebase_admin.get_app("nextrade-fcm")
        except ValueError:
            app = firebase_admin.initialize_app(credentials.Certificate(path), {"projectId": project_id}, name="nextrade-fcm")
        message = messaging.Message(
            token=token,
            notification=messaging.Notification(title=title, body=body),
            data={str(k): str(v) for k, v in (data or {}).items()},
        )
        messaging.send(message, app=app)
        return True, None
    except Exception as exc:  # Keep external credential/provider errors out of client detail.
        return False, f"FCM send failed: {type(exc).__name__}"


async def send_fcm(token: str, title: str, body: str, data: dict[str, Any] | None = None) -> tuple[bool, str | None]:
    return await asyncio.to_thread(_send_fcm_sync, token, title, body, data)
