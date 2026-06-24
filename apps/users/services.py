"""Push + notifications helpers.

We use 2 layers:
- Internal DB notifications (always).
- Optional Expo push (best-effort).

The mobile app can still poll /api/users/notifications/ which is 100% reliable.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import requests

from .models import PushToken, User


logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def send_expo_push_to_user(user: User, title: str, body: str, data: Optional[Dict[str, Any]] = None) -> None:
    """Best-effort Expo push. Never raises — échecs loggés silencieusement."""
    try:
        tokens = list(PushToken.objects.filter(user=user).values_list("token", flat=True))
        if not tokens:
            logger.debug("push: no tokens for user=%s", user.id)
            return

        payload = [
            {
                "to": t,
                "title": title,
                "body": body,
                "sound": "default",
                "data": data or {},
                "priority": "high",
            }
            for t in tokens
        ]

        response = requests.post(
            EXPO_PUSH_URL,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=3,
        )

        if response.status_code >= 400:
            logger.warning(
                "push: Expo returned HTTP %s for user=%s",
                response.status_code,
                user.id,
            )

    except requests.Timeout:
        logger.warning("push: timeout sending to user=%s", user.id)
    except Exception as exc:
        logger.error("push: unexpected error for user=%s: %r", user.id, exc)
