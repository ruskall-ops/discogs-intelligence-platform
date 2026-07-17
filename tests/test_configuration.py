from __future__ import annotations

import unittest

from dip.config import SETTINGS


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


if __name__ == "__main__":
    unittest.main()
