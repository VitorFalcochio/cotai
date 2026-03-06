from __future__ import annotations

import time
from typing import Any

import requests

from ..config import Settings
from ..utils.retry import retry_call


class WhatsAppService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = requests.Session()

    def close(self) -> None:
        self.session.close()

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.settings.waha_api_key:
            headers["X-Api-Key"] = self.settings.waha_api_key
        return headers

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        timeout = kwargs.pop("timeout", self.settings.request_timeout_seconds)

        def do_request() -> requests.Response:
            response = self.session.request(method, url, timeout=timeout, **kwargs)
            if response.status_code in {408, 429, 500, 502, 503, 504}:
                response.raise_for_status()
            return response

        return retry_call(
            do_request,
            attempts=self.settings.retry_attempts,
            backoff_seconds=self.settings.retry_backoff_seconds,
            max_backoff_seconds=max(self.settings.retry_backoff_seconds, self.settings.request_timeout_seconds),
        )

    def healthcheck(self) -> dict[str, Any]:
        try:
            response = self._request(
                "GET",
                f"{self.settings.waha_base_url}/api/{self.settings.waha_session}/chats",
                params={"limit": 1},
                headers=self._headers(),
                timeout=self.settings.healthcheck_timeout_seconds,
            )
            return {"ok": response.ok, "status_code": response.status_code}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc)}

    def list_chats(self) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            f"{self.settings.waha_base_url}/api/{self.settings.waha_session}/chats",
            params={"limit": self.settings.waha_chats_limit},
            headers=self._headers(),
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def get_messages(self, chat_id: str, limit: int = 25) -> list[dict[str, Any]]:
        base = self.settings.waha_base_url
        session = self.settings.waha_session
        attempts = [
            (f"{base}/api/{session}/chats/{chat_id}/messages", {"limit": limit}),
            (f"{base}/api/{session}/messages", {"chatId": chat_id, "limit": limit}),
            (f"{base}/api/messages", {"session": session, "chatId": chat_id, "limit": limit}),
        ]

        last_error: Exception | None = None
        for url, params in attempts:
            try:
                response = self._request("GET", url, params=params, headers=self._headers())
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, list):
                    return [row for row in payload if isinstance(row, dict)]
                if isinstance(payload, dict):
                    if isinstance(payload.get("messages"), list):
                        return [row for row in payload["messages"] if isinstance(row, dict)]
                    if isinstance(payload.get("data"), list):
                        return [row for row in payload["data"] if isinstance(row, dict)]
                return []
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        if last_error is not None:
            raise last_error
        return []

    def send_text(self, chat_id: str, text: str) -> dict[str, Any]:
        payload = {"session": self.settings.waha_session, "chatId": chat_id, "text": text}
        response = self._request(
            "POST",
            f"{self.settings.waha_base_url}/api/sendText",
            headers=self._headers(),
            json=payload,
        )
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return {"ok": True, "status_code": response.status_code}
