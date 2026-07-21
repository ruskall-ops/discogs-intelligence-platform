
from __future__ import annotations
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from dip.collection.importers import CollectionImportError
from dip.collection.services import ImportService
from dip.composition import build_desktop_application_dependencies
from dip.config import SETTINGS
from dip.data_sources.discogs import DiscogsClient
from dip.experience.reporting import ReportingService, render_markdown
from dip.experience.dashboard import (
    DashboardHomepageViewModel,
)
from dip.experience.desktop.homepage_renderer import (
    DesktopDashboardHomepageRenderer,
)
from dip.exports import export_excel
from dip.intelligence.modules.opportunity_scoring import calculate

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        dependencies = build_desktop_application_dependencies()
        self.title(SETTINGS.application_name)
        self.geometry(

    f"{SETTINGS.window_width}x{SETTINGS.window_height}"

)
        self.minsize(1050, 650)
        self.db = dependencies.database
        self.import_service = ImportService(self.db)
        self.dashboard_homepage_service = dependencies.dashboard_homepage
        self.collection_health_controller = dependencies.collection_health_controller
        self.collection_explorer_controller = dependencies.collection_explorer_controller
        self.hidden_gems_controller = dependencies.hidden_gems_controller
        self.desktop_homepage_renderer = DesktopDashboardHomepageRenderer()
        self.current_dashboard_homepage = DashboardHomepageViewModel.loading()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.status_var = tk.StringVar(value="Ready")
        self.search_var = tk.StringVar()
        self.priority_var = tk.StringVar(value="All")
        self.decision_filter_var = tk.StringVar(value="All")

        self.build_ui()
        self.refresh_dashboard()
        self.load_table()

    def build_ui(self):
        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text="Import Collection CSV", command=self.import_csv).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Refresh Discogs Data", command=self.start_refresh).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Export Excel", command=self.export_report).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Export Intelligence Report", command=self.export_intelligence_report).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Refresh View", command=self.load_table).pack(side="left", padx=3)

        self.progress = ttk.Progressbar(toolbar, length=260, mode="determinate")
        self.progress.pack(side="right", padx=5)
        ttk.Label(toolbar, textvariable=self.status_var).pack(side="right", padx=8)

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)

        self.dashboard_tab = ttk.Frame(self.tabs, padding=18)
        self.review_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.dashboard_tab, text="Dashboard")
        self.tabs.add(self.review_tab, text="Collection Review")

        self.kpis = {}

        labels = [
            ("unique_releases", "Unique releases"),
            ("owned_copies", "Owned copies"),
            ("high_priority", "High-priority reviews"),
            ("worth_reviewing", "Worth reviewing"),
            ("hot_now", "Hot now"),
            ("protected", "Protected / Keep"),
        ]

        for index, (key, label) in enumerate(labels):
            box = ttk.LabelFrame(
                self.dashboard_tab,
                text=label,
                padding=15,
            )
            box.grid(
                row=0,
                column=index,
                padx=8,
                pady=8,
                sticky="nsew",
            )

            value = ttk.Label(
                box,
                text="0",
                font=("Helvetica", 24, "bold"),
            )
            value.pack()

            self.kpis[key] = value
            self.dashboard_tab.columnconfigure(index, weight=1)

        info = ttk.LabelFrame(self.dashboard_tab, text="Platform status", padding=16)
        info.grid(row=1, column=0, columnspan=6, padx=8, pady=20, sticky="ew")
        ttk.Label(info, text=(
            "SQLite is now the source of truth. Collection details, market snapshots, "
            "scores, decisions and notes persist between runs. Excel is generated only "
            "when you want an export."
        ), wraplength=1100, justify="left").pack(anchor="w")

        self.dashboard_homepage_vars = {}
        homepage_sections = (
            ("collection_overview", "Collection overview", 2, 0, 3),
            ("collection_health", "Collection Health", 2, 3, 3),
            ("hidden_gems", "Hidden Gems", 3, 0, 3),
            ("what_changed", "What Changed", 3, 3, 3),
            ("latest_execution", "Latest execution", 4, 0, 6),
        )
        for section_id, title, row, column, columnspan in homepage_sections:
            card = ttk.LabelFrame(self.dashboard_tab, text=title, padding=14)
            card.grid(
                row=row,
                column=column,
                columnspan=columnspan,
                padx=8,
                pady=8,
                sticky="nsew",
            )
            body = tk.StringVar(value="Intelligence is loading…")
            ttk.Label(
                card,
                textvariable=body,
                wraplength=350,
                justify="left",
            ).pack(anchor="nw", fill="both", expand=True)
            if section_id == "collection_health":
                ttk.Button(
                    card,
                    text="Open Collection Health",
                    command=self.open_collection_health,
                ).pack(anchor="w", pady=(10, 0))
            elif section_id == "hidden_gems":
                self.hidden_gems_button = ttk.Button(
                    card,
                    text="Open Hidden Gems",
                    command=self.open_hidden_gems,
                )
            self.dashboard_homepage_vars[section_id] = body
        self.dashboard_tab.rowconfigure(2, weight=1)
        self.dashboard_tab.rowconfigure(3, weight=1)
        self.collection_explorer_button = ttk.Button(
            self.dashboard_tab,
            text="Open Collection Explorer",
            command=self.open_intelligence_explorer,
        )
        self.collection_explorer_button.grid(
            row=5,
            column=0,
            columnspan=6,
            padx=8,
            pady=(10, 4),
        )

        filters = ttk.Frame(self.review_tab)
        filters.pack(fill="x", pady=(0,8))
        ttk.Label(filters, text="Search").pack(side="left")
        search = ttk.Entry(filters, textvariable=self.search_var, width=30)
        search.pack(side="left", padx=5)
        search.bind("<Return>", lambda e: self.load_table())

        ttk.Label(filters, text="Priority").pack(side="left", padx=(12,0))
        ttk.Combobox(filters, textvariable=self.priority_var, state="readonly", width=22,
                     values=["All","High-priority review","Worth reviewing","Possible candidate","Low priority","Not scored"]).pack(side="left", padx=5)

        ttk.Label(filters, text="Decision").pack(side="left", padx=(12,0))
        ttk.Combobox(filters, textvariable=self.decision_filter_var, state="readonly", width=14,
                     values=["All","Review","Keep","List for sale","Maybe","Ignore"]).pack(side="left", padx=5)
        ttk.Button(filters, text="Apply", command=self.load_table).pack(side="left", padx=5)

        cols = ("artist","title","price","wants","sale","opportunity","window","priority","decision")
        self.tree = ttk.Treeview(self.review_tab, columns=cols, show="headings", selectmode="browse")
        headings = {
            "artist":"Artist","title":"Title","price":"Lowest £","wants":"Wants",
            "sale":"For Sale","opportunity":"Opportunity","window":"Sell Window",
            "priority":"Priority","decision":"Decision"
        }
        widths = {"artist":210,"title":310,"price":85,"wants":80,"sale":80,
                  "opportunity":95,"window":150,"priority":185,"decision":110}
        for c in cols:
            self.tree.heading(c, text=headings[c])
            self.tree.column(c, width=widths[c], anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", self.edit_selected)

        scroll = ttk.Scrollbar(self.review_tab, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)

    def import_csv(self):
        path = filedialog.askopenfilename(
            title="Select Discogs collection export",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not path:
            return

        try:
            result = self.import_service.import_collection(Path(path))

            self.status_var.set(
                f"Imported {result.imported_records:,} collection rows "
                f"({result.invalid_release_ids:,} invalid rows skipped)"
            )

            self.refresh_dashboard()
            self.load_table()

            messagebox.showinfo(
                "Import complete",
                (
                    f"Imported or updated {result.imported_records:,} records.\n\n"
                    f"CSV rows: {result.total_rows:,}\n"
                    f"Valid release IDs: {result.valid_release_ids:,}\n"
                    f"Invalid release IDs: {result.invalid_release_ids:,}"
                ),
            )

        except CollectionImportError as exc:
            messagebox.showerror(
                "Import failed",
                str(exc),
            )

        except Exception as exc:
            messagebox.showerror(
                "Import failed",
                f"An unexpected error occurred:\n\n{exc}",
            )

    def start_refresh(self):
        if not self.db.release_ids():
            messagebox.showwarning("No collection", "Import your Discogs collection CSV first.")
            return
        token = simpledialog.askstring(
            "Discogs token",
            "Paste your Discogs personal access token.\nIt is used for this refresh only and is not saved.",
            show="*"
        )
        if not token:
            return
        threading.Thread(target=self.refresh_market_data, args=(token,), daemon=True).start()

    def refresh_market_data(self, token):
        ids = self.db.release_ids()
        attempted = 0
        succeeded = 0
        failed = 0

        run_id = self.db.start_analysis_run(
            run_type="market_refresh",
            source="discogs",
            application_version=SETTINGS.application_version,
        )

        try:
            client = DiscogsClient(token)
            captured_at = datetime.now().isoformat(timespec="seconds")

            self.after(
                0,
                lambda: self.progress.configure(maximum=len(ids)),
            )

            for pos, release_id in enumerate(ids, start=1):
                attempted += 1

                try:
                    data = client.get_release(release_id)

                    if not data:
                        failed += 1
                    else:
                        previous = self.db.previous_snapshot(
                            release_id,
                            captured_at,
                        )

                        self.db.add_snapshot(
                            run_id,
                            release_id,
                            captured_at,
                            data,
                        )

                        score = calculate(data, previous)

                        self.db.upsert_score(
                            release_id,
                            captured_at,
                            score,
                        )

                        succeeded += 1

                except Exception:
                    failed += 1

                self.after(
                    0,
                    self.update_refresh_progress,
                    pos,
                    len(ids),
                    succeeded,
                    failed,
                )

                time.sleep(
    SETTINGS.discogs_request_delay_seconds
)

            self.db.complete_analysis_run(
                run_id=run_id,
                releases_attempted=attempted,
                releases_succeeded=succeeded,
                releases_failed=failed,
            )

            self.after(
                0,
                self.finish_refresh,
                succeeded,
                failed,
            )

        except Exception as exc:
            self.db.fail_analysis_run(
                run_id=run_id,
                error_message=repr(exc),
                releases_attempted=attempted,
                releases_succeeded=succeeded,
                releases_failed=failed,
            )

            self.after(
                0,
                self.show_refresh_error,
                repr(exc),
            )
    def update_refresh_progress(
        self,
        position,
        total,
        succeeded,
        failed,
    ):
        self.progress["value"] = position
        self.status_var.set(
            f"Refreshing {position:,}/{total:,} "
            f"— successful {succeeded:,}, errors {failed:,}"
        )

    def finish_refresh(self, succeeded, failed):
        self.status_var.set(
            f"Refresh complete — {succeeded:,} successful, "
            f"{failed:,} errors"
        )
        self.refresh_dashboard()
        self.load_table()
        messagebox.showinfo(
            "Refresh complete",
            self.status_var.get(),
        )

    def show_refresh_error(self, error_message):
        self.status_var.set("Refresh failed")
        messagebox.showerror(
            "Refresh failed",
            f"An unexpected error occurred:\n\n{error_message}",
        )

    def refresh_dashboard(self):
        row = self.db.dashboard()
        for key, widget in self.kpis.items():
            widget.configure(text=f"{int(row[key] or 0):,}")
        self.refresh_intelligence_dashboard()

    def refresh_intelligence_dashboard(self):
        try:
            homepage = self.dashboard_homepage_service.homepage()
            self.current_dashboard_homepage = homepage
            sections = self.desktop_homepage_renderer.render(homepage)
            rendered = {
                section.section_id.value: section.body
                for section in sections
            }
        except Exception as exc:
            self.current_dashboard_homepage = DashboardHomepageViewModel.loading()
            rendered = {
                section_id: (
                    "Dashboard information is unavailable.\n"
                    f"{type(exc).__name__}: {exc}"
                )
                for section_id in self.dashboard_homepage_vars
            }

        for section_id, variable in self.dashboard_homepage_vars.items():
            variable.set(rendered.get(section_id, "Dashboard information is unavailable."))
        self._update_collection_explorer_navigation()
        self._update_hidden_gems_navigation()

    def open_collection_health(self):
        try:
            rendered = self.collection_health_controller.open(
                self.current_dashboard_homepage
            )
        except Exception as exc:
            messagebox.showerror(
                "Collection Health unavailable",
                f"Collection Health could not be displayed:\n\n{exc}",
            )
            return

        window = tk.Toplevel(self)
        window.title(rendered.title)
        window.geometry("780x680")
        window.minsize(620, 500)
        window.transient(self)

        header = ttk.Frame(window, padding=(18, 18, 18, 8))
        header.pack(fill="x")
        ttk.Label(
            header,
            text=rendered.headline,
            font=("Helvetica", 20, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            header,
            text=rendered.summary,
            wraplength=720,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        content = ttk.Frame(window, padding=(18, 8, 18, 12))
        content.pack(fill="both", expand=True)
        text = tk.Text(content, wrap="word", padx=10, pady=10)
        scrollbar = ttk.Scrollbar(
            content,
            orient="vertical",
            command=text.yview,
        )
        text.configure(yscrollcommand=scrollbar.set)
        for section in rendered.sections:
            text.insert("end", f"{section.title}\n", "section_heading")
            text.insert("end", f"{section.body}\n\n")
        text.tag_configure(
            "section_heading",
            font=("Helvetica", 12, "bold"),
        )
        text.configure(state="disabled")
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Button(window, text="Close", command=window.destroy).pack(
            pady=(0, 12)
        )

    def _update_hidden_gems_navigation(self):
        if self.hidden_gems_controller.can_open(self.current_dashboard_homepage):
            self.hidden_gems_button.pack(anchor="w", pady=(10, 0))
        else:
            self.hidden_gems_button.pack_forget()

    def _update_collection_explorer_navigation(self):
        if self.collection_explorer_controller.can_open(
            self.current_dashboard_homepage
        ):
            self.collection_explorer_button.state(["!disabled"])
        else:
            self.collection_explorer_button.state(["disabled"])

    def open_hidden_gems(self):
        try:
            rendered = self.hidden_gems_controller.open(
                self.current_dashboard_homepage
            )
        except Exception as exc:
            messagebox.showerror(
                "Hidden Gems unavailable",
                f"Hidden Gems could not be displayed:\n\n{exc}",
            )
            return

        window = tk.Toplevel(self)
        window.title(rendered.title)
        window.geometry("820x720")
        window.minsize(640, 520)
        window.transient(self)

        header = ttk.Frame(window, padding=(18, 18, 18, 8))
        header.pack(fill="x")
        ttk.Label(
            header,
            text=rendered.headline,
            font=("Helvetica", 20, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            header,
            text=rendered.summary,
            wraplength=760,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        content = ttk.Frame(window, padding=(18, 8, 18, 12))
        content.pack(fill="both", expand=True)
        text = tk.Text(content, wrap="word", padx=10, pady=10)
        scrollbar = ttk.Scrollbar(content, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        for candidate in rendered.candidates:
            text.insert("end", f"{candidate.heading}\n", "candidate_heading")
            text.insert("end", f"{candidate.body}\n\n")
        if rendered.diagnostics:
            text.insert("end", "Diagnostics\n", "candidate_heading")
            text.insert("end", rendered.diagnostics)
        text.tag_configure("candidate_heading", font=("Helvetica", 12, "bold"))
        text.configure(state="disabled")
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Button(window, text="Close", command=window.destroy).pack(
            pady=(0, 12)
        )

    def open_intelligence_explorer(self):
        try:
            rendered = self.collection_explorer_controller.open(
                self.current_dashboard_homepage
            )
        except Exception as exc:
            messagebox.showerror(
                "Collection Explorer unavailable",
                f"Collection Explorer could not be displayed:\n\n{exc}",
            )
            return

        window = tk.Toplevel(self)
        window.title(rendered.title)
        window.geometry("1050x720")
        window.minsize(800, 560)
        window.transient(self)

        notebook = ttk.Notebook(window)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)

        selected_index = 0
        for index, section in enumerate(rendered.sections):
            frame = ttk.Frame(notebook, padding=12)
            notebook.add(frame, text=section.title)
            if section.destination is rendered.selected_destination:
                selected_index = index
            text = tk.Text(frame, wrap="word", padx=10, pady=10)
            scrollbar = ttk.Scrollbar(
                frame,
                orient="vertical",
                command=text.yview,
            )
            text.configure(yscrollcommand=scrollbar.set)
            text.insert("1.0", section.body)
            text.configure(state="disabled")
            text.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
        notebook.select(selected_index)

        ttk.Button(window, text="Close", command=window.destroy).pack(
            pady=(0, 12)
        )

    def load_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        rows = self.db.review_rows(
            search=self.search_var.get().strip(),
            priority=self.priority_var.get(),
            decision=self.decision_filter_var.get()
        )
        for row in rows:
            self.tree.insert("", "end", iid=str(row["release_id"]), values=(
                row["artist"], row["title"], f"{row['lowest_price']:.2f}",
                row["wants"], row["copies_for_sale"], f"{row['opportunity_score']:.1f}",
                row["sell_window"], row["priority"], row["decision"]
            ))
        self.status_var.set(f"Showing {len(rows):,} records")

    def edit_selected(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        rid = int(selection[0])
        row = self.db.review_rows(limit=5000)
        record = next((x for x in row if x["release_id"] == rid), None)
        if not record:
            return

        window = tk.Toplevel(self)
        window.title(f"{record['artist']} — {record['title']}")
        window.geometry("650x560")
        window.transient(self)
        window.grab_set()

        ttk.Label(window, text=f"{record['artist']} — {record['title']}",
                  font=("Helvetica", 16, "bold"), wraplength=610).pack(anchor="w", padx=18, pady=(18,6))
        ttk.Label(window, text=record["explanation"], wraplength=610,
                  justify="left").pack(anchor="w", padx=18, pady=(0,14))

        form = ttk.Frame(window, padding=18)
        form.pack(fill="both", expand=True)

        decision = tk.StringVar(value=record["decision"])
        miss = tk.StringVar(value=record["miss_rating"])
        protected = tk.BooleanVar(value=bool(record["protected"]))

        ttk.Label(form, text="Decision").grid(row=0,column=0,sticky="w",pady=6)
        ttk.Combobox(form, textvariable=decision, state="readonly",
                     values=["Review","Keep","List for sale","Maybe","Ignore"]).grid(row=0,column=1,sticky="ew",pady=6)

        ttk.Label(form, text="Would I miss it?").grid(row=1,column=0,sticky="w",pady=6)
        ttk.Combobox(form, textvariable=miss, state="readonly",
                     values=["Never sell","Would miss it","Unsure","Would not miss it"]).grid(row=1,column=1,sticky="ew",pady=6)

        ttk.Checkbutton(form, text="Protect from sale shortlists",
                        variable=protected).grid(row=2,column=1,sticky="w",pady=6)

        ttk.Label(form, text="Personal notes").grid(row=3,column=0,sticky="nw",pady=6)
        notes = tk.Text(form, height=10, wrap="word")
        notes.grid(row=3,column=1,sticky="nsew",pady=6)
        notes.insert("1.0", record["personal_notes"])
        form.columnconfigure(1, weight=1)
        form.rowconfigure(3, weight=1)

        def save():
            self.db.save_decision(rid, decision.get(), miss.get(),
                                  notes.get("1.0","end").strip(), protected.get())
            window.destroy()
            self.refresh_dashboard()
            self.load_table()

        ttk.Button(window, text="Save", command=save).pack(pady=12)
    def export_intelligence_report(self):
        path = filedialog.asksaveasfilename(
            title="Save intelligence report",
            defaultextension=".md",
            filetypes=[
                ("Markdown files", "*.md"),
                ("All files", "*.*"),
            ],
            initialfile="discogs_intelligence_report.md",
        )

        if not path:
            return

        try:
            reporting_service = ReportingService(self.db)
            report = reporting_service.build_latest_report()
            markdown = render_markdown(report)

            Path(path).write_text(
                markdown,
                encoding="utf-8",
            )

            messagebox.showinfo(
                "Report exported",
                f"Intelligence report saved to:\n\n{path}",
            )

        except Exception as exc:
            messagebox.showerror(
                "Report export failed",
                f"An unexpected error occurred:\n\n{exc}",
            )

    def export_report(self):
        path = filedialog.asksaveasfilename(
            title="Save Excel export",
            defaultextension=".xlsx",
            initialfile="Discogs_Intelligence_Export.xlsx",
            filetypes=[("Excel workbook","*.xlsx")]
        )
        if not path:
            return
        rows = self.db.review_rows(limit=10000)
        export_excel(Path(path), rows)
        messagebox.showinfo("Export complete", f"Saved:\n{path}")

    def on_close(self):
        self.db.close()
        self.destroy()

if __name__ == "__main__":
    App().mainloop()
