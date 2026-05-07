from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from hashlib import sha1
from zoneinfo import ZoneInfo


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _fold(line: str) -> list[str]:
    limit = 75
    if len(line) <= limit:
        return [line]
    parts = [line[:limit]]
    line = line[limit:]
    while line:
        parts.append(" " + line[: limit - 1])
        line = line[limit - 1 :]
    return parts


def _stamp(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _episode_code(episode: dict) -> str:
    season = episode.get("season")
    number = episode.get("number")
    if season is None or number is None:
        return ""
    return f"S{int(season):02d}E{int(number):02d}"


def _event_title(item: dict, tag: str | None) -> str:
    show = item.get("show") or {}
    episode = item.get("episode") or {}
    bits = [show.get("title") or "Unknown show"]
    code = _episode_code(episode)
    if code:
        bits.append(code)
    if episode.get("title"):
        bits.append(episode["title"])
    title = " - ".join(bits)
    return f"{tag}: {title}" if tag else title


def _description(item: dict, tag: str | None) -> str:
    show = item.get("show") or {}
    episode = item.get("episode") or {}
    lines = []
    if tag:
        lines.append(tag)
    if episode.get("overview"):
        lines.append(episode["overview"])
    if show.get("overview"):
        lines.append("")
        lines.append(f"Show: {show['overview']}")
    if show.get("network"):
        lines.append("")
        lines.append(f"Network: {show['network']}")
    return "\n".join(lines)


def _url(item: dict) -> str:
    show = item.get("show") or {}
    episode = item.get("episode") or {}
    ids = episode.get("ids") or show.get("ids") or {}
    slug = ids.get("slug")
    return f"https://trakt.tv/shows/{slug}" if slug else "https://trakt.tv"


def _tag_for(item: dict, source: str) -> str | None:
    episode = item.get("episode") or {}
    season = episode.get("season")
    number = episode.get("number")
    if source == "premieres":
        return "Season Premiere"
    if source == "new":
        return "New Show"
    if source == "finales":
        return "Season Finale"
    if season == 1 and number == 1:
        return "New Show"
    if number == 1:
        return "Season Premiere"
    return None


def build_calendar(items: list[dict], calendar_name: str, tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    now = datetime.now(timezone.utc)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Trakt iCal Bridge//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(calendar_name)}",
        f"X-WR-TIMEZONE:{tz_name}",
        "X-PUBLISHED-TTL:PT6H",
    ]

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

        start = datetime.fromisoformat(first_aired.replace("Z", "+00:00")).astimezone(tz)
        end = start + timedelta(hours=1)
        episode = item.get("episode") or {}
        show = item.get("show") or {}
        ids = episode.get("ids") or {}
        uid_source = f"{ids.get('trakt') or ids.get('tvdb') or first_aired}-{show.get('title')}"
        uid = f"{sha1(uid_source.encode('utf-8')).hexdigest()}@trakt-ical-bridge"
        if uid in seen:
            continue
        seen.add(uid)

        tag = _tag_for(item, item.get("_source", "shows"))
        event_lines = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{_stamp(now)}",
            f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{_escape(_event_title(item, tag))}",
            f"DESCRIPTION:{_escape(_description(item, tag))}",
            f"URL:{_escape(_url(item))}",
            "END:VEVENT",
        ]
        for line in event_lines:
            lines.extend(_fold(line))

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def http_date() -> str:
    return format_datetime(datetime.now(timezone.utc), usegmt=True)
