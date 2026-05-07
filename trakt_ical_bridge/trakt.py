from __future__ import annotations

import json
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from .config import Settings


class TraktError(RuntimeError):
    pass


class TraktClient:
    api_base = "https://api.trakt.tv"
    site_base = "https://trakt.tv"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.token_path = self.settings.data_dir / "tokens.json"

    def configured(self) -> bool:
        return bool(self.settings.trakt_client_id and self.settings.trakt_client_secret)

    def authorized(self) -> bool:
        return self.token_path.exists()

    def authorize_url(self) -> str:
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.settings.trakt_client_id,
                "redirect_uri": self.settings.trakt_redirect_uri,
            }
        )
        return f"{self.site_base}/oauth/authorize?{query}"

    def exchange_code(self, code: str) -> None:
        payload = {
            "code": code,
            "client_id": self.settings.trakt_client_id,
            "client_secret": self.settings.trakt_client_secret,
            "redirect_uri": self.settings.trakt_redirect_uri,
            "grant_type": "authorization_code",
        }
        token = self._post_token(payload)
        self._save_token(token)

    def _load_token(self) -> dict[str, Any]:
        if not self.token_path.exists():
            raise TraktError("Trakt is not authorized yet. Open /setup first.")
        return json.loads(self.token_path.read_text(encoding="utf-8"))

    def _save_token(self, token: dict[str, Any]) -> None:
        token["saved_at"] = int(time.time())
        self.token_path.write_text(json.dumps(token, indent=2), encoding="utf-8")
        self.token_path.chmod(0o600)

    def _post_token(self, payload: dict[str, str]) -> dict[str, Any]:
        response = requests.post(f"{self.api_base}/oauth/token", json=payload, timeout=30)
        if response.status_code >= 400:
            raise TraktError(f"Trakt token request failed: {response.status_code} {response.text}")
        return response.json()

    def _access_token(self) -> str:
        token = self._load_token()
        expires_at = int(token.get("saved_at", 0)) + int(token.get("expires_in", 0)) - 300
        if int(time.time()) < expires_at:
            return token["access_token"]

        payload = {
            "refresh_token": token["refresh_token"],
            "client_id": self.settings.trakt_client_id,
            "client_secret": self.settings.trakt_client_secret,
            "redirect_uri": self.settings.trakt_redirect_uri,
            "grant_type": "refresh_token",
        }
        refreshed = self._post_token(payload)
        self._save_token(refreshed)
        return refreshed["access_token"]

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": self.settings.trakt_client_id,
            "Authorization": f"Bearer {self._access_token()}",
        }

    def _get(self, path: str) -> list[dict[str, Any]]:
        response = requests.get(f"{self.api_base}/{path}", headers=self._headers(), timeout=45)
        if response.status_code >= 400:
            raise TraktError(f"Trakt API request failed: {response.status_code} {response.text}")
        data = response.json()
        if not isinstance(data, list):
            raise TraktError("Trakt returned an unexpected response shape.")
        return data

    def calendar_items(self) -> list[dict[str, Any]]:
        start = date.today() - timedelta(days=self.settings.days_back)
        days = self.settings.days_back + self.settings.days_ahead
        start_s = start.isoformat()

        sources = [("shows", f"calendars/my/shows/{start_s}/{days}")]
        if self.settings.include_premieres:
            sources.append(("premieres", f"calendars/my/shows/premieres/{start_s}/{days}"))
        if self.settings.include_finales:
            sources.append(("finales", f"calendars/my/shows/finales/{start_s}/{days}"))
        if self.settings.include_new_shows:
            sources.append(("new", f"calendars/my/shows/new/{start_s}/{days}"))

        items: list[dict[str, Any]] = []
        for source, path in sources:
            for item in self._get(path):
                item["_source"] = source
                items.append(item)
        return items


class CalendarCache:
    def __init__(self, path: Path, ttl_seconds: int):
        self.path = path
        self.ttl_seconds = ttl_seconds

    def fresh(self) -> bool:
        return self.path.exists() and time.time() - self.path.stat().st_mtime < self.ttl_seconds

    def read(self) -> str:
        return self.path.read_text(encoding="utf-8")

    def write(self, content: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(content, encoding="utf-8")
