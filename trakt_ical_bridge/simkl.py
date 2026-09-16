from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from .config import Settings
class SimklError(RuntimeError):
    pass


class SimklClient:
    api_base = "https://api.simkl.com"
    calendar_base = "https://data.simkl.in/calendar"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.token_path = self.settings.data_dir / "simkl-token.json"
        self.library_path = self.settings.data_dir / "simkl-library.json"

    def configured(self) -> bool:
        return bool(self.settings.simkl_client_id)

    def authorized(self) -> bool:
        return self.token_path.exists()

    def request_pin(self) -> dict[str, Any]:
        data = self._get_json(
            f"{self.api_base}/oauth/pin",
            params={"client_id": self.settings.simkl_client_id},
            authenticated=False,
        )
        if data.get("result") != "OK" or not data.get("user_code"):
            raise SimklError(f"Simkl did not issue a PIN: {data}")
        return data

    def poll_pin(self, user_code: str) -> dict[str, Any]:
        data = self._get_json(
            f"{self.api_base}/oauth/pin/{user_code}",
            params={"client_id": self.settings.simkl_client_id},
            authenticated=False,
        )
        token = data.get("access_token")
        if data.get("result") == "OK" and token:
            self.token_path.write_text(json.dumps({"access_token": token}), encoding="utf-8")
            self.token_path.chmod(0o600)
        return data

    def calendar_items(self) -> list[dict[str, Any]]:
        library_ids = self._library_ids()
        items: list[dict[str, Any]] = []
        for kind in ("tv", "anime"):
            data = self._get_json(
                f"{self.calendar_base}/{kind}.json",
                params=None,
                authenticated=False,
            )
            if not isinstance(data, list):
                raise SimklError(f"Simkl {kind} calendar returned an unexpected response")
            for raw in data:
                simkl_id = str((raw.get("ids") or {}).get("simkl_id") or "")
                if simkl_id in library_ids:
                    items.append(self._normalize(raw, kind))
        return items

    def _library_ids(self) -> set[str]:
        cached: dict[str, Any] = {}
        if self.library_path.exists():
            try:
                cached = json.loads(self.library_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                cached = {}

        activities = self._get_json(
            f"{self.api_base}/sync/activities",
            params={"client_id": self.settings.simkl_client_id},
        )
        activity_key = json.dumps(activities, sort_keys=True, separators=(",", ":"))
        if cached.get("activity_key") == activity_key and cached.get("ids") is not None:
            return set(cached.get("ids", []))

        library = self._get_json(
            f"{self.api_base}/sync/all-items/all/all",
            params={"client_id": self.settings.simkl_client_id, "extended": "ids_only"},
        )
        ids: set[str] = set()
        for group, media_key in (("shows", "show"), ("anime", "show")):
            for row in library.get(group, []):
                if row.get("status") == "dropped":
                    continue
                media = row.get(media_key) or row.get(group[:-1]) or {}
                simkl_id = (media.get("ids") or {}).get("simkl")
                if simkl_id:
                    ids.add(str(simkl_id))
        self.library_path.write_text(
            json.dumps({"saved_at": time.time(), "activity_key": activity_key, "ids": sorted(ids)}),
            encoding="utf-8",
        )
        return ids

    def _get_json(
        self,
        url: str,
        *,
        params: dict[str, str] | None,
        authenticated: bool = True,
    ) -> Any:
        headers = {"User-Agent": "media-command-simkl-bridge/1.0"}
        if authenticated:
            if not self.authorized():
                raise SimklError("Simkl is not connected. Open /setup to authorize it.")
            token = json.loads(self.token_path.read_text(encoding="utf-8"))["access_token"]
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = requests.get(url, params=params, headers=headers, timeout=45)
        except requests.RequestException as exc:
            raise SimklError(f"Simkl request failed: {exc}") from exc
        if response.status_code >= 400:
            raise SimklError(f"Simkl request failed: {response.status_code} {response.text}")
        try:
            return response.json()
        except ValueError as exc:
            raise SimklError("Simkl returned invalid JSON") from exc

    @staticmethod
    def _normalize(raw: dict[str, Any], kind: str) -> dict[str, Any]:
        raw_ids = raw.get("ids") or {}
        episode = raw.get("episode") or {}
        number = episode.get("episode")
        season = episode.get("season")
        return {
            "_source": "shows",
            "_provider": "simkl",
            "_provider_url": episode.get("url") or raw.get("url") or "https://simkl.com",
            "first_aired": raw.get("date"),
            "show": {
                "title": raw.get("title") or "Unknown show",
                "ids": {
                    "simkl": raw_ids.get("simkl_id"),
                    "slug": raw_ids.get("slug"),
                    "imdb": raw_ids.get("imdb"),
                    "tmdb": raw_ids.get("tmdb"),
                },
            },
            "episode": {
                "season": season,
                "number": number,
                "title": "",
                "ids": {"simkl": f"{raw_ids.get('simkl_id')}:{season}:{number}:{kind}"},
            },
        }


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


__all__ = ["CalendarCache", "SimklClient", "SimklError"]
