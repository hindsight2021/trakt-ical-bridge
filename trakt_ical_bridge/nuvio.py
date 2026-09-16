from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import requests


CINEMETA_BASE = "https://v3-cinemeta.strem.io"


class NuvioLookupError(RuntimeError):
    pass


@dataclass(frozen=True)
class NuvioSelection:
    content_id: str
    content_type: str
    title: str
    season: int | None = None
    episode: int | None = None
    episode_title: str = ""
    poster: str = ""
    background: str = ""
    logo: str = ""

    @property
    def video_id(self) -> str:
        if self.content_type == "series" and self.season is not None and self.episode is not None:
            return f"{self.content_id}:{self.season}:{self.episode}"
        return self.content_id


class NuvioCatalog:
    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout

    def _json(self, path: str) -> dict:
        try:
            response = requests.get(f"{CINEMETA_BASE}{path}", timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            raise NuvioLookupError(f"Nuvio catalog lookup failed: {exc}") from exc

    def search(self, query: str, content_type: str = "series") -> list[dict]:
        media_type = "movie" if content_type == "movie" else "series"
        query = query.strip()
        if not query:
            return []
        payload = self._json(f"/catalog/{media_type}/top/search={quote(query, safe='')}.json")
        return [
            {
                "id": item.get("id", ""),
                "type": media_type,
                "title": item.get("name", ""),
                "poster": item.get("poster", ""),
                "background": item.get("background", ""),
                "year": item.get("releaseInfo", ""),
            }
            for item in payload.get("metas", [])[:12]
            if item.get("id") and item.get("name")
        ]

    def details(self, content_id: str, content_type: str = "series") -> dict:
        media_type = "movie" if content_type == "movie" else "series"
        content_id = content_id.strip()
        if not content_id:
            raise NuvioLookupError("A content ID is required.")
        meta = self._json(f"/meta/{media_type}/{quote(content_id, safe=':')}.json").get("meta") or {}
        if not meta:
            raise NuvioLookupError("The selected title was not found.")
        episodes = []
        for video in meta.get("videos") or []:
            season = video.get("season")
            episode = video.get("number")
            if season is None or episode is None:
                continue
            episodes.append({
                "season": int(season),
                "episode": int(episode),
                "title": video.get("title") or video.get("name") or "",
                "id": video.get("id") or f"{content_id}:{season}:{episode}",
            })
        episodes.sort(key=lambda item: (item["season"], item["episode"]))
        return {
            "id": content_id,
            "type": media_type,
            "title": meta.get("name") or content_id,
            "poster": meta.get("poster") or "",
            "background": meta.get("background") or "",
            "logo": meta.get("logo") or "",
            "episodes": episodes,
            "seasons": sorted({item["season"] for item in episodes}),
        }

    def resolve(self, title: str, content_type: str, season: int | None, episode: int | None) -> NuvioSelection:
        matches = self.search(title, content_type)
        if not matches:
            raise NuvioLookupError(f'No Nuvio title matched "{title}".')
        exact = next((item for item in matches if item["title"].casefold() == title.strip().casefold()), matches[0])
        details = self.details(exact["id"], exact["type"])
        episode_title = ""
        if exact["type"] == "series":
            if season is None or episode is None:
                raise NuvioLookupError("Series playback requires a season and episode.")
            selected = next(
                (item for item in details["episodes"] if item["season"] == season and item["episode"] == episode),
                None,
            )
            if not selected:
                raise NuvioLookupError(f"Season {season} episode {episode} is not available for {details['title']}.")
            episode_title = selected["title"]
        return NuvioSelection(
            content_id=details["id"], content_type=details["type"], title=details["title"],
            season=season, episode=episode, episode_title=episode_title,
            poster=details["poster"], background=details["background"], logo=details["logo"],
        )


def adb_launch_command(selection: NuvioSelection, package: str = "com.nuvio.tv.plus") -> str:
    component = f"{package}/com.nuvio.tv.MainActivity"
    def esc(value: object) -> str:
        return str(value).replace("\\", "\\\\").replace('"', '\\"')

    args = [
        "am start -W -a android.intent.action.MAIN",
        f'-n "{esc(component)}"',
        f'--es contentId "{esc(selection.content_id)}"',
        f'--es contentType "{esc(selection.content_type)}"',
        '--es launchMode "stream"',
        f'--es videoId "{esc(selection.video_id)}"',
        f'--es name "{esc(selection.title)}"',
        '--ez android.intent.extra.START_PLAYBACK true',
    ]
    for key, value in (("poster", selection.poster), ("backdrop", selection.background), ("logo", selection.logo)):
        if value:
            args.append(f'--es {key} "{esc(value)}"')
    if selection.season is not None:
        args.append(f"--ei season {selection.season}")
    if selection.episode is not None:
        args.append(f"--ei episode {selection.episode}")
    if selection.episode_title:
        args.append(f'--es episodeTitle "{esc(selection.episode_title)}"')
    return " ".join(args)
