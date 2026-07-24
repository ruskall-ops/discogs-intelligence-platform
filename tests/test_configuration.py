from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from dip import __version__
from dip.config import SETTINGS, load_settings
from dip.data_sources.discogs.client import DiscogsClient


class ConfigurationTestCase(unittest.TestCase):
    def test_configuration(self) -> None:
        """Verify the default application configuration."""

        self.assertTrue(SETTINGS.application_name)
        self.assertTrue(SETTINGS.application_version)
        self.assertTrue(SETTINGS.database_path)

        self.assertGreaterEqual(
            SETTINGS.discogs_request_delay_seconds,
            0,
        )

        self.assertGreaterEqual(SETTINGS.window_width, 800)
        self.assertGreaterEqual(SETTINGS.window_height, 500)

    def test_default_application_version_matches_package_version(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = load_settings()

        self.assertEqual(settings.application_version, __version__)

    def test_application_version_environment_override_is_preserved(self) -> None:
        with patch.dict(
            os.environ,
            {"DIP_APPLICATION_VERSION": "test-build"},
            clear=True,
        ):
            settings = load_settings()

        self.assertEqual(settings.application_version, "test-build")

    def test_discogs_user_agent_uses_package_version(self) -> None:
        client = DiscogsClient("test-token")

        self.assertEqual(
            client.session.headers["User-Agent"],
            f"RussellDiscogsIntelligencePlatform/{__version__}",
        )


if __name__ == "__main__":
    unittest.main()
