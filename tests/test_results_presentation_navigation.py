from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import Mock, patch

from dip.experience.desktop.app import (
    App,
    _MARKETPLACE_REFRESH_BLOCKED,
    _MARKETPLACE_REFRESH_EXPLANATION,
    _STALE_MARKETPLACE_COPY,
)
from dip.experience.desktop.collection_explorer_renderer import (
    DesktopCollectionExplorerNavigationItem,
    DesktopCollectionExplorerRenderer,
)
from dip.experience.explorer import (
    CollectionExplorerConsistencyError,
    CollectionExplorerDestination,
    ENABLED_EXPLORER_DESTINATIONS,
    UNAVAILABLE_EXPLORER_DESTINATIONS,
    UNAVAILABLE_EXPLORER_EXPLANATION,
)

from tests.test_collection_explorer import available_homepage, build_explorer


class _Widget:
    instances = []

    def __init__(self, parent=None, **values):
        self.parent = parent
        self.values = dict(values)
        self.bindings = {}
        self.states = []
        self.packed = []
        self._current = -1
        self.text = values.get("text", "")
        self.insertions = []
        type(self).instances.append(self)

    def pack(self, **values): self.packed.append(values)
    def bind(self, sequence, callback, add=None): self.bindings[sequence] = callback
    def configure(self, **values): self.values.update(values); self.text = values.get("text", self.text)
    def state(self, values): self.states.append(values)
    def current(self, value=None):
        if value is not None: self._current = value
        return self._current
    def delete(self, *args): self.insertions.clear()
    def insert(self, index, value, tags=()): self.insertions.append((value, tags))
    def tag_configure(self, *args, **kwargs): pass
    def yview(self): return (0.0, 1.0)
    def yview_moveto(self, value): self.position = value
    def update_idletasks(self): self.idle_updated = True


class _Frame(_Widget): pass
class _Label(_Widget): pass
class _LabelFrame(_Widget): pass
class _Combobox(_Widget): pass
class _Button(_Widget): pass
class _Scrollbar(_Widget):
    def set(self, *args): pass
class _Text(_Widget): pass


class _Window:
    def __init__(self):
        self.bindings = {}
        self.protocols = {}
        self.exists = True

    def title(self, value): self.window_title = value
    def geometry(self, value): self.window_geometry = value
    def minsize(self, width, height): self.minimum = (width, height)
    def transient(self, parent): self.owner = parent
    def bind(self, sequence, callback, add=None): self.bindings[sequence] = callback
    def protocol(self, name, callback): self.protocols[name] = callback
    def winfo_exists(self): return self.exists
    def destroy(self): self.exists = False


class ResultsPresentationNavigationModelTest(unittest.TestCase):
    def test_authoritative_availability_order_and_fixed_copy(self):
        self.assertEqual(
            ENABLED_EXPLORER_DESTINATIONS,
            (
                CollectionExplorerDestination.OVERVIEW,
                CollectionExplorerDestination.COLLECTION_HEALTH,
                CollectionExplorerDestination.HIDDEN_GEMS,
                CollectionExplorerDestination.COLLECTION_TRENDS,
                CollectionExplorerDestination.PRICE_CHANGES,
                CollectionExplorerDestination.SUPPLY_CHANGES,
            ),
        )
        self.assertEqual(
            set(ENABLED_EXPLORER_DESTINATIONS) | set(UNAVAILABLE_EXPLORER_DESTINATIONS),
            set(CollectionExplorerDestination),
        )
        self.assertFalse(
            set(ENABLED_EXPLORER_DESTINATIONS) & set(UNAVAILABLE_EXPLORER_DESTINATIONS)
        )
        self.assertEqual(
            UNAVAILABLE_EXPLORER_DESTINATIONS,
            tuple(value for value in CollectionExplorerDestination if value not in ENABLED_EXPLORER_DESTINATIONS),
        )
        rendered = DesktopCollectionExplorerRenderer().render(
            build_explorer(available_homepage())
        )
        self.assertEqual(
            tuple(item.destination for item in rendered.navigation if item.available),
            ENABLED_EXPLORER_DESTINATIONS,
        )
        self.assertEqual(
            tuple(item.destination for item in rendered.navigation if not item.available),
            UNAVAILABLE_EXPLORER_DESTINATIONS,
        )
        for item in rendered.navigation:
            self.assertEqual(
                item.unavailable_explanation,
                "" if item.available else UNAVAILABLE_EXPLORER_EXPLANATION,
            )
        with self.assertRaises(FrozenInstanceError):
            rendered.navigation[0].available = False  # type: ignore[misc]
        with self.assertRaises(ValueError):
            replace(rendered.navigation[0], available=False)
        with self.assertRaises(ValueError):
            DesktopCollectionExplorerNavigationItem(
                CollectionExplorerDestination.WEEKEND_LISTINGS,
                "Weekend Listings",
                rendered.navigation[4].state,
                True,
                False,
                UNAVAILABLE_EXPLORER_EXPLANATION,
            )

    def test_complete_model_rejects_unavailable_selected_destination(self):
        explorer = build_explorer(available_homepage())
        with self.assertRaisesRegex(
            CollectionExplorerConsistencyError, "production-enabled"
        ):
            replace(
                explorer,
                selected_destination=CollectionExplorerDestination.WEEKEND_LISTINGS,
            )


class ResultsPresentationDesktopBoundaryTest(unittest.TestCase):
    def setUp(self):
        for value in (_Frame, _Label, _LabelFrame, _Combobox, _Button, _Scrollbar, _Text):
            value.instances = []

    def _populate(self, *, active=False, destination=CollectionExplorerDestination.PRICE_CHANGES):
        rendered = DesktopCollectionExplorerRenderer().render(
            replace(build_explorer(available_homepage()), selected_destination=destination)
        )
        app = App.__new__(App)
        app._collector_run_active = active
        app._marketplace_explorer_handles = {}
        app.tk = Mock()
        app.tk.call.return_value = "aqua"
        window = _Window()
        with (
            patch("dip.experience.desktop.app.ttk.Frame", _Frame),
            patch("dip.experience.desktop.app.ttk.Label", _Label),
            patch("dip.experience.desktop.app.ttk.LabelFrame", _LabelFrame),
            patch("dip.experience.desktop.app.ttk.Combobox", _Combobox),
            patch("dip.experience.desktop.app.ttk.Button", _Button),
            patch("dip.experience.desktop.app.ttk.Scrollbar", _Scrollbar),
            patch("dip.experience.desktop.app.tk.Text", _Text),
        ):
            app._populate_intelligence_explorer_window(window, rendered)
        return app, window, rendered

    def test_production_population_has_full_responsive_labels_and_fixed_copy(self):
        app, window, rendered = self._populate()
        navigation = window._dip_explorer_navigation
        expected_labels = tuple(
            item.label for item in rendered.navigation if item.available
        )
        self.assertEqual(navigation.values["values"], expected_labels)
        self.assertGreaterEqual(navigation.values["width"], max(map(len, expected_labels)))
        self.assertEqual(
            expected_labels,
            ("Overview", "Collection Health", "Hidden Gems", "Collection Trends", "Price Changes", "Supply Changes"),
        )
        unavailable_text = next(
            value.text for value in _Label.instances
            if "Weekend Listings" in value.text
        )
        self.assertEqual(unavailable_text.splitlines(), [
            "Weekend Listings", "Rare Appearances", "Marketplace Activity",
            "Listing Lifecycle", "Marketplace Momentum", "Marketplace Stability",
            "Marketplace Scarcity", "Marketplace Opportunity",
        ])
        self.assertEqual(
            sum(value.text == UNAVAILABLE_EXPLORER_EXPLANATION for value in _Label.instances),
            1,
        )
        self.assertEqual(
            sum(value.text == _MARKETPLACE_REFRESH_EXPLANATION for value in _Label.instances),
            1,
        )
        self.assertTrue(any("Command-R" in value.text and "Control-R" in value.text for value in _Label.instances))
        self.assertEqual(window.minimum, (800, 560))
        self.assertIn("<Command-r>", window.bindings)
        self.assertIn("<Control-r>", window.bindings)
        self.assertIn("<<ComboboxSelected>>", navigation.bindings)
        self.assertEqual(navigation.values["state"], "readonly")
        self.assertTrue(navigation.values["takefocus"])
        self.assertTrue(window._dip_explorer_text.values["takefocus"])
        actionable = {
            value.text: value
            for value in _Button.instances
            if value.text in {"Refresh Marketplace Changes", "Close"}
        }
        self.assertEqual(tuple(actionable), ("Refresh Marketplace Changes", "Close"))
        for button in actionable.values():
            self.assertTrue(button.values["takefocus"])
            self.assertIn("<Return>", button.bindings)
            self.assertIn("<space>", button.bindings)
        self.assertEqual(window._dip_selected_destination, CollectionExplorerDestination.PRICE_CHANGES)
        self.assertNotIn(UNAVAILABLE_EXPLORER_EXPLANATION, window._dip_explorer_text.insertions)

    def test_active_run_explanation_and_keyboard_refresh_are_fail_closed(self):
        app, window, rendered = self._populate(active=True)
        stale, button, _close = window._dip_marketplace_registration
        self.assertEqual(window._dip_active_run_explanation.text, _MARKETPLACE_REFRESH_BLOCKED)
        self.assertEqual(button.states, [["disabled"]])
        app._refresh_marketplace_explorer = Mock()
        result = window.bindings["<Command-r>"](object())
        self.assertEqual(result, "break")
        app._refresh_marketplace_explorer.assert_called_once()
        # The shared production boundary performs the active-run rejection before
        # any controller, query, provider, engine, or persistence collaborator.
        app._refresh_marketplace_explorer.reset_mock()
        App._refresh_marketplace_explorer(app, window, window._dip_explorer_navigation, rendered)
        app._refresh_marketplace_explorer.assert_not_called()
        self.assertEqual(stale.text, "")

    def test_retired_live_window_shortcuts_are_harmless(self):
        app, window, _rendered = self._populate()
        callback = window.bindings["<Control-r>"]
        app._marketplace_explorer_handles.pop(window)
        app._refresh_marketplace_explorer = Mock()
        self.assertEqual(callback(object()), "break")
        app._refresh_marketplace_explorer.assert_not_called()

    def test_stale_copy_is_separate_exact_and_multi_window_safe(self):
        app, first, _ = self._populate()
        _app, second, _ = self._populate(destination=CollectionExplorerDestination.SUPPLY_CHANGES)
        dead = _Window(); dead.exists = False
        dead_label, dead_button = _Label(), _Button()
        app._marketplace_explorer_handles[second] = second._dip_marketplace_registration[:2]
        app._marketplace_explorer_handles[dead] = (dead_label, dead_button)
        app._mark_marketplace_explorers_stale()
        self.assertEqual(first._dip_marketplace_registration[0].text, _STALE_MARKETPLACE_COPY)
        self.assertEqual(second._dip_marketplace_registration[0].text, _STALE_MARKETPLACE_COPY)
        self.assertEqual(first._dip_selected_destination, CollectionExplorerDestination.PRICE_CHANGES)
        self.assertEqual(second._dip_selected_destination, CollectionExplorerDestination.SUPPLY_CHANGES)
        self.assertNotIn(dead, app._marketplace_explorer_handles)
        self.assertNotIn(_STALE_MARKETPLACE_COPY, "".join(value for value, _ in first._dip_explorer_text.insertions))

    def test_view_position_is_clamped_and_only_restored_for_equivalent_content(self):
        text = _Text()
        window = _Window(); window._dip_explorer_text = text
        App._restore_marketplace_view_position(window, 4.0)
        self.assertEqual(text.position, 1.0)
        App._restore_marketplace_view_position(window, -2.0)
        self.assertEqual(text.position, 0.0)
        text.yview = lambda: (0.42, 0.75)
        self.assertEqual(App._marketplace_view_position(window), 0.42)

    def test_toolbar_uses_complete_marketplace_label_and_responsive_rows(self):
        source = Path("src/dip/experience/desktop/app.py").read_text(encoding="utf-8")
        self.assertIn('text="Marketplace"', source)
        self.assertNotIn('text="Marketplace Workspace",\n            command=self.open_marketplace_workspace', source)
        self.assertIn("primary_toolbar", source)
        self.assertIn("secondary_toolbar", source)
        self.assertIn("command=self.open_marketplace_workspace", source)


class ResultsPresentationRealTkBoundaryTest(unittest.TestCase):
    def _root(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        root.withdraw()
        self.addCleanup(lambda: root.destroy() if root.winfo_exists() else None)
        return root

    @staticmethod
    def _descendants(widget):
        values = []
        for child in widget.winfo_children():
            values.append(child)
            values.extend(ResultsPresentationRealTkBoundaryTest._descendants(child))
        return values

    def test_real_toolbar_keeps_full_labels_callbacks_and_two_rows_at_supported_widths(self):
        root = self._root()
        root.status_var = tk.StringVar(master=root, value="Ready")
        callbacks = (
            "import_csv", "start_refresh", "back_up_database", "export_report",
            "export_intelligence_report", "load_table", "open_portfolio_overview",
            "open_intelligence_change_analysis", "open_marketplace_workspace",
        )
        for name in callbacks:
            setattr(root, name, Mock())
        toolbar = App._build_main_toolbar(root)
        buttons = {
            child.cget("text"): child
            for child in self._descendants(toolbar)
            if isinstance(child, ttk.Button)
        }
        self.assertEqual(
            tuple(buttons),
            (
                "Import Collection CSV", "Refresh Discogs Data", "Back Up Database…",
                "Export Excel", "Export Intelligence Report", "Refresh View",
                "Portfolio", "Historical Intelligence", "Marketplace",
            ),
        )
        self.assertEqual(len(toolbar.winfo_children()), 2)
        root.deiconify()
        for width in (1200, 1050):
            root.geometry(f"{width}x220")
            root.update_idletasks()
            for button in buttons.values():
                self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth())
        expected = {
            "Import Collection CSV": "import_csv",
            "Refresh Discogs Data": "start_refresh",
            "Back Up Database…": "back_up_database",
            "Export Excel": "export_report",
            "Export Intelligence Report": "export_intelligence_report",
            "Refresh View": "load_table",
            "Portfolio": "open_portfolio_overview",
            "Historical Intelligence": "open_intelligence_change_analysis",
            "Marketplace": "open_marketplace_workspace",
        }
        for label, callback in expected.items():
            buttons[label].state(["!disabled"])
            buttons[label].invoke()
            getattr(root, callback).assert_called_once_with()

    def test_real_explorer_geometry_focus_and_keyboard_contract(self):
        root = self._root()
        app = App.__new__(App)
        app.tk = root.tk
        app._w = root._w
        app.children = root.children
        app._collector_run_active = False
        app._marketplace_explorer_handles = {}
        window = tk.Toplevel(root)
        window.withdraw()
        rendered = DesktopCollectionExplorerRenderer().render(
            replace(
                build_explorer(available_homepage()),
                selected_destination=CollectionExplorerDestination.PRICE_CHANGES,
            )
        )
        App._populate_intelligence_explorer_window(app, window, rendered)
        window.deiconify()
        navigation = window._dip_explorer_navigation
        descendants = self._descendants(window)
        buttons = {
            child.cget("text"): child
            for child in descendants
            if isinstance(child, ttk.Button)
        }
        for width in (1050, 800):
            window.geometry(f"{width}x720")
            window.update_idletasks()
            self.assertGreaterEqual(navigation.winfo_width(), navigation.winfo_reqwidth())
            for child in descendants:
                if isinstance(child, ttk.Label) and child.cget("text") in {
                    "Weekend Listings\nRare Appearances\nMarketplace Activity\nListing Lifecycle\nMarketplace Momentum\nMarketplace Stability\nMarketplace Scarcity\nMarketplace Opportunity",
                    UNAVAILABLE_EXPLORER_EXPLANATION,
                }:
                    self.assertGreaterEqual(child.winfo_width(), child.winfo_reqwidth())
        focus_chain = []
        current = navigation
        for _ in range(6):
            current = current.tk_focusNext()
            focus_chain.append(str(current))
        self.assertIn(str(window._dip_explorer_text), focus_chain)
        self.assertIn(str(buttons["Refresh Marketplace Changes"]), focus_chain)
        self.assertIn(str(buttons["Close"]), focus_chain)
        self.assertEqual(str(navigation.cget("state")), "readonly")
        self.assertEqual(tuple(navigation.cget("values")), tuple(
            item.label for item in rendered.navigation if item.available
        ))
        operations = {
            name: Mock()
            for name in (
                "history", "metadata", "provider", "engine", "persistence",
                "refresh", "rebuild", "register", "destroy", "replacement",
            )
        }
        app._refresh_marketplace_explorer = operations["refresh"]
        app._create_marketplace_replacement_toplevel = operations["replacement"]
        app.collection_explorer_controller = Mock()
        app.db = Mock()
        app.collector_run_service = Mock()
        original_sections = rendered.sections

        def press(keysym):
            navigation.focus_force()
            root.update()
            self.assertIs(root.focus_get(), navigation)
            navigation.event_generate(f"<KeyPress-{keysym}>")
            root.update()

        navigation.current(2)
        press("Left")
        self.assertEqual(navigation.current(), 1)
        self.assertIs(window._dip_selected_destination, CollectionExplorerDestination.COLLECTION_HEALTH)
        press("Up")
        self.assertEqual(navigation.current(), 0)
        self.assertIs(window._dip_selected_destination, CollectionExplorerDestination.OVERVIEW)
        content = window._dip_explorer_text
        content.configure(state="normal")
        content.insert("end", "\n" + "boundary viewport\n" * 200)
        content.configure(state="disabled")
        content.yview_moveto(0.5)
        root.update()
        first_boundary_content = content.get("1.0", "end")
        first_boundary_view = content.yview()
        press("Left")
        press("Up")
        self.assertEqual(navigation.current(), 0)
        self.assertEqual(content.get("1.0", "end"), first_boundary_content)
        self.assertEqual(content.yview(), first_boundary_view)
        press("Right")
        self.assertEqual(navigation.current(), 1)
        press("Down")
        self.assertEqual(navigation.current(), 2)
        navigation.current(5)
        navigation.focus_force()
        content.configure(state="normal")
        content.delete("1.0", "end")
        content.insert("1.0", "last boundary\n" * 200)
        content.configure(state="disabled")
        content.yview_moveto(0.5)
        root.update()
        last_boundary_content = content.get("1.0", "end")
        last_boundary_view = content.yview()
        press("Right")
        press("Down")
        self.assertEqual(navigation.current(), 5)
        self.assertEqual(content.get("1.0", "end"), last_boundary_content)
        self.assertEqual(content.yview(), last_boundary_view)
        navigation.current(4)
        press("Return")
        self.assertIs(window._dip_selected_destination, CollectionExplorerDestination.PRICE_CHANGES)
        navigation.current(5)
        press("space")
        self.assertIs(window._dip_selected_destination, CollectionExplorerDestination.SUPPLY_CHANGES)
        navigation.current(1)
        navigation.event_generate("<<ComboboxSelected>>")
        root.update()
        self.assertIs(window._dip_selected_destination, CollectionExplorerDestination.COLLECTION_HEALTH)
        navigation.set("Weekend Listings")
        press("Return")
        self.assertEqual(navigation.current(), -1)
        self.assertIs(window._dip_selected_destination, CollectionExplorerDestination.COLLECTION_HEALTH)
        self.assertIs(rendered.sections, original_sections)
        for operation in operations.values():
            operation.assert_not_called()
        self.assertEqual(app.collection_explorer_controller.mock_calls, [])
        self.assertEqual(app.db.mock_calls, [])
        self.assertEqual(app.collector_run_service.mock_calls, [])
        self.assertTrue(window.bind("<Command-r>"))
        self.assertTrue(window.bind("<Control-r>"))
        self.assertIs(navigation.tk_focusPrev(), buttons["Close"])

        navigation.current(2)
        app._marketplace_explorer_handles.pop(window)
        press("Right")
        self.assertEqual(navigation.current(), 2)
        operations["refresh"].assert_not_called()
        app._marketplace_explorer_handles[window] = window._dip_marketplace_registration[:2]
        buttons["Refresh Marketplace Changes"].focus_force()
        root.update()
        buttons["Refresh Marketplace Changes"].event_generate("<KeyPress-space>")
        root.update()
        operations["refresh"].assert_called_once()
        buttons["Close"].focus_force()
        root.update()
        buttons["Close"].event_generate("<KeyPress-Return>")
        root.update()
        self.assertFalse(window.winfo_exists())
        with self.assertRaises(tk.TclError):
            navigation.event_generate("<KeyPress-Right>")
        operations["refresh"].assert_called_once()


if __name__ == "__main__":
    unittest.main()
