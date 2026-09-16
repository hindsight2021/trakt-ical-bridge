from trakt_ical_bridge.nuvio import NuvioSelection, adb_launch_command


def test_episode_launch_command_contains_direct_stream_extras():
    command = adb_launch_command(NuvioSelection(
        content_id="tt0058792", content_type="series", title="The Golden Girls",
        season=2, episode=4, episode_title="It's a Miserable Life",
    ))
    assert "com.nuvio.tv.plus/com.nuvio.tv.MainActivity" in command
    assert '--es launchMode "stream"' in command
    assert '--es videoId "tt0058792:2:4"' in command
    assert "--ei season 2" in command
    assert "--ei episode 4" in command
    assert '--es episodeTitle "It\'s a Miserable Life"' in command


def test_movie_launch_omits_episode_extras():
    command = adb_launch_command(NuvioSelection(
        content_id="tt0111161", content_type="movie", title="The Shawshank Redemption"
    ))
    assert '--es videoId "tt0111161"' in command
    assert "--ei season" not in command
    assert "--ei episode" not in command
