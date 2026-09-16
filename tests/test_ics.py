from trakt_ical_bridge.ics import build_calendar
from trakt_ical_bridge.simkl import SimklClient
from trakt_ical_bridge.config import Settings
from pathlib import Path


def test_build_calendar_dedupes_and_marks_premiere():
    items = [
        {
            "_source": "shows",
            "first_aired": "2026-05-08T01:00:00.000Z",
            "show": {"title": "Example Show", "ids": {"slug": "example-show"}},
            "episode": {
                "season": 2,
                "number": 1,
                "title": "A Return",
                "overview": "The show comes back.",
                "ids": {"trakt": 123},
            },
        },
        {
            "_source": "premieres",
            "first_aired": "2026-05-08T01:00:00.000Z",
            "show": {"title": "Example Show", "ids": {"slug": "example-show"}},
            "episode": {
                "season": 2,
                "number": 1,
                "title": "A Return",
                "overview": "The show comes back.",
                "ids": {"trakt": 123},
            },
        },
    ]

    ics = build_calendar(items, "Trakt Shows", "America/Moncton")

    assert ics.startswith("BEGIN:VCALENDAR")
    assert ics.count("BEGIN:VEVENT") == 1
    assert "SUMMARY:Season Premiere: Example Show - S02E01 - A Return" in ics


def test_special_tags_win_over_plain_calendar_items():
    items = [
        {
            "_source": "shows",
            "first_aired": "2026-05-08T01:00:00.000Z",
            "show": {"title": "Example Show", "ids": {"slug": "example-show"}},
            "episode": {"season": 2, "number": 8, "title": "End", "ids": {"trakt": 456}},
        },
        {
            "_source": "finales",
            "first_aired": "2026-05-08T01:00:00.000Z",
            "show": {"title": "Example Show", "ids": {"slug": "example-show"}},
            "episode": {"season": 2, "number": 8, "title": "End", "ids": {"trakt": 456}},
        },
    ]

    ics = build_calendar(items, "Trakt Shows", "America/Moncton")

    assert ics.count("BEGIN:VEVENT") == 1
    assert "SUMMARY:Season Finale: Example Show - S02E08 - End" in ics


def test_simkl_pin_is_saved(tmp_path, monkeypatch):
    settings = Settings(
        simkl_client_id="client",
        simkl_client_secret="secret",
        public_base_url="http://lan-host:8765",
        calendar_token="calendar-token",
        data_dir=Path(tmp_path),
        days_ahead=90,
        days_back=1,
        timezone="America/Moncton",
        include_premieres=True,
        include_new_shows=False,
        include_finales=True,
        cache_seconds=60,
        public_schedule=True,
        schedule_days=14,
    )
    client = SimklClient(settings)
    monkeypatch.setattr(client, "_get_json", lambda *args, **kwargs: {"result": "OK", "access_token": "fresh"})

    assert client.poll_pin("ABCDE")["access_token"] == "fresh"
    assert client.authorized()
    assert "fresh" in client.token_path.read_text(encoding="utf-8")


def test_simkl_calendar_normalizes_episode():
    item = SimklClient._normalize(
        {
            "title": "Example Show",
            "date": "2026-09-20T21:00:00-03:00",
            "url": "https://simkl.com/tv/42/example-show",
            "ids": {"simkl_id": 42, "slug": "example-show", "imdb": "tt42"},
            "episode": {"season": 2, "episode": 3, "url": "https://simkl.com/tv/42/example-show/2/3"},
        },
        "tv",
    )

    assert item["show"]["title"] == "Example Show"
    assert item["episode"]["season"] == 2
    assert item["episode"]["number"] == 3
    assert item["_provider_url"].endswith("/2/3")
