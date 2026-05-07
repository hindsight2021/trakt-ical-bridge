from __future__ import annotations

import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from .ics import _tag_for


def _clean_title(title: str) -> str:
    title = re.sub(r"\s+-\s+S\d{2}E\d{2}.*$", "", title)
    title = re.sub(r"^(Season Premiere|Season Finale|New Show):\s+", "", title)
    return title.strip()


class TvMazeClient:
    def __init__(self) -> None:
        self._cache: dict[str, dict] = {}

    def lookup(self, title: str) -> dict:
        key = _clean_title(title).lower()
        if key in self._cache:
            return self._cache[key]

        result = {
            "poster": "",
            "rating": None,
            "imdb_url": "",
            "network": "",
        }
        try:
            response = requests.get(
                "https://api.tvmaze.com/singlesearch/shows",
                params={"q": key},
                timeout=15,
            )
            if response.status_code == 200:
                data = response.json()
                image = data.get("image") or {}
                externals = data.get("externals") or {}
                result = {
                    "poster": image.get("medium") or image.get("original") or "",
                    "rating": (data.get("rating") or {}).get("average"),
                    "imdb_url": f"https://www.imdb.com/title/{externals['imdb']}/"
                    if externals.get("imdb")
                    else "",
                    "network": ((data.get("network") or data.get("webChannel") or {}).get("name") or ""),
                }
        except requests.RequestException:
            pass

        self._cache[key] = result
        return result


def build_schedule_items(items: list[dict], tz_name: str) -> list[dict]:
    tz = ZoneInfo(tz_name)
    tvmaze = TvMazeClient()
    schedule: list[dict] = []
    seen: set[str] = set()
    source_priority = {"finales": 0, "premieres": 1, "new": 2, "shows": 3}

    for item in sorted(
        items,
        key=lambda event: (
            event.get("first_aired") or "",
            source_priority.get(event.get("_source", "shows"), 9),
        ),
    ):
        first_aired = item.get("first_aired")
        if not first_aired:
            continue
        show = item.get("show") or {}
        episode = item.get("episode") or {}
        ids = episode.get("ids") or {}
        uid = str(ids.get("trakt") or ids.get("tvdb") or f"{show.get('title')}-{first_aired}")
        if uid in seen:
            continue
        seen.add(uid)

        aired = datetime.fromisoformat(first_aired.replace("Z", "+00:00")).astimezone(tz)
        available = aired + timedelta(hours=1)
        tag = _tag_for(item, item.get("_source", "shows"))
        title = show.get("title") or "Unknown show"
        meta = tvmaze.lookup(title)

        schedule.append(
            {
                "show": title,
                "episode": episode.get("title") or "",
                "season": episode.get("season"),
                "number": episode.get("number"),
                "tag": tag or "New Episode",
                "air_time": aired.isoformat(),
                "available_time": available.isoformat(),
                "available_label": _format_available(available),
                "poster": meta["poster"],
                "rating": meta["rating"],
                "imdb_url": meta["imdb_url"],
                "network": meta["network"] or show.get("network") or "",
                "trakt_url": _trakt_url(show),
            }
        )
    return schedule


def _trakt_url(show: dict) -> str:
    ids = show.get("ids") or {}
    slug = ids.get("slug")
    return f"https://trakt.tv/shows/{slug}" if slug else "https://trakt.tv"


def _format_available(value: datetime) -> str:
    return f"{value.strftime('%a, %b')} {value.day} at {value.strftime('%I:%M %p %Z').lstrip('0')}"
