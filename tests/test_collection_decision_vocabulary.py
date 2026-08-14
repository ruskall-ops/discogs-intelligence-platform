from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from xml.etree import ElementTree
from zipfile import ZipFile

from dip.collection_decision_vocabulary import (
    CANONICAL_DECISIONS,
    CANONICAL_PRIORITIES,
    ReviewFilterChoiceKind,
    ReviewFilterField,
    review_filter_choices,
    validate_writable_decision,
)
from dip.persistence.sqlite import Database
from dip.experience.desktop.app import App
from dip.exports import export_excel


class _Variable:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Combobox:
    def configure(self, **values):
        self.values = values["values"]


class CollectionDecisionVocabularyTestCase(unittest.TestCase):
    def test_canonical_and_retained_choices_are_typed_ordered_and_collision_safe(self):
        choices = review_filter_choices(
            ReviewFilterField.DECISION,
            (
                "Review", "Research further", "Consider selling", "All",
                "review", "Retained: All", "Arbitrary legacy",
            ),
        )
        self.assertEqual(
            tuple(choice.query_value for choice in choices[:6]),
            (None, *CANONICAL_DECISIONS),
        )
        retained = choices[6:]
        self.assertTrue(all(
            choice.kind is ReviewFilterChoiceKind.RETAINED
            for choice in retained
        ))
        self.assertEqual(
            tuple(choice.query_value for choice in retained),
            (
                "All", "Arbitrary legacy", "Consider selling",
                "Research further", "Retained: All", "review",
            ),
        )
        self.assertEqual(len({choice.label for choice in choices}), len(choices))
        self.assertEqual(
            tuple(choice.query_value for choice in review_filter_choices(
                ReviewFilterField.PRIORITY, ("Monitor", "monitor")
            )[:6]),
            (None, *CANONICAL_PRIORITIES),
        )

    def test_writable_decisions_are_closed_and_strict(self):
        for value in CANONICAL_DECISIONS:
            self.assertEqual(validate_writable_decision(value), value)
        for value in ("Research further", "", " Review", "Review "):
            with self.assertRaises(ValueError):
                validate_writable_decision(value)
        for value in (True, 1, None):
            with self.assertRaises(TypeError):
                validate_writable_decision(value)

    def test_runtime_restoration_uses_identity_and_missing_retained_falls_to_all(self):
        previous = review_filter_choices(
            ReviewFilterField.DECISION, ("Research further",)
        )
        variable = _Variable("Retained: Research further")
        combobox = _Combobox()
        current = App._replace_review_filter_choices(
            variable, combobox, previous,
            review_filter_choices(
                ReviewFilterField.DECISION, ("Research further",)
            ),
        )
        self.assertEqual(variable.get(), "Retained: Research further")
        self.assertEqual(
            App._review_filter_query_value(variable.get(), current).query_value,
            "Research further",
        )
        App._replace_review_filter_choices(
            variable, combobox, current,
            review_filter_choices(ReviewFilterField.DECISION, ()),
        )
        self.assertEqual(variable.get(), "All")

    def test_real_repository_discovers_and_exactly_filters_retained_values(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "review.sqlite3")
            try:
                database.conn.executemany(
                    "INSERT INTO releases(release_id, artist, title) VALUES (?, 'A', 'T')",
                    ((1,), (2,), (3,), (4,)),
                )
                database.conn.executemany(
                    "INSERT INTO scores(release_id, calculated_at, priority) VALUES (?, '2026-08-14T00:00:00+00:00', ?)",
                    ((1, "Worth reviewing"), (2, "Monitor"), (3, "monitor")),
                )
                database.conn.executemany(
                    "INSERT INTO decisions(release_id, decision) VALUES (?, ?)",
                    ((1, "Keep"), (2, "Research further"), (3, "All")),
                )
                database.conn.commit()
                priorities, decisions = database.review_filter_values()
                self.assertEqual(
                    priorities,
                    ("Monitor", "Not scored", "Worth reviewing", "monitor"),
                )
                self.assertEqual(
                    decisions,
                    ("All", "Keep", "Research further", "Review"),
                )
                for value, release_id in (
                    ("Research further", 2), ("All", 3)
                ):
                    selection = next(
                        choice for choice in review_filter_choices(
                            ReviewFilterField.DECISION, decisions
                        )
                        if choice.query_value == value
                        and choice.kind is ReviewFilterChoiceKind.RETAINED
                    )
                    self.assertEqual(
                        tuple(row["release_id"] for row in database.review_rows(
                            decision=selection
                        )),
                        (release_id,),
                    )
                self.assertEqual(
                    tuple(row["release_id"] for row in database.review_rows(
                        priority="Monitor"
                    )),
                    (2,),
                )
                self.assertEqual(
                    tuple(row["release_id"] for row in database.review_rows(
                        priority="Not scored", decision="Review"
                    )),
                    (4,),
                )
                database.save_decision(4, "Ignore", "Unsure", "", False)
                self.assertEqual(
                    database.conn.execute(
                        "SELECT decision FROM decisions WHERE release_id = 4"
                    ).fetchone()[0],
                    "Ignore",
                )
                with self.assertRaises(ValueError):
                    database.save_decision(
                        4, "Research further", "Unsure", "", False
                    )
                self.assertEqual(
                    database.conn.execute(
                        "SELECT decision FROM decisions WHERE release_id = 4"
                    ).fetchone()[0],
                    "Ignore",
                )
            finally:
                database.close()

    def test_retained_storage_and_export_values_are_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = Database(root / "review.sqlite3")
            retained = ("Research further", "Consider selling", "All", "review")
            try:
                database.conn.executemany(
                    "INSERT INTO releases(release_id, artist, title) VALUES (?, 'A', 'T')",
                    ((index,) for index in range(1, len(retained) + 1)),
                )
                database.conn.executemany(
                    "INSERT INTO decisions(release_id, decision) VALUES (?, ?)",
                    enumerate(retained, start=1),
                )
                database.conn.commit()
                before = tuple(
                    row[0] for row in database.conn.execute(
                        "SELECT decision FROM decisions ORDER BY release_id"
                    )
                )
                path = root / "retained.xlsx"
                export_excel(path, database.review_rows())
                after = tuple(
                    row[0] for row in database.conn.execute(
                        "SELECT decision FROM decisions ORDER BY release_id"
                    )
                )
                self.assertEqual(before, retained)
                self.assertEqual(after, retained)
                with ZipFile(path) as workbook:
                    shared = ElementTree.fromstring(
                        workbook.read("xl/sharedStrings.xml")
                    )
                namespace = {
                    "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                }
                exported = tuple(
                    "".join(node.itertext())
                    for node in shared.findall("x:si", namespace)
                )
                for value in retained:
                    self.assertIn(value, exported)
            finally:
                database.close()

    def test_migrations_remain_exactly_one_through_seven(self):
        versions = Path("src/dip/persistence/sqlite/migrations/versions")
        self.assertEqual(
            tuple(path.name for path in sorted(versions.glob("v*.py"))),
            (
                "v001_add_analysis_run_id.py",
                "v002_add_intelligence_history.py",
                "v003_add_marketplace_history.py",
                "v004_add_projects.py",
                "v005_add_intelligence_marketplace_provenance.py",
                "v006_add_weekend_review_queue.py",
                "v007_add_desktop_session.py",
            ),
        )


if __name__ == "__main__":
    unittest.main()
