from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "src/dip"


class MarketplaceHistoryArchitectureTestCase(unittest.TestCase):
    def test_domain_contract_has_no_sqlite_application_ui_network_or_clock_coupling(
        self,
    ) -> None:
        source = source_for(SOURCE_ROOT / "marketplace_history")

        for forbidden in (
            "sqlite3",
            "dip.persistence",
            "dip.app",
            "dip.experience",
            "tkinter",
            "requests",
            "urllib",
            "httpx",
            "datetime.now",
            "datetime.utcnow",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_application_service_depends_on_domain_contract_not_sqlite_or_ui(
        self,
    ) -> None:
        source = (
            SOURCE_ROOT / "app/marketplace_history.py"
        ).read_text(encoding="utf-8")

        self.assertIn("MarketplaceHistoryRepository", source)
        for forbidden in (
            "SQLiteMarketplaceHistoryRepository",
            "sqlite3",
            "dip.persistence",
            "dip.experience",
            "WeekendListingsModule",
            "IntelligenceEngine",
            "tkinter",
            "requests",
            "urllib",
            "httpx",
            "datetime.now",
            "datetime.utcnow",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_sqlite_adapter_reuses_serializer_without_ui_network_or_module_logic(
        self,
    ) -> None:
        source = (
            SOURCE_ROOT / "persistence/sqlite/marketplace_history.py"
        ).read_text(encoding="utf-8")

        self.assertIn("dumps_marketplace_snapshot", source)
        self.assertIn("loads_marketplace_snapshot", source)
        self.assertNotIn("float(", source)
        for forbidden in (
            "dip.experience",
            "dip.app",
            "WeekendListingsModule",
            "IntelligenceEngine",
            "tkinter",
            "requests",
            "urllib",
            "httpx",
            "datetime.now",
            "datetime.utcnow",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_concrete_repository_is_wired_only_at_persistence_and_composition(
        self,
    ) -> None:
        allowed = {
            SOURCE_ROOT / "composition.py",
            SOURCE_ROOT / "persistence/sqlite/__init__.py",
            SOURCE_ROOT / "persistence/sqlite/marketplace_history.py",
        }
        occurrences = {
            path
            for path in SOURCE_ROOT.rglob("*.py")
            if "SQLiteMarketplaceHistoryRepository"
            in path.read_text(encoding="utf-8")
        }

        self.assertTrue(occurrences)
        self.assertEqual(occurrences - allowed, set())
        composition = (SOURCE_ROOT / "composition.py").read_text(encoding="utf-8")
        self.assertIn("MarketplaceHistoryQueryService", composition)
        self.assertIn("MarketplaceHistoryCommandService", composition)
        self.assertIn("SQLiteMarketplaceHistoryRepository", composition)

    def test_dashboard_explorer_weekend_and_desktop_are_not_integrated(self) -> None:
        integration_files = {
            SOURCE_ROOT / "app/dashboard.py",
            SOURCE_ROOT / "app/collection_explorer_presentation.py",
            SOURCE_ROOT / "app/weekend_listings_presentation.py",
            SOURCE_ROOT / "marketplace_intelligence/weekend_listings.py",
            SOURCE_ROOT / "experience/desktop/app.py",
        }
        for package in (
            SOURCE_ROOT / "experience/dashboard",
            SOURCE_ROOT / "experience/explorer",
            SOURCE_ROOT / "experience/weekend_listings",
        ):
            integration_files.update(package.rglob("*.py"))

        for path in sorted(integration_files):
            source = path.read_text(encoding="utf-8")
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn("MarketplaceHistory", source)
                self.assertNotIn("marketplace_history", source)

    def test_repository_contract_is_append_only(self) -> None:
        source = (
            SOURCE_ROOT / "marketplace_history/repository.py"
        ).read_text(encoding="utf-8")

        self.assertIn("def save_snapshot", source)
        self.assertIn("def get_snapshot", source)
        self.assertNotIn("def update", source)
        self.assertNotIn("def delete", source)


def source_for(directory: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(directory.glob("*.py"))
    )


if __name__ == "__main__":
    unittest.main()
