from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Application-wide configuration for DIP."""

    application_name: str
    application_version: str
    database_path: Path
    discogs_request_delay_seconds: float
    window_width: int
    window_height: int


def load_settings() -> Settings:
    """Load settings from defaults with optional environment overrides."""

    application_name = os.getenv(
        "DIP_APPLICATION_NAME",
        "Discogs Intelligence Platform",
    )

    application_version = os.getenv(
        "DIP_APPLICATION_VERSION",
        "0.1-dev",
    )

    database_filename = os.getenv(
        "DIP_DATABASE_FILENAME",
        "discogs_intelligence.db",
    )

    request_delay = float(
        os.getenv(
            "DIP_DISCOGS_REQUEST_DELAY_SECONDS",
            "1.08",
        )
    )

    window_width = int(
        os.getenv(
            "DIP_WINDOW_WIDTH",
            "1380",
        )
    )

    window_height = int(
        os.getenv(
            "DIP_WINDOW_HEIGHT",
            "820",
        )
    )

    if request_delay < 0:
        raise ValueError(
            "DIP_DISCOGS_REQUEST_DELAY_SECONDS must be zero or greater."
        )

    if window_width < 800:
        raise ValueError(
            "DIP_WINDOW_WIDTH must be at least 800."
        )

    if window_height < 500:
        raise ValueError(
            "DIP_WINDOW_HEIGHT must be at least 500."
        )

    return Settings(
        application_name=application_name,
        application_version=application_version,
        database_path=Path(database_filename).expanduser().resolve(),
        discogs_request_delay_seconds=request_delay,
        window_width=window_width,
        window_height=window_height,
    )


SETTINGS = load_settings()