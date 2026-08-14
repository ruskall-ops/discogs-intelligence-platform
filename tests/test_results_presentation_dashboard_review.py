from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import os
from pathlib import Path
from types import MappingProxyType, SimpleNamespace
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import Mock, patch

from dip.experience.collector_review_presentation import (
    COLLECTION_DECISION_COLUMNS,
    CollectionDecisionColumn,
    CollectionDecisionColumnId,
    ColumnAnchor,
    DisabledActionReason,
    ReviewDetailSection,
    ReviewDetailSectionKind,
    WarningProjectionState,
    decision_row_values,
    format_count,
    format_price,
    format_score,
    observation_detail_sections,
    public_warning_lines,
)
from tests.test_collector_review_desktop import _workspace
from dip.experience.desktop.app import App
from dip.experience.dashboard import DashboardHomepageViewModelBuilder
from dip.experience.desktop.hidden_gems_renderer import DesktopHiddenGemsController
from dip.collector_review import (
    ObservationWarning, QueueMembership, WeekendObservationSource,
    WeekendReviewQueueItem,
    WeekendReviewStatus,
)
from dip.persistence.sqlite import Database
from tests.test_dashboard_homepage import candidate, execution, health_record, hidden_record


class CollectionReviewPresentationTestCase(unittest.TestCase):
    def test_real_sqlite_missing_zero_nonzero_survives_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.sqlite3"
            database = Database(path)
            try:
                database.conn.executemany(
                    "INSERT INTO releases(release_id, artist, title) VALUES (?, ?, ?)",
                    ((1, "Missing", "Facts"), (2, "Zero", "Facts"), (3, "Nonzero", "Facts")),
                )
                database.conn.executemany(
                    "INSERT INTO scores(release_id, calculated_at, value_score, demand_score, liquidity_score, momentum_score, opportunity_score, sell_window, priority, explanation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        (2, "2026-08-12T10:00:00+00:00", 0, 0, 0, 0, 0, "Stable", "Worth reviewing", "Zero facts"),
                        (3, "2026-08-12T10:00:00+00:00", 1.0, 2.25, -3.5, 4.0, 87.125, "Stable", "Worth reviewing", "Nonzero facts"),
                    ),
                )
                database.conn.executemany(
                    "INSERT INTO market_snapshots(release_id, captured_at, wants, haves, copies_for_sale, lowest_price, currency) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        (2, "2026-08-12T10:00:00+00:00", 0, 0, 0, 0, "GBP"),
                        (3, "2026-08-12T10:00:00+00:00", 12, 15, 3, 19.5, "GBP"),
                    ),
                )
                database.conn.commit()
            finally:
                database.close()
            for reopened in (Database(path), Database(path)):
                try:
                    rows = {row["release_id"]: row for row in reopened.review_rows()}
                    numeric_fields = (
                        "lowest_price", "wants", "haves", "copies_for_sale",
                        "value_score", "demand_score", "liquidity_score",
                        "momentum_score", "opportunity_score",
                    )
                    self.assertEqual(tuple(rows[1][key] for key in numeric_fields), (None,) * 9)
                    self.assertEqual(tuple(rows[2][key] for key in numeric_fields), (0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0))
                    self.assertEqual(
                        tuple(rows[3][key] for key in numeric_fields),
                        (19.5, 12, 15, 3, 1.0, 2.25, -3.5, 4.0, 87.125),
                    )
                    self.assertEqual(decision_row_values(rows[1])[2:6], ("—", "—", "—", "—"))
                    self.assertEqual(decision_row_values(rows[2])[2:6], ("0.00", "0", "0", "0.0"))
                    self.assertEqual(decision_row_values(rows[3])[2:6], ("19.50", "12", "3", "87.1"))
                    self.assertIsInstance(rows[3]["lowest_price"], float)
                    for key in ("wants", "haves", "copies_for_sale"):
                        self.assertIsInstance(rows[3][key], int)
                    for key in ("value_score", "demand_score", "liquidity_score", "momentum_score", "opportunity_score"):
                        self.assertIsInstance(rows[3][key], float)
                finally:
                    reopened.close()

    def test_column_alignment_and_overflow_contract(self) -> None:
        anchors = {column.column_id: column.anchor for column in COLLECTION_DECISION_COLUMNS}
        self.assertEqual(anchors[CollectionDecisionColumnId.ARTIST], ColumnAnchor.LEFT)
        self.assertEqual(anchors[CollectionDecisionColumnId.TITLE], ColumnAnchor.LEFT)
        for column in (CollectionDecisionColumnId.PRICE, CollectionDecisionColumnId.WANTS, CollectionDecisionColumnId.SUPPLY, CollectionDecisionColumnId.OPPORTUNITY):
            self.assertEqual(anchors[column], ColumnAnchor.RIGHT)
        self.assertGreater(sum(column.width for column in COLLECTION_DECISION_COLUMNS), 800)

    def test_missing_zero_and_exact_decimal_text_remain_distinct(self) -> None:
        self.assertEqual(format_price(None), "—")
        self.assertEqual(format_price(0), "0.00")
        self.assertEqual(format_price(Decimal("12.3400")), "12.34")
        self.assertEqual(format_score(0.0), "0.0")
        self.assertEqual(format_score(87.125), "87.1")
        self.assertEqual(format_score(12.0), "12.0")
        self.assertEqual(format_score(-3.5), "-3.5")
        self.assertEqual(format_price(-2.25), "-2.25")
        self.assertEqual(format_count(0), "0")
        for formatter in (format_price, format_score, format_count):
            with self.assertRaises(TypeError):
                formatter(True)

    def test_decision_projection_preserves_identity_source_and_values(self) -> None:
        row = MappingProxyType(
            {
                "release_id": 42,
                "artist": "A" * 400,
                "title": "T" * 600,
                "lowest_price": Decimal("0.00"),
                "wants": 0,
                "copies_for_sale": None,
                "opportunity_score": Decimal("87.125"),
                "sell_window": "Current classification",
                "priority": "Worth reviewing",
                "decision": "Review",
            }
        )
        before = dict(row)
        values = decision_row_values(row)
        self.assertEqual(values[2:6], ("0.00", "0", "—", "87.1"))
        self.assertEqual(values[0], "A" * 400)
        self.assertEqual(values[1], "T" * 600)
        self.assertEqual(dict(row), before)

    def test_typed_observation_detail_has_required_hierarchy(self) -> None:
        observation = _workspace(1).hot_now[0]
        sections = observation_detail_sections(observation)
        self.assertEqual(
            tuple(section.kind for section in sections),
            (ReviewDetailSectionKind.CALCULATED, ReviewDetailSectionKind.QUEUE_STATE),
        )
        self.assertIn("Current catalogue label:", sections[0].lines[0])
        self.assertEqual(sections[-1].lines, ("State: Not queued",))

    def test_public_values_are_closed_validated_and_defensively_immutable(self) -> None:
        with self.assertRaises(TypeError):
            CollectionDecisionColumn("artist", "Artist", 10, ColumnAnchor.LEFT)  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            CollectionDecisionColumn(CollectionDecisionColumnId.ARTIST, "Artist", True, ColumnAnchor.LEFT)
        with self.assertRaises(ValueError):
            ReviewDetailSection(ReviewDetailSectionKind.CALCULATED, ("",))
        supplied = ["Line"]
        section = ReviewDetailSection(ReviewDetailSectionKind.CALCULATED, supplied)
        supplied.append("Changed")
        self.assertEqual(section.lines, ("Line",))

    def test_hostile_warning_payloads_map_only_to_fixed_copy(self) -> None:
        sentinels = (
            "TOKEN-secret", "provider body", "SELECT * FROM private_table",
            "/private/live.sqlite", "/destination/private", '{"serialized":"row"}',
            "unknown-code", "£999 supply=88", "PERSONAL NOTE",
        )
        warnings = tuple(type("Warning", (), {"code": value, "message": value})() for value in sentinels)
        public = public_warning_lines(WarningProjectionState.EVIDENCE_LIMITED, warnings)
        rendered = repr((public, tuple(DisabledActionReason)))
        for sentinel in sentinels:
            self.assertNotIn(sentinel, rendered)
        self.assertEqual(public, ("• Some supplied Marketplace evidence was incomplete.",))
        self.assertEqual(
            public_warning_lines(WarningProjectionState.SUPPRESSED, warnings),
            (),
        )
        with self.assertRaises(TypeError):
            public_warning_lines("evidence_limited", warnings)  # type: ignore[arg-type]

    def test_warning_policy_is_deterministic_deduplicated_and_state_aware(self) -> None:
        known = type(
            "Warning", (),
            {"code": "hot_now_score_stale", "message": "HOSTILE"},
        )()
        unknown = type(
            "Warning", (), {"code": "unknown", "message": "HOSTILE-2"},
        )()
        self.assertEqual(
            public_warning_lines(
                WarningProjectionState.EVIDENCE_LIMITED,
                (known, known, unknown, unknown),
            ),
            (
                "• Newer usable Marketplace evidence exists for this release.",
                "• Some supplied Marketplace evidence was incomplete.",
            ),
        )
        self.assertEqual(
            public_warning_lines(
                WarningProjectionState.SUPPRESSED,
                (known, unknown),
            ),
            (),
        )

    def test_large_volume_projection_is_deterministic_and_non_mutating(self) -> None:
        rows = tuple(
            {
                "release_id": index,
                "artist": f"Artist {index}" * 8,
                "title": f"Title {index}" * 12,
                "lowest_price": None if index % 3 == 0 else Decimal(f"{index}.00"),
                "wants": index,
                "copies_for_sale": 0 if index % 2 == 0 else index + 1,
                "opportunity_score": Decimal("0") if index % 5 == 0 else Decimal("50.5"),
                "sell_window": "Unavailable" if index % 7 == 0 else "Stable",
                "priority": "Not scored" if index % 11 == 0 else "Worth reviewing",
                "decision": "Review",
            }
            for index in range(1, 1001)
        )
        first = tuple(decision_row_values(row) for row in rows)
        second = tuple(decision_row_values(row) for row in rows)
        self.assertEqual(first, second)
        self.assertEqual(tuple(row["release_id"] for row in rows), tuple(range(1, 1001)))

    def test_table_reload_preserves_visible_identity_and_does_not_substitute(self) -> None:
        for visible in (True, False):
            with self.subTest(visible=visible):
                app = App.__new__(App)
                app.tree = Mock()
                app.tree.selection.return_value = ("42",)
                app.tree.get_children.return_value = ()
                app.tree.exists.return_value = visible
                app.db = Mock()
                app.db.review_rows.return_value = (
                    {
                        "release_id": 42 if visible else 7,
                        "artist": "Artist",
                        "title": "Title",
                        "lowest_price": Decimal("12.00"),
                        "wants": 0,
                        "copies_for_sale": None,
                        "opportunity_score": Decimal("50.0"),
                        "sell_window": "Stable",
                        "priority": "Worth reviewing",
                        "decision": "Review",
                    },
                )
                app.search_var = Mock()
                app.search_var.get.return_value = ""
                app.priority_var = Mock()
                app.priority_var.get.return_value = "All"
                app.decision_filter_var = Mock()
                app.decision_filter_var.get.return_value = "All"
                app.status_var = Mock()
                self.assertTrue(app.load_table())
                if visible:
                    app.tree.selection_set.assert_called_once_with("42")
                    app.tree.see.assert_called_once_with("42")
                else:
                    app.tree.selection_set.assert_not_called()
                    app.tree.selection_remove.assert_called_once()


