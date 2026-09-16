from trakt_ical_bridge.ics import build_calendar
from trakt_ical_bridge.trakt import TraktClient
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


def test_refresh_token_does_not_send_redirect_uri(tmp_path, monkeypatch):
    settings = Settings(
        trakt_client_id="client",
        trakt_client_secret="secret",
        trakt_redirect_uri="http://lan-host:8765/auth/callback",
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
    )
    client = TraktClient(settings)
    client._save_token({"refresh_token": "refresh", "access_token": "expired", "expires_in": 0})
    captured = {}

    def fake_post_token(payload):
        captured.update(payload)
        return {"refresh_token": "next", "access_token": "fresh", "expires_in": 3600}

    monkeypatch.setattr(client, "_post_token", fake_post_token)

    assert client._access_token() == "fresh"
    assert captured["grant_type"] == "refresh_token"
    assert "redirect_uri" not in captured
