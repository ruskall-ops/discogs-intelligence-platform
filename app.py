
from __future__ import annotations
import getpass
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from database import Database
from discogs_client import DiscogsClient
from scoring import calculate
from report import export_excel
from importers import CollectionImportError, DiscogsCSVImporter

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "discogs_intelligence.db"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Discogs Intelligence Platform")
        self.geometry("1380x820")
        self.minsize(1050, 650)
        self.db = Database(DB_PATH)
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
            ("total", "Collection"),
            ("high_priority", "High-priority reviews"),
            ("worth_reviewing", "Worth reviewing"),
            ("hot_now", "Hot now"),
            ("protected", "Protected / Keep"),
        ]
        for index, (key, label) in enumerate(labels):
            box = ttk.LabelFrame(self.dashboard_tab, text=label, padding=15)
            box.grid(row=0, column=index, padx=8, pady=8, sticky="nsew")
            value = ttk.Label(box, text="0", font=("Helvetica", 24, "bold"))
            value.pack()
            self.kpis[key] = value
            self.dashboard_tab.columnconfigure(index, weight=1)

        info = ttk.LabelFrame(self.dashboard_tab, text="Platform status", padding=16)
        info.grid(row=1, column=0, columnspan=5, padx=8, pady=20, sticky="ew")
        ttk.Label(info, text=(
            "SQLite is now the source of truth. Collection details, market snapshots, "
            "scores, decisions and notes persist between runs. Excel is generated only "
            "when you want an export."
        ), wraplength=1100, justify="left").pack(anchor="w")

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
            importer = DiscogsCSVImporter()
            result = importer.read(Path(path))

            count = self.db.import_releases(
                result.rows,
                result.release_id_column,
            )

            self.status_var.set(
                f"Imported {count:,} collection rows "
                f"({result.invalid_release_ids:,} invalid rows skipped)"
            )

            self.refresh_dashboard()
            self.load_table()

            messagebox.showinfo(
                "Import complete",
                (
                    f"Imported or updated {count:,} records.\n\n"
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
        client = DiscogsClient(token)
        captured_at = datetime.now().isoformat(timespec="seconds")
        self.progress["maximum"] = len(ids)
        errors = 0

        for pos, rid in enumerate(ids, start=1):
            try:
                data = client.get_release(rid)
                if data:
                    previous = self.db.previous_snapshot(rid, captured_at)
                    self.db.add_snapshot(rid, captured_at, data)
                    score = calculate(data, previous)
                    self.db.upsert_score(rid, captured_at, score)
            except Exception:
                errors += 1
            self.progress["value"] = pos
            self.status_var.set(f"Refreshing {pos:,}/{len(ids):,} — errors {errors}")
            self.update_idletasks()
            time.sleep(1.08)

        self.status_var.set(f"Refresh complete — {len(ids)-errors:,} successful, {errors} errors")
        self.refresh_dashboard()
        self.load_table()
        messagebox.showinfo("Refresh complete", self.status_var.get())

    def refresh_dashboard(self):
        row = self.db.dashboard()
        for key, widget in self.kpis.items():
            widget.configure(text=f"{int(row[key] or 0):,}")

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