class Slice4ProductionTkTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                "import tkinter as tk; root=tk.Tk(); root.withdraw(); root.destroy()",
            ],
            capture_output=True,
            text=True,
        )
        if probe.returncode:
            if os.environ.get("DIP_REQUIRE_TK_TESTS") == "1":
                raise AssertionError(
                    "DIP_REQUIRE_TK_TESTS requires an operational Tk display: "
                    + probe.stderr
                )
            raise unittest.SkipTest("A real Tk display is unavailable.")

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.directory.name) / "ui.sqlite3")
        dependencies = SimpleNamespace(
            database=self.database,
            dashboard_homepage=Mock(),
            collection_health_controller=Mock(),
            collection_explorer_controller=Mock(),
            hidden_gems_controller=DesktopHiddenGemsController(Mock()),
            portfolio_overview_controller=Mock(),
            portfolio_controller=Mock(),
        )
        self.dependencies = dependencies
        self.import_callback = patch.object(App, "import_csv", autospec=True)
        self.refresh_callback = patch.object(App, "start_refresh", autospec=True)
        self.import_mock = self.import_callback.start()
        self.refresh_mock = self.refresh_callback.start()
        with patch(
            "dip.experience.desktop.app.build_desktop_application_dependencies",
            return_value=dependencies,
        ), patch.object(App, "_restore_session_and_load"):
            self.root = App()
        self.root.geometry("800x560")
        self.root.update()
        for dependency in (
            dependencies.dashboard_homepage,
            dependencies.collection_health_controller,
            dependencies.collection_explorer_controller,
            dependencies.portfolio_overview_controller,
            dependencies.portfolio_controller,
        ):
            dependency.reset_mock()

    def tearDown(self) -> None:
        self.root.destroy()
        self.refresh_callback.stop()
        self.import_callback.stop()
        self.database.close()
        self.directory.cleanup()

    def test_real_tree_alignment_horizontal_overflow_and_mapping(self) -> None:
        self.database.conn.executemany(
            "INSERT INTO releases(release_id, artist, title) VALUES (?, ?, ?)",
            (
                (41, "Missing", "Evidence"),
                (42, "Artist" * 80, "Title" * 80),
                (43, "Nonzero", "Evidence"),
                (44, "Duplicate-looking", "Separate identity"),
                (45, "Duplicate-looking", "Separate identity"),
                *((release_id, f"Volume {release_id}", "Overflow") for release_id in range(100, 160)),
            ),
        )
        self.database.conn.executemany(
            "INSERT INTO market_snapshots(release_id, captured_at, wants, haves, copies_for_sale, lowest_price, currency) VALUES (?, '2026-08-12T10:00:00+00:00', ?, ?, ?, ?, 'GBP')",
            ((42, 0, 0, 0, 0), (43, 12, 15, 3, 19.5)),
        )
        self.database.conn.executemany(
            "INSERT INTO scores(release_id, calculated_at, value_score, demand_score, liquidity_score, momentum_score, opportunity_score, sell_window, priority, explanation) VALUES (?, '2026-08-12T10:00:00+00:00', ?, ?, ?, ?, ?, 'Stable', 'Worth reviewing', 'Facts')",
            ((42, 0, 0, 0, 0, 0), (43, 1.0, 2.25, 3.5, 4.0, 87.125)),
        )
        self.database.conn.executemany(
            "INSERT INTO scores(release_id, calculated_at, sell_window, priority) VALUES (?, '2026-08-12T10:00:00+00:00', 'Stable', ?)",
            (
                (44, "Monitor"), (45, "monitor"),
                (100, "High-priority review"),
                (101, "Possible candidate"), (102, "Low priority"),
            ),
        )
        self.database.conn.executemany(
            "INSERT INTO decisions(release_id, decision) VALUES (?, ?)",
            (
                (41, "Research further"), (42, "Keep"),
                (43, "Consider selling"), (44, "All"), (45, "review"),
                (100, "List for sale"), (101, "Maybe"), (102, "Ignore"),
            ),
        )
        self.database.conn.commit()
        rows = {row["release_id"]: row for row in self.database.review_rows()}
        self.assertEqual(
            tuple(rows[41][key] for key in (
                "lowest_price", "wants", "haves", "copies_for_sale",
                "value_score", "demand_score", "liquidity_score",
                "momentum_score", "opportunity_score",
            )),
            (None,) * 9,
        )
        self.assertEqual(decision_row_values(rows[41])[2:6], ("—", "—", "—", "—"))
        self.assertEqual(decision_row_values(rows[42])[2:6], ("0.00", "0", "0", "0.0"))
        self.assertEqual(decision_row_values(rows[43])[2:6], ("19.50", "12", "3", "87.1"))
        self.root.tabs.select(self.root.review_tab)
        self.root.collection_review_tabs.select(self.root.decisions_tab)
        tree = self.root.tree
        horizontal = self.root.decision_horizontal_scrollbar
        self.assertTrue(self.root.load_table())
        self.root.update_idletasks()
        self.assertTrue(tree.winfo_ismapped())
        self.assertTrue(tree.winfo_viewable())
        self.assertTrue(horizontal.winfo_ismapped())
        self.assertTrue(self.root.decision_vertical_scrollbar.winfo_ismapped())
        decision_trees = tuple(
            widget for widget in self.root.decisions_tab.winfo_children()
            for widget in widget.winfo_children()
            if isinstance(widget, ttk.Treeview)
            and widget.winfo_ismapped()
            and widget.winfo_viewable()
        )
        self.assertEqual(decision_trees, (tree,))
        self.assertEqual(tree.winfo_parent(), str(tree.master))
        self.assertEqual(
            tuple(tree.heading(column.column_id.value, "text") for column in COLLECTION_DECISION_COLUMNS),
            tuple(column.label for column in COLLECTION_DECISION_COLUMNS),
        )
        self.assertEqual(tuple(str(value) for value in tree.cget("show")), ("headings",))
        self.assertEqual(
            tuple(str(value) for value in tree.cget("displaycolumns")), ("#all",)
        )
        for column in ("price", "wants", "sale", "opportunity"):
            self.assertEqual(str(tree.column(column, "anchor")), "e")
        for column in ("artist", "title", "window", "priority", "decision"):
            self.assertEqual(str(tree.column(column, "anchor")), "w")
        self.assertLess(tree.xview()[1], 1.0)
        self.assertLess(tree.yview()[1], 1.0)
        tree.xview_moveto(1.0)
        tree.yview_moveto(1.0)
        self.root.update_idletasks()
        self.assertEqual(tree.xview()[1], 1.0)
        self.assertEqual(tree.yview()[1], 1.0)
        self.assertEqual(tree.item("41", "values")[2:6], ("—", "—", "—", "—"))
        self.assertEqual(tree.item("42", "values")[2:6], ("0.00", "0", "0", "0.0"))
        self.assertEqual(tree.item("43", "values")[2:6], ("19.50", "12", "3", "87.1"))
        self.assertEqual(tree.item("44", "values")[:2], tree.item("45", "values")[:2])
        duplicate_identity = tree.item("44", "values")[:2]
        self.assertEqual(
            {
                iid for iid in tree.get_children()
                if tree.item(iid, "values")[:2] == duplicate_identity
            },
            {"44", "45"},
        )
        tree.xview_moveto(0.0)
        displayed = tree.get_children()
        for release_id in (displayed[0], displayed[len(displayed) // 2], displayed[-1]):
            tree.see(release_id)
            self.root.update_idletasks()
            bbox = tree.bbox(release_id)
            self.assertTrue(bbox)
            x, y, width, height = bbox
            self.assertGreater(width, 0)
            self.assertGreater(height, 0)
            containing = self.root.winfo_containing(
                tree.winfo_rootx() + x + min(10, max(1, width // 2)),
                tree.winfo_rooty() + y + max(1, height // 2),
            )
            self.assertIs(containing, tree)
        tree.selection_set("42")
        self.assertTrue(self.root.load_table())
        self.assertEqual(tree.selection(), ("42",))
        self.root.search_var.set("Nonzero")
        self.assertTrue(self.root.load_table())
        self.assertEqual(tree.selection(), ())
        self.root.search_var.set("No synthetic row can match this filter")
        self.assertTrue(self.root.load_table())
        self.assertEqual(tree.get_children(), ())
        self.root.search_var.set("")
        self.assertTrue(self.root.load_table())
        self.assertEqual(len(tree.get_children()), 65)
        decision_labels = tuple(self.root.decision_filter.cget("values"))
        priority_labels = tuple(self.root.priority_filter.cget("values"))
        self.assertEqual(
            decision_labels[:6],
            ("All", "Review", "Keep", "List for sale", "Maybe", "Ignore"),
        )
        self.assertIn("Retained: Research further", decision_labels)
        self.assertIn("Retained: Consider selling", decision_labels)
        self.assertIn("Retained: All", decision_labels)
        self.assertIn("Retained: review", decision_labels)
        self.assertIn("Retained: Monitor", priority_labels)
        self.assertIn("Retained: monitor", priority_labels)
        self.assertEqual(
            {choice.query_value for choice in self.root._decision_filter_choices},
            {row["decision"] for row in self.database.review_rows()} | {None},
        )
        self.assertEqual(
            {choice.query_value for choice in self.root._priority_filter_choices},
            {row["priority"] for row in self.database.review_rows()} | {None},
        )
        changes_before_filters = self.database.conn.total_changes
        with patch.object(
            self.database, "review_rows", wraps=self.database.review_rows
        ) as review_rows:
            self.root.decision_filter_var.set("Retained: All")
            self.assertTrue(self.root.load_table())
            self.assertEqual(tree.get_children(), ("44",))
            self.assertEqual(
                review_rows.call_args.kwargs["decision"].query_value, "All"
            )
            self.root.decision_filter_var.set("All")
            self.root.priority_var.set("Retained: Monitor")
            self.assertTrue(self.root.load_table())
            self.assertEqual(tree.get_children(), ("44",))
            self.assertEqual(
                review_rows.call_args.kwargs["priority"].query_value, "Monitor"
            )
            self.root.priority_var.set("All")
            self.assertTrue(self.root.load_table())
            self.assertEqual(len(tree.get_children()), 65)
        self.assertEqual(self.database.conn.total_changes, changes_before_filters)
        self.import_mock.assert_not_called()
        self.refresh_mock.assert_not_called()
        for dependency in (
            self.dependencies.dashboard_homepage,
            self.dependencies.collection_health_controller,
            self.dependencies.collection_explorer_controller,
            self.dependencies.hidden_gems_controller._presentation,
            self.dependencies.portfolio_overview_controller,
            self.dependencies.portfolio_controller,
        ):
            dependency.assert_not_called()

    def test_production_dashboard_sections_and_complete_mapped_focus_cycle(self) -> None:
        traced_sql: list[str] = []
        self.root.tabs.select(self.root.dashboard_tab)
        self.root.update()
        self.assertEqual(
            tuple(section.cget("text") for section in self.root.dashboard_primary_sections),
            (
                "Current collection", "Latest completed intelligence",
                "Available destinations", "Unavailable destinations",
            ),
        )
        eligible = tuple(
            value for value in self.root._dip_dashboard_focus_order
            if self.root._focus_eligible(value)
        )
        self.assertEqual(len(eligible), len(set(eligible)))
        current = eligible[0]
        current.focus_force()
        visited = []
        for _ in eligible:
            visited.append(current)
            self.assertEqual(self.root._move_scoped_focus(current, True), "break")
            current = self.root.focus_get()
        self.assertIs(current, eligible[0])
        self.assertEqual(tuple(visited), eligible)
        for section in self.root.dashboard_primary_sections:
            self.root.dashboard_canvas.yview_moveto(
                section.winfo_y() / max(1, self.root.dashboard_content.winfo_reqheight())
            )
            self.root.update_idletasks()
            self.assertTrue(section.winfo_ismapped())

        canvas = self.root.dashboard_canvas
        nested = self.root.dashboard_primary_sections[0].winfo_children()[0]
        self.database.conn.set_trace_callback(traced_sql.append)
        changes_before = self.database.conn.total_changes
        canvas.yview_moveto(0.0)
        self.root.update_idletasks()
        start = canvas.yview()
        nested.event_generate("<MouseWheel>", delta=-120)
        self.root.update()
        self.assertGreater(canvas.yview()[0], start[0])
        for delta in (-1, -120):
            before = canvas.yview()
            self.assertEqual(
                self.root._scroll_dashboard_from_wheel(
                    SimpleNamespace(widget=nested, delta=delta, num=None)
                ),
                "break",
            )
            self.assertGreater(canvas.yview()[0], before[0])
        for number, direction in ((4, -1), (5, 1)):
            canvas.yview_moveto(0.5)
            before = canvas.yview()[0]
            self.assertEqual(
                self.root._scroll_dashboard_from_wheel(
                    SimpleNamespace(widget=nested, delta=0, num=number)
                ),
                "break",
            )
            self.assertEqual(canvas.yview()[0] > before, direction > 0)
        self.database.conn.set_trace_callback(None)
        self.assertEqual(traced_sql, [])
        self.assertEqual(self.database.conn.total_changes, changes_before)

        self.root.tabs.select(self.root.review_tab)
        self.root.collection_review_tabs.select(self.root.decisions_tab)
        self.database.conn.executemany(
            "INSERT INTO releases(release_id, artist, title) VALUES (?, ?, ?)",
            ((release_id, "Scrollable", f"Release {release_id}") for release_id in range(200, 260)),
        )
        self.database.conn.commit()
        self.assertTrue(self.root.load_table())
        self.root.update()
        traced_sql.clear()
        self.database.conn.set_trace_callback(traced_sql.append)
        changes_before = self.database.conn.total_changes
        canvas_before = canvas.yview()
        tree_before = self.root.tree.yview()
        self.assertIsNone(
            self.root._scroll_dashboard_from_wheel(
                SimpleNamespace(widget=self.root.tree, delta=-120, num=None)
            )
        )
        self.assertEqual(self.root.tree.yview(), tree_before)
        self.root.tree.yview_scroll(1, "units")
        self.assertGreater(self.root.tree.yview()[0], tree_before[0])
        self.assertEqual(canvas.yview(), canvas_before)

        retired = ttk.Label(self.root.dashboard_content, text="Retired")
        retired.destroy()
        canvas_before = canvas.yview()
        self.assertIsNone(
            self.root._scroll_dashboard_from_wheel(
                SimpleNamespace(widget=retired, delta=-120, num=None)
            )
        )
        self.assertEqual(canvas.yview(), canvas_before)
        self.database.conn.set_trace_callback(None)
        self.assertEqual(traced_sql, [])
        self.assertEqual(self.database.conn.total_changes, changes_before)
        self.root.dashboard_homepage_service.homepage.assert_not_called()
        self.import_mock.assert_not_called()
        self.refresh_mock.assert_not_called()
        for dependency in (
            self.dependencies.collection_health_controller,
            self.dependencies.collection_explorer_controller,
            self.dependencies.portfolio_overview_controller,
            self.dependencies.portfolio_controller,
        ):
            self.assertEqual(dependency.method_calls, [])

    def test_production_focus_cycles_follow_mapping_and_state_changes(self) -> None:
        traced_sql: list[str] = []

        def assert_cycle(declared: tuple[tk.Widget, ...]) -> tuple[tk.Widget, ...]:
            self.root.update()
            eligible = tuple(value for value in declared if self.root._focus_eligible(value))
            self.assertEqual(len(eligible), len(set(eligible)))
            for index, current in enumerate(eligible):
                self.root._move_scoped_focus(current, True)
                self.assertIs(self.root.focus_get(), eligible[(index + 1) % len(eligible)])
                self.root._move_scoped_focus(current, False)
                self.assertIs(self.root.focus_get(), eligible[(index - 1) % len(eligible)])
            return eligible

        self.root.tabs.select(self.root.dashboard_tab)
        self.root.current_dashboard_homepage = DashboardHomepageViewModelBuilder().build(None)
        self.root._update_hidden_gems_navigation()
        hidden = assert_cycle(self.root._dip_dashboard_focus_order)
        self.assertNotIn(self.root.hidden_gems_button, hidden)
        self.root.current_dashboard_homepage = DashboardHomepageViewModelBuilder().build(
            execution(52, hidden_record(52, candidates=(candidate(7),)))
        )
        self.root._update_hidden_gems_navigation()
        self.database.conn.set_trace_callback(traced_sql.append)
        changes_before = self.database.conn.total_changes
        shown = assert_cycle(self.root._dip_dashboard_focus_order)
        self.assertIn(self.root.hidden_gems_button, shown)

        self.root.tabs.select(self.root.review_tab)
        for tab in (
            self.root.observations_tab,
            self.root.queue_tab,
            self.root.decisions_tab,
        ):
            self.root.collection_review_tabs.select(tab)
            self.assertGreaterEqual(len(assert_cycle(self.root._dip_review_focus_order)), 2)
        self.database.conn.set_trace_callback(None)
        self.assertEqual(traced_sql, [])
        self.assertEqual(self.database.conn.total_changes, changes_before)
        self.root.dashboard_homepage_service.homepage.assert_not_called()
        self.import_mock.assert_not_called()
        self.refresh_mock.assert_not_called()
        for dependency in (
            self.dependencies.collection_health_controller,
            self.dependencies.collection_explorer_controller,
            self.dependencies.portfolio_overview_controller,
            self.dependencies.portfolio_controller,
        ):
            self.assertEqual(dependency.method_calls, [])
        self.assertEqual(
            self.root.hidden_gems_controller._presentation.method_calls,
            [],
        )

    def test_execution_bound_dashboard_rejects_later_mutable_score_attribution(self) -> None:
        homepage = DashboardHomepageViewModelBuilder().build(
            execution(41, health_record(41, score=47.8, collection_size=1))
        )
        self.assertEqual(homepage.section_for("latest_execution").run_id, 41)
        self.root.dashboard_homepage_service.homepage.return_value = homepage
        self.database.conn.execute(
            "INSERT INTO releases(release_id, artist, title) VALUES (1, 'Later', 'Mutable')"
        )
        self.database.conn.execute(
            "INSERT INTO scores(release_id, calculated_at, value_score, demand_score, liquidity_score, momentum_score, opportunity_score, sell_window, priority, explanation) VALUES (1, '2099-01-01T00:00:00+00:00', 99, 99, 99, 99, 99, 'Hot now', 'High-priority review', 'B-SENTINEL')"
        )
        self.database.conn.commit()
        self.assertTrue(self.root.refresh_dashboard())
        self.assertEqual(
            self.root.current_dashboard_homepage.section_for("latest_execution").run_id,
            41,
        )
        self.assertIn(
            "Execution ID: 41",
            self.root.dashboard_homepage_vars["latest_execution"].get(),
        )
        self.assertEqual(set(self.root.kpis), {"unique_releases", "owned_copies", "protected"})
        latest_text = "\n".join(value.get() for value in self.root.dashboard_homepage_vars.values())
        self.assertIn("47.8", latest_text)
        self.assertNotIn("99", latest_text)
        self.assertNotIn("B-SENTINEL", latest_text)

    def test_production_detail_sanitizes_warnings_and_styles_provenance(self) -> None:
        sentinels = (
            "TOKEN-secret", "provider body", "SELECT private", "/private/db",
            "/destination/path", '{"serialized":"row"}', "PERSONAL NOTE",
            "£999 supply=88", "exception text",
        )
        observation = replace(
            _workspace(1).hot_now[0],
            warnings=tuple(
                ObservationWarning(f"unknown_{index}", sentinel)
                for index, sentinel in enumerate(sentinels)
            ),
            source_marketplace_snapshot_id="snapshot-safe",
        )
        self.root.tabs.select(self.root.review_tab)
        self.root.collection_review_tabs.select(self.root.observations_tab)
        self.root.update()
        self.root._show_observation_detail(observation)
        rendered = self.root.observation_detail.get("1.0", "end-1c")
        for sentinel in sentinels:
            self.assertNotIn(sentinel, rendered)
        self.assertIn("Some supplied Marketplace evidence was incomplete.", rendered)
        self.assertIn("Technical provenance", rendered)
        self.assertEqual(
            self.root.observation_detail.tag_cget("provenance_heading", "lmargin1"),
            "14",
        )

    def test_production_disabled_reason_state_matrix(self) -> None:
        previous_reasons = {}

        def assert_reason(label, variable, expected):
            self.root.update()
            self.assertEqual(variable.get(), expected.value)
            self.assertTrue(label.winfo_ismapped())
            self.assertTrue(label.winfo_viewable())
            self.assertGreater(label.winfo_width(), 1)
            self.assertGreater(label.winfo_height(), 1)
            self.assertEqual(str(label.cget("takefocus")), "1")
            self.assertTrue(self.root._focus_eligible(label))
            previous = previous_reasons.get(label)
            if previous is not None:
                self.assertNotEqual(variable.get(), previous)
            previous_reasons[label] = variable.get()
            self.assertGreaterEqual(label.winfo_rooty(), self.root.review_tab.winfo_rooty())
            self.assertLessEqual(
                label.winfo_rooty() + label.winfo_height(),
                self.root.review_tab.winfo_rooty() + self.root.review_tab.winfo_height(),
            )

        def assert_disabled(*buttons):
            for button in buttons:
                self.assertIn("disabled", button.state())

        def assert_enabled(*buttons):
            for button in buttons:
                self.assertNotIn("disabled", button.state())

        observation_buttons = (
            self.root.add_observation_button,
            self.root.reopen_observation_button,
            self.root.open_queued_observation_button,
        )
        queue_buttons = (
            self.root.queue_save_button,
            self.root.queue_status_button,
            self.root.queue_resolve_button,
            self.root.queue_remove_button,
            self.root.queue_decision_button,
        )

        def assert_queue_layout(expected_mode):
            self.root.update()
            self.assertEqual(self.root._queue_action_layout, expected_mode)
            root_right = self.root.winfo_rootx() + self.root.winfo_width()
            root_bottom = self.root.winfo_rooty() + self.root.winfo_height()
            for button in queue_buttons:
                self.assertTrue(button.winfo_ismapped(), button.cget("text"))
                self.assertTrue(button.winfo_viewable(), button.cget("text"))
                self.assertGreaterEqual(
                    button.winfo_width(), button.winfo_reqwidth(),
                    button.cget("text"),
                )
                self.assertLessEqual(
                    button.winfo_rootx() + button.winfo_width(), root_right,
                    button.cget("text"),
                )
                self.assertLessEqual(
                    button.winfo_rooty() + button.winfo_height(), root_bottom,
                    button.cget("text"),
                )
            reason = self.root.queue_action_reason_label
            self.assertLessEqual(int(reason.cget("wraplength")), reason.winfo_width())
            self.assertGreaterEqual(reason.winfo_height(), reason.winfo_reqheight())
        self.root.tabs.select(self.root.review_tab)
        self.root.collection_review_tabs.select(self.root.observations_tab)
        self.root.update()
        self.root.collector_review_service = Mock()
        self.root._set_observation_action_state(None)
        assert_disabled(*observation_buttons)
        assert_reason(
            self.root.observation_action_reason_label,
            self.root.observation_action_reason_var,
            DisabledActionReason.NO_OBSERVATION,
        )

        observation = _workspace(1).hot_now[0]
        self.root._set_observation_action_state(observation)
        assert_enabled(self.root.add_observation_button)
        assert_disabled(
            self.root.reopen_observation_button,
            self.root.open_queued_observation_button,
        )
        assert_reason(
            self.root.observation_action_reason_label,
            self.root.observation_action_reason_var,
            DisabledActionReason.NOT_QUEUED,
        )

        queued_observation = replace(
            observation,
            queue_membership=QueueMembership(1, WeekendReviewStatus.TO_REVIEW),
        )
        self.root._set_observation_action_state(queued_observation)
        assert_enabled(self.root.open_queued_observation_button)
        assert_disabled(
            self.root.add_observation_button,
            self.root.reopen_observation_button,
        )
        assert_reason(
            self.root.observation_action_reason_label,
            self.root.observation_action_reason_var,
            DisabledActionReason.ALREADY_QUEUED,
        )

        resolved_observation = replace(
            observation,
            queue_membership=QueueMembership(1, WeekendReviewStatus.RESOLVED),
        )
        self.root._set_observation_action_state(resolved_observation)
        assert_enabled(
            self.root.reopen_observation_button,
            self.root.open_queued_observation_button,
        )
        assert_disabled(self.root.add_observation_button)
        assert_reason(
            self.root.observation_action_reason_label,
            self.root.observation_action_reason_var,
            DisabledActionReason.RESOLVED_OBSERVATION,
        )

        self.root.collector_review_service = None
        self.root._set_observation_action_state(resolved_observation)
        assert_disabled(*observation_buttons)
        assert_reason(
            self.root.observation_action_reason_label,
            self.root.observation_action_reason_var,
            DisabledActionReason.OBSERVATION_SERVICE_UNAVAILABLE,
        )

        self.root.collection_review_tabs.select(self.root.queue_tab)
        self.root.update()
        self.root.collector_review_service = Mock()
        self.root._load_queue_item(None)
        assert_disabled(*queue_buttons)
        assert_queue_layout("compact")
        self.assertEqual(self.root.queue_note.cget("state"), "disabled")
        assert_reason(
            self.root.queue_action_reason_label,
            self.root.queue_action_reason_var,
            DisabledActionReason.NO_QUEUE_ITEM,
        )
        now = datetime(2026, 8, 12, tzinfo=timezone.utc)
        active = WeekendReviewQueueItem(
            1, 1, now, WeekendReviewStatus.TO_REVIEW, "", now, None,
            WeekendObservationSource.HOT_NOW, now, "Stored signal", None, None,
        )
        self.root._load_queue_item(active)
        assert_enabled(*queue_buttons)
        service_calls = tuple(self.root.collector_review_service.method_calls)
        eligible = tuple(
            widget for widget in self.root._dip_review_focus_order
            if self.root._focus_eligible(widget)
        )
        for widget in eligible:
            self.root._move_scoped_focus(widget, True)
            self.root._move_scoped_focus(widget, False)
        self.assertEqual(
            tuple(self.root.collector_review_service.method_calls), service_calls
        )
        assert_reason(
            self.root.queue_action_reason_label,
            self.root.queue_action_reason_var,
            DisabledActionReason.QUEUE_ACTIONS_AVAILABLE,
        )
        self.root._queue_note_loading = False
        self.root.queue_note.insert("1.0", "changed")
        self.root._on_queue_note_edited()
        self.assertTrue(self.root._queue_note_dirty)
        assert_enabled(*queue_buttons)
        assert_reason(
            self.root.queue_action_reason_label,
            self.root.queue_action_reason_var,
            DisabledActionReason.UNSAVED_NOTE,
        )
        with patch(
            "dip.experience.desktop.app.messagebox.askyesnocancel",
            return_value=None,
        ):
            self.assertFalse(self.root._confirm_unsaved_queue_note())
        self.assertTrue(self.root._queue_note_dirty)
        self.assertEqual(
            self.root.queue_action_reason_var.get(),
            DisabledActionReason.UNSAVED_NOTE.value,
        )
        with patch(
            "dip.experience.desktop.app.messagebox.askyesnocancel",
            return_value=False,
        ):
            self.assertTrue(self.root._confirm_unsaved_queue_note())
        self.assertFalse(self.root._queue_note_dirty)
        resolved = replace(
            active,
            queue_item_id=2,
            release_id=2,
            status=WeekendReviewStatus.RESOLVED,
            resolved_at=now,
        )
        self.root._load_queue_item(resolved)
        self.assertIn("disabled", self.root.queue_status_button.state())
        assert_enabled(
            self.root.queue_save_button,
            self.root.queue_resolve_button,
            self.root.queue_remove_button,
            self.root.queue_decision_button,
        )
        assert_reason(
            self.root.queue_action_reason_label,
            self.root.queue_action_reason_var,
            DisabledActionReason.RESOLVED_START_REVIEW,
        )
        self.root.collector_review_service.list_queue.return_value = (
            active, resolved
        )
        self.root.queue_filter_var.set("All")
        self.root.refresh_weekend_review_queue()
        self.assertEqual(len(self.root.queue_tree.get_children()), 2)
        self.assertEqual(
            {
                self.root.queue_tree.item(item, "values")[2]
                for item in self.root.queue_tree.get_children()
            },
            {"To Review", "Resolved"},
        )
        self.root.geometry("1600x900")
        assert_queue_layout("expanded")
        self.root.geometry("800x560")
        assert_queue_layout("compact")
        for hostile in ("TOKEN", "provider", "SQL", "/private", "PERSONAL NOTE"):
            self.assertNotIn(hostile, self.root.observation_action_reason_var.get())
            self.assertNotIn(hostile, self.root.queue_action_reason_var.get())
        self.root.collector_review_service = None
        self.root.refresh_weekend_review_queue()
        self.assertEqual(
            self.root.queue_summary_var.get(),
            "Weekend Review Queue is unavailable.",
        )
        self.root._load_queue_item(None)
        assert_disabled(*queue_buttons)
        assert_queue_layout("compact")
        assert_reason(
            self.root.queue_action_reason_label,
            self.root.queue_action_reason_var,
            DisabledActionReason.QUEUE_SERVICE_UNAVAILABLE,
        )

    def test_real_button_return_space_and_bidirectional_focus(self) -> None:
        self.root.tabs.select(self.root.dashboard_tab)
        first = self.root.import_csv_button
        second = self.root.refresh_discogs_button
        self.root.update_idletasks()
        first.focus_force()
        first.event_generate("<Return>")
        second.focus_force()
        second.event_generate("<space>")
        self.root.update()
        self.import_mock.assert_called_once_with(self.root)
        self.refresh_mock.assert_called_once_with(self.root)
        self.assertEqual(self.root._move_scoped_focus(first, True), "break")
        self.assertIs(self.root.focus_get(), second)
        self.assertEqual(self.root._move_scoped_focus(second, False), "break")
        self.assertIs(self.root.focus_get(), first)

        self.root.tabs.select(self.root.review_tab)
        self.root.collection_review_tabs.select(self.root.queue_tab)
        now = datetime(2026, 8, 12, tzinfo=timezone.utc)
        active = WeekendReviewQueueItem(
            1, 1, now, WeekendReviewStatus.TO_REVIEW, "", now, None,
            WeekendObservationSource.HOT_NOW, now, "Stored signal", None, None,
        )
        self.root.collector_review_service = Mock()
        self.root._load_queue_item(active)
        activation = Mock()
        self.root.queue_decision_button.configure(command=activation)
        self.root.update()
        self.root.queue_decision_button.focus_force()
        self.root.queue_decision_button.event_generate("<Return>")
        self.root.update()
        activation.assert_called_once_with()
        activation.reset_mock()
        self.root.queue_decision_button.event_generate("<space>")
        self.root.update()
        activation.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
