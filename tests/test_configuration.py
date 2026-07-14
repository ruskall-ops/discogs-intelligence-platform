from __future__ import annotations

from config import SETTINGS


def test_configuration() -> None:
    """Verify the default application configuration."""

    assert SETTINGS.application_name
    assert SETTINGS.application_version
    assert SETTINGS.database_path

    assert SETTINGS.discogs_request_delay_seconds >= 0

    assert SETTINGS.window_width >= 800
    assert SETTINGS.window_height >= 500