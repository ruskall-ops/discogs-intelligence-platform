"""Agent-operated real-Tk coverage over production composition and synthetic SQLite."""

from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
import os
import json
import sqlite3
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from dip.composition import SETTINGS, build_desktop_application_dependencies
from dip.experience.desktop.app import App
from tests.test_portfolio_artist_inspection import manifest


class PortfolioArtistInspectionTkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            root=tk.Tk();root.withdraw();root.destroy()
        except tk.TclError as exc:
            if os.environ.get("DIP_REQUIRE_TK_TESTS")=="1": raise RuntimeError("Real Tk display is required") from exc
            raise unittest.SkipTest(f"Real Tk display unavailable: {exc}")

    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.path=Path(self.directory.name)/"synthetic.sqlite3"
        self.stack=ExitStack()
        self.addCleanup(self.stack.close)
        self.provider=self.stack.enter_context(patch("dip.composition.DiscogsClient",side_effect=AssertionError("provider forbidden")))
        self.network=self.stack.enter_context(patch("socket.socket.connect",side_effect=AssertionError("network forbidden")))
        self.stack.enter_context(patch("dip.composition.SETTINGS",replace(SETTINGS,database_path=self.path)))
        self.dependencies=build_desktop_application_dependencies()
        self.database=self.dependencies.database
        self.database.conn.executemany("INSERT INTO releases(release_id,artist,title,label,format,released) VALUES (?, ?, ?, 'Label','Vinyl','2001')",((10,"A","First"),(20,"A","Second"),(30,"B","Third"),(40,None,"Missing"),*((value,"B","Long title "*30) for value in range(100,141))))
        self.database.conn.executemany("INSERT INTO collection_ownership(release_id,quantity) VALUES (?, ?)",((10,3),(20,2),(30,1),(40,1),*((value,1) for value in range(100,141))))
        self.database.conn.commit()
        self.stack.enter_context(patch("dip.experience.desktop.app.build_desktop_application_dependencies",return_value=self.dependencies))
        self.errors=[]
        self.app=App()
        self.app.report_callback_exception=lambda *args:self.errors.append(args)
        self.app.geometry("1050x650+0+0")
        self.pump()
        self.before=manifest(self.database.conn)
        self.execution=self.stack.enter_context(patch.object(self.dependencies.current_collection_portfolio_execution,"execute",wraps=self.dependencies.current_collection_portfolio_execution.execute))
        self.info=self.stack.enter_context(patch("dip.experience.desktop.app.messagebox.showinfo"))
        self.error=self.stack.enter_context(patch("dip.experience.desktop.app.messagebox.showerror"))
        self.warning=self.stack.enter_context(patch("dip.experience.desktop.app.messagebox.showwarning"))
        self.app.open_portfolio_overview()
        self.portfolio=self.app._current_collection_portfolio_window
        self.portfolio.window.geometry("800x560")
        self.pump()

    def pump(self, condition=lambda:True):
        deadline=time.monotonic()+5
        while True:
            self.app.update()
            self.assertEqual(self.errors,[])
            if condition():return
            if time.monotonic()>=deadline:self.fail("Tk condition timed out")

    def inspect(self, label="A"):
        index=next(index for index, value in enumerate(self.portfolio._artist_categories) if value.label==label)
        self.portfolio.artist_category.current(index)
        self.portfolio.inspect_button.invoke()
        self.pump()
        return self.app._portfolio_artist_window

    def edit(self):
        inspection=self.inspect()
        inspection.tree.selection_set("10")
        self.pump()
        inspection.open_button.invoke()
        self.pump()
        self.assertIsNotNone(self.app._decision_editor)
        return inspection,self.app._decision_editor

    def tearDown(self):
        try:
            self.provider.assert_not_called();self.network.assert_not_called()
            self.assertEqual(self.errors,[])
        finally:
            try:
                if self.app.winfo_exists():self.app.destroy()
            except tk.TclError:
                pass
            self.database.close()
            self.directory.cleanup()

    def test_retained_source_labels_and_zero_writes(self):
        source=self.app._current_collection_portfolio_source
        self.database.conn.execute("UPDATE releases SET artist='Changed',title='Current title' WHERE release_id=10")
        self.database.conn.commit()
        before=manifest(self.database.conn)
        inspection=self.inspect()
        self.assertIs(inspection.inspection.source,source)
        self.assertEqual(inspection.inspection.category.display_name,"A")
        self.assertEqual(tuple((v.release_id,v.copies_at_calculation) for v in inspection.inspection.members),((10,3),(20,2)))
        self.assertEqual(inspection.tree.item("10","values"),("10","3","Changed","Current title"))
        self.assertEqual(self.execution.call_count,1)
        self.assertEqual(manifest(self.database.conn),before)
        self.assertIn("disabled",inspection.open_button.state())

    def test_measured_compact_windows_keyboard_controls_and_overflow(self):
        self.pump(lambda:(self.portfolio.window.winfo_width(),self.portfolio.window.winfo_height())==(800,560))
        self.assertTrue(self.portfolio.artist_category.winfo_ismapped())
        self.portfolio.refresh_button.focus_force()
        self.portfolio.refresh_button.event_generate("<Tab>")
        self.pump()
        self.assertIs(self.app.focus_get(),self.portfolio.artist_category)
        self.portfolio.artist_category.event_generate("<Tab>")
        self.pump()
        self.assertIs(self.app.focus_get(),self.portfolio.inspect_button)
        self.portfolio.artist_category.current(next(index for index, value in enumerate(self.portfolio._artist_categories) if value.label=="B"))
        self.portfolio.inspect_button.event_generate("<Return>")
        self.pump()
        inspection=self.app._portfolio_artist_window
        self.pump(lambda:(inspection.window.winfo_width(),inspection.window.winfo_height())==(800,560))
        self.assertEqual(inspection.heading.get("1.0", "end-1c"), "Artist category: B")
        inspection.heading.focus_force();self.pump()
        inspection.heading.event_generate("<Tab>");self.pump()
        self.assertIs(self.app.focus_get(),inspection.tree)
        inspection.tree.event_generate("<Shift-Tab>");self.pump()
        self.assertIs(self.app.focus_get(),inspection.heading)
        inspection.heading.event_generate("<Shift-Tab>");self.pump()
        self.assertIs(self.app.focus_get(),inspection.close_button)
        inspection.close_button.event_generate("<Tab>");self.pump()
        self.assertIs(self.app.focus_get(),inspection.heading)
        self.assertGreater(len(inspection.tree.get_children()),30)
        self.assertLess(inspection.tree.yview()[1],1)
        self.assertLess(inspection.tree.xview()[1],1)
        inspection.tree.yview_moveto(1)
        inspection.tree.xview_moveto(1)
        self.pump()
        self.assertGreater(inspection.tree.yview()[0],0)
        self.assertGreater(inspection.tree.xview()[0],0)
        for widget in (inspection.open_button,inspection.close_button):
            self.assertTrue(widget.winfo_ismapped())
            self.assertLessEqual(widget.winfo_y()+widget.winfo_height(),widget.master.winfo_height())
        inspection.tree.selection_set("30")
        inspection.tree.focus_force();self.pump()
        inspection.tree.event_generate("<Tab>");self.pump()
        self.assertIs(self.app.focus_get(),inspection.open_button)
        inspection.open_button.event_generate("<Shift-Tab>");self.pump()
        self.assertIs(self.app.focus_get(),inspection.tree)
        inspection.tree.event_generate("<Tab>");self.pump()
        inspection.open_button.event_generate("<space>");self.pump()
        self.assertIsNotNone(self.app._decision_editor)
        self.app._decision_editor._decision_controls[5].invoke();self.pump()
        inspection.close_button.focus_force();self.pump()
        inspection.close_button.event_generate("<Shift-Tab>");self.pump()
        self.assertIs(self.app.focus_get(),inspection.open_button)
        self.assertEqual(manifest(self.database.conn),self.before)
        self.assertEqual(self.execution.call_count,1)
        self.portfolio.navigation.current(1)
        self.portfolio.navigation.event_generate("<<ComboboxSelected>>")
        self.pump()
        self.assertFalse(self.portfolio.artist_controls.winfo_ismapped())

    def _assert_long_artist_layout(self, repetitions, expected_length):
        artist = ("Long Artist " * repetitions).strip()
        self.assertEqual(len(artist), expected_length)
        self.database.conn.execute(
            "UPDATE releases SET artist=? WHERE release_id IN (10,20)", (artist,),
        )
        self.database.conn.commit()
        self.app.refresh_current_collection_portfolio()
        before = manifest(self.database.conn)
        source = self.app._current_collection_portfolio_source
        inspection = self.inspect(label=artist)
        self.pump(lambda: (inspection.window.winfo_width(), inspection.window.winfo_height()) == (800, 560))
        self.assertEqual(inspection.window.minsize(), (800, 560))
        self.assertIs(inspection.inspection.source, source)
        self.assertEqual(inspection.inspection.category.display_name, artist)
        self.assertEqual(inspection.tree.get_children(), ("10", "20"))
        self.assertEqual(tuple(value.copies_at_calculation for value in inspection.inspection.members), (3, 2))
        bounds = {}
        for name, widget in (("members", inspection.tree), ("open", inspection.open_button), ("close", inspection.close_button)):
            self.assertTrue(widget.winfo_ismapped(), name)
            x = widget.winfo_rootx() - inspection.window.winfo_rootx()
            y = widget.winfo_rooty() - inspection.window.winfo_rooty()
            width, height = widget.winfo_width(), widget.winfo_height()
            bounds[name] = (x, y, width, height)
            self.assertGreaterEqual(x, 0, name)
            self.assertGreaterEqual(y, 0, name)
            self.assertLessEqual(x + width, 800, name)
            self.assertLessEqual(y + height, 560, name)
        self.assertGreater(inspection.tree.winfo_height(), 100)
        self.assertEqual(inspection.heading.get("1.0", "end-1c"), "Artist category: " + artist)
        self.assertEqual(str(inspection.heading.cget("state")), "disabled")
        inspection.heading.yview_moveto(0)
        self.pump()
        self.assertIsNotNone(inspection.heading.bbox("1.0"))
        self.assertLess(inspection.heading.yview()[1], 1)
        inspection.heading.focus_force()
        self.pump()
        inspection.heading.event_generate("<Next>")
        self.pump()
        self.assertGreater(inspection.heading.yview()[0], 0)
        inspection.heading.yview_moveto(1)
        self.pump()
        self.assertGreater(inspection.heading.yview()[0], 0)
        self.assertIsNotNone(inspection.heading.bbox("end-2c"))
        self.assertEqual(inspection.heading.get("1.0", "end-1c"), "Artist category: " + artist)
        print("LONG_ARTIST_LAYOUT " + json.dumps(dict(
            characters=expected_length, content_size=(inspection.window.winfo_width(), inspection.window.winfo_height()),
            bounds=bounds, heading_yview=inspection.heading.yview(),
        )), flush=True)
        inspection.tree.selection_set("20")
        inspection.tree.see("20")
        self.pump()
        self.assertNotIn("disabled", inspection.open_button.state())
        with patch.object(self.app, "_edit_collection_decision", wraps=self.app._edit_collection_decision) as opening:
            inspection.open_button.invoke()
            self.pump()
            opening.assert_called_once_with(20, parent=inspection.window, from_portfolio=True)
        editor = self.app._decision_editor
        self.assertIsNotNone(editor)
        self.assertEqual(editor._decision_controls[0].get(), "Review")
        editor.focus_force()
        self.pump()
        editor.event_generate("<Escape>")
        self.pump()
        self.assertIsNone(self.app._decision_editor)
        self.assertIsNone(self.app.grab_current())
        inspection.close_button.focus_force()
        self.pump()
        inspection.close_button.event_generate("<Return>")
        self.pump()
        self.assertFalse(inspection.alive())
        self.assertIsNone(self.app._portfolio_artist_window)
        self.assertEqual(manifest(self.database.conn), before)
        self.assertEqual(self.execution.call_count, 2)

    def test_1919_character_artist_remains_accessible_at_800x560(self):
        self._assert_long_artist_layout(160, 1919)

    def test_3839_character_artist_remains_accessible_at_800x560(self):
        self._assert_long_artist_layout(320, 3839)

    def test_cancel_escape_and_window_close_release_grab_without_writes(self):
        for action in ("cancel","escape","close"):
            with self.subTest(action=action):
                inspection,editor=self.edit()
                notes=editor._decision_controls[3]
                notes.insert("1.0","Unsaved synthetic note")
                if action=="cancel":editor._decision_controls[5].invoke()
                elif action=="escape":
                    editor.focus_force();self.pump();editor.event_generate("<Escape>")
                else:editor.tk.eval(editor.protocol("WM_DELETE_WINDOW"))
                self.pump()
                self.assertIsNone(self.app._decision_editor)
                self.assertIsNone(self.app.grab_current())
                self.assertEqual(manifest(self.database.conn),self.before)
                self.assertEqual(self.execution.call_count,1)

    def test_explicit_save_changes_one_decision_without_execution_or_freshness_change(self):
        inspection,editor=self.edit()
        controls=editor._decision_controls
        controls[0].set("Keep");controls[1].set("Would miss it");controls[2].set(True)
        controls[3].insert("1.0","Synthetic decision note")
        controls[4].invoke();self.pump()
        self.assertIsNone(self.app._decision_editor)
        self.assertIsNone(self.app.grab_current())
        before=dict(self.before[1]);after=dict(manifest(self.database.conn)[1])
        self.assertEqual({name for name in before if before[name]!=after[name]},{"decisions"})
        row=self.database.conn.execute("SELECT release_id,decision,personal_notes,protected FROM decisions").fetchone()
        self.assertEqual(tuple(row),(10,"Keep","Synthetic decision note",1))
        self.assertEqual(self.portfolio.freshness.get(),"Current")
        self.assertEqual(self.execution.call_count,1)
        self.assertTrue(inspection.alive())

    def test_failed_save_retains_draft_and_parent_guards(self):
        inspection,editor=self.edit()
        editor._decision_controls[3].insert("1.0","Keep this draft")
        with patch.object(self.dependencies.collection_decision,"save",side_effect=RuntimeError("secret")):
            editor._decision_controls[4].invoke();self.pump()
        self.assertIs(self.app._decision_editor,editor)
        self.assertIn("Keep this draft",editor._decision_controls[3].get("1.0","end"))
        self.assertIs(self.app.grab_current(),editor)
        self.app.refresh_current_collection_portfolio()
        inspection.close();self.portfolio.close();self.app.on_close()
        self.pump()
        self.assertTrue(inspection.alive());self.assertTrue(self.portfolio.alive())
        self.assertEqual(self.execution.call_count,1)
        self.assertEqual(manifest(self.database.conn),self.before)
        self.assertNotIn("secret",str(self.error.call_args))

    def test_filter_hidden_exact_id_editor_and_legacy_entry_points(self):
        self.database.conn.execute("INSERT INTO releases(release_id,artist,title) VALUES (5002,'A','Exact target')")
        self.database.conn.execute("INSERT INTO collection_ownership(release_id,quantity) VALUES (5002,1)")
        self.database.conn.commit()
        self.app.refresh_current_collection_portfolio()
        self.app.search_var.set("No matching title")
        self.app.decision_filter_var.set("Keep")
        self.app.load_table()
        self.assertFalse(self.app.tree.exists("5002"))
        inspection=self.inspect()
        inspection.tree.selection_set("5002");self.pump()
        with patch.object(self.database,"review_rows",side_effect=AssertionError("No capped query allowed")):
            inspection.open_button.invoke();self.pump()
        self.assertIn("Exact target",self.app._decision_editor.title())
        self.assertEqual(self.app.search_var.get(),"No matching title")
        self.assertEqual(self.app.decision_filter_var.get(),"Keep")
        self.app._decision_editor._decision_controls[5].invoke();self.pump()
        self.app.open_collection_decision(5002);self.pump()
        self.assertIn("Exact target",self.app._decision_editor.title())
        self.app._decision_editor._decision_controls[5].invoke();self.pump()
        self.app.search_var.set("");self.app.decision_filter_var.set("All");self.app.load_table()
        self.app.tree.selection_set("5002")
        self.app.edit_selected();self.pump()
        self.assertIn("Exact target",self.app._decision_editor.title())
        self.app._decision_editor._decision_controls[5].invoke()
        self.assertIsNone(self.app.grab_current())

    def test_save_does_not_clear_stale_state_and_run_guard_keeps_draft(self):
        inspection,editor=self.edit()
        self.app._mark_current_collection_portfolio_outdated()
        self.app._collector_run_active=True
        editor._decision_controls[3].insert("1.0","Retained draft")
        editor._decision_controls[4].invoke();self.pump()
        self.assertIs(self.app._decision_editor,editor)
        self.assertEqual(manifest(self.database.conn),self.before)
        self.app._collector_run_active=False
        editor._decision_controls[4].invoke();self.pump()
        self.assertIn("Out of date",self.portfolio.freshness.get())
        self.assertIn("Out of date",inspection.freshness.get())
        self.assertEqual(self.execution.call_count,1)

    def test_display_failure_does_not_close_retained_inspection_or_rebind_source(self):
        inspection=self.inspect()
        source=self.app._current_collection_portfolio_source
        show=self.portfolio.show
        calls=[]
        def fail_first(*args,**kwargs):
            calls.append(kwargs)
            if len(calls)==1:raise RuntimeError("display unavailable")
            return show(*args,**kwargs)
        with patch.object(self.portfolio,"show",side_effect=fail_first):
            self.app.refresh_current_collection_portfolio()
        self.assertTrue(inspection.alive())
        self.assertIs(self.app._current_collection_portfolio_source,source)
        self.assertEqual(self.portfolio.freshness.get(),"Current")
        self.assertEqual(len(calls),2)

    def test_successful_refresh_closes_inspection_failed_refresh_preserves_it(self):
        inspection=self.inspect()
        source=self.app._current_collection_portfolio_source
        workspace=self.portfolio._workspace
        with patch.object(self.dependencies.current_collection_portfolio_execution,"execute",side_effect=RuntimeError("secret")):
            self.app.refresh_current_collection_portfolio()
        self.assertTrue(inspection.alive())
        self.assertIs(self.app._current_collection_portfolio_source,source)
        self.assertIs(self.portfolio._workspace,workspace)
        self.assertEqual(self.portfolio.freshness.get(),"Current")
        self.app.refresh_current_collection_portfolio();self.pump()
        self.assertFalse(inspection.alive())
        self.assertIsNone(self.app._portfolio_artist_window)
        self.assertIsNot(self.app._current_collection_portfolio_source,source)
        self.assertEqual(self.execution.call_count,2)

    def test_active_run_blocks_new_actions_retains_readable_inspection(self):
        inspection=self.inspect()
        inspection.tree.selection_set("10");self.pump()
        self.app._collector_run_active=True
        self.app._update_current_collection_portfolio_run_state();self.pump()
        self.assertIn("disabled",self.portfolio.inspect_button.state())
        self.assertIn("disabled",inspection.open_button.state())
        self.app.inspect_portfolio_artist(inspection.inspection.category.category_id)
        self.app._open_artist_collection_decision(10)
        self.app.refresh_current_collection_portfolio()
        self.assertIsNone(self.app._decision_editor)
        self.assertIs(self.app._portfolio_artist_window,inspection)
        self.assertEqual(self.execution.call_count,1)
        self.app._collector_run_active=False
        self.app._update_current_collection_portfolio_run_state();self.pump()
        self.assertNotIn("disabled",inspection.open_button.state())

    def test_missing_record_retained_and_editor_rechecks_identity(self):
        self.database.conn.execute("DELETE FROM releases WHERE release_id=20")
        self.database.conn.commit()
        inspection=self.inspect()
        self.assertEqual(inspection.tree.get_children(),("10","20"))
        self.assertEqual(inspection.inspection.category.owned_copy_count,5)
        inspection.tree.selection_set("20");self.pump()
        self.assertIn("disabled",inspection.open_button.state())
        self.database.conn.execute("DELETE FROM releases WHERE release_id=10")
        self.database.conn.commit()
        inspection.tree.selection_set("10");self.pump()
        inspection.open_button.invoke();self.pump()
        self.assertIsNone(self.app._decision_editor)
        self.warning.assert_called_once()

    def test_failed_labels_keep_all_ids_and_disable_editing(self):
        with patch.object(self.dependencies.portfolio_artist_inspection._metadata,"metadata_for_release_ids",side_effect=RuntimeError("secret")):
            inspection=self.inspect()
        self.assertEqual(inspection.tree.get_children(),("10","20"))
        inspection.tree.selection_set("10");self.pump()
        self.assertIn("disabled",inspection.open_button.state())
        self.assertNotIn("secret",inspection.status.get())
        self.assertEqual(manifest(self.database.conn),self.before)

    def test_inspection_setup_error_leaves_no_partial_window_or_callback_exception(self):
        before=set(self.portfolio.window.winfo_children())
        with patch("dip.experience.desktop.portfolio_artist_inspection_window.ttk.Label",side_effect=RuntimeError("construction failed")):
            self.portfolio.inspect_button.invoke()
        self.pump()
        self.assertEqual(set(self.portfolio.window.winfo_children()),before)
        self.assertIsNone(self.app._portfolio_artist_window)
        self.assertEqual(manifest(self.database.conn),self.before)
        self.error.assert_called_once()

    def test_editor_grab_failure_cleans_up_and_normal_cancel_preserves_legacy_value(self):
        inspection=self.inspect()
        before=set(inspection.window.winfo_children())
        with patch("tkinter.Toplevel.grab_set",side_effect=tk.TclError("grab unavailable")):
            self.app._open_artist_collection_decision(10)
        self.pump()
        self.assertIsNone(self.app._decision_editor)
        self.assertIsNone(self.app.grab_current())
        self.assertEqual(set(inspection.window.winfo_children()),before)
        self.database.conn.execute("INSERT INTO decisions(release_id,decision) VALUES (10,'Retained legacy')")
        self.database.conn.commit()
        baseline=manifest(self.database.conn)
        self.app._open_artist_collection_decision(10);self.pump()
        self.assertEqual(self.app._decision_editor._decision_controls[0].get(),"Retained legacy")
        self.app._decision_editor._decision_controls[5].invoke();self.pump()
        self.assertEqual(manifest(self.database.conn),baseline)

    def test_editor_setup_error_does_not_leak_window_or_grab(self):
        inspection=self.inspect()
        before=set(inspection.window.winfo_children())
        with patch("dip.experience.desktop.app.ttk.Label",side_effect=RuntimeError("setup failed")):
            self.app._open_artist_collection_decision(10)
        self.pump()
        self.assertEqual(set(inspection.window.winfo_children()),before)
        self.assertIsNone(self.app._decision_editor)
        self.assertIsNone(self.app.grab_current())
        self.assertEqual(manifest(self.database.conn),self.before)

    def test_csv_commit_marks_retained_inspection_stale_without_execution(self):
        inspection=self.inspect()
        source=inspection.inspection.source
        csv=Path(self.directory.name)/"additional.csv"
        csv.write_text("release_id,Artist,Title,Label,Format,Released\n5002,New Artist,New title,New Label,Vinyl,2002\n")
        with patch("dip.experience.desktop.app.filedialog.askopenfilename",return_value=str(csv)):
            self.app.import_csv()
        self.pump()
        self.assertIs(inspection.inspection.source,source)
        self.assertIn("Out of date",inspection.freshness.get())
        self.assertIn("Out of date",self.portfolio.freshness.get())
        self.assertEqual(inspection.tree.get_children(),("10","20"))
        self.assertEqual(self.execution.call_count,1)
        self.assertIsNotNone(self.dependencies.collection_decision.load(5002))
        self.assertIsNone(self.database.conn.execute("SELECT release_id FROM decisions WHERE release_id=10").fetchone())

    def test_failed_and_cancelled_import_preserve_inspection_freshness(self):
        inspection=self.inspect()
        with patch("dip.experience.desktop.app.filedialog.askopenfilename",return_value=""):
            self.app.import_csv()
        with patch("dip.experience.desktop.app.filedialog.askopenfilename",return_value="synthetic.csv"),patch.object(self.app.import_service,"import_collection",side_effect=RuntimeError("failure")):
            self.app.import_csv()
        self.assertEqual(inspection.freshness.get(),"Current")
        self.assertEqual(self.execution.call_count,1)
        self.assertEqual(manifest(self.database.conn),self.before)

    def test_normal_close_persists_only_session_and_read_only_reopen(self):
        inspection=self.inspect()
        inspection.close();self.portfolio.close();self.pump()
        self.app.on_close()
        with self.assertRaises(tk.TclError):
            self.app.winfo_exists()
        with sqlite3.connect(self.path.as_uri()+"?mode=ro",uri=True) as connection:
            after=manifest(connection)
            self.assertEqual(after[0],self.before[0])
            before=dict(self.before[1]);values=dict(after[1])
            self.assertEqual({name for name in before if before[name]!=values[name]},{"desktop_session"})
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0],"ok")
            self.assertEqual(connection.execute("PRAGMA quick_check").fetchone()[0],"ok")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(),[])
            self.assertEqual([v[0] for v in connection.execute("SELECT version FROM schema_migrations ORDER BY version")],list(range(1,8)))
        self.assertEqual(tuple(Path(self.directory.name).iterdir()),(self.path,))
