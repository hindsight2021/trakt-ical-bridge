from trakt_ical_bridge.ics import build_calendar


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
