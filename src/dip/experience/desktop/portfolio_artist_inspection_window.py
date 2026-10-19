"""Thin Tk view over retained Artist membership and supplementary labels."""

import tkinter as tk
from tkinter import ttk, font

from dip.app.portfolio_artist_inspection import ArtistInspection
from dip.experience.current_collection_portfolio import PresentedRatio
from dip.experience.desktop.current_collection_portfolio_window import _ratio


class PortfolioArtistInspectionWindow:
    def __init__(self, parent, inspection: ArtistInspection, freshness: str, on_open, on_close):
        self.inspection = inspection
        self._on_open = on_open
        self._on_close = on_close
        self._active = False
        self._closed = False
        self.window = tk.Toplevel(parent)
        try:
            self.window.title("Artist category — contributing releases")
            self.window.geometry("800x560")
            self.window.minsize(800, 560)
            self.window.transient(parent)
            shell = ttk.Frame(self.window, padding=10)
            shell.pack(fill="both", expand=True)
            category = inspection.category
            # Catalogue labels have no length limit. Keep the complete label in
            # a bounded viewport rather than letting it displace members/actions.
            heading_region = ttk.Frame(shell)
            heading_region.pack(fill="x", pady=(0, 5))
            self.heading = tk.Text(
                heading_region, height=4, width=1, wrap="word",
                font="TkDefaultFont", takefocus=True, padx=5, pady=5,
            )
            heading_scroll = ttk.Scrollbar(
                heading_region, orient="vertical", command=self.heading.yview,
            )
            self.heading.configure(yscrollcommand=heading_scroll.set)
            self.heading.pack(side="left", fill="x", expand=True)
            heading_scroll.pack(side="right", fill="y")
            self.heading.insert("1.0", f"Artist category: {category.display_name}")
            self.heading.configure(state="disabled")
            ttk.Label(shell, text=(
                "Retained releases: " + _ratio(PresentedRatio(category.unique_release_count, category.release_denominator, category.release_ratio))
                + "; copies: " + _ratio(PresentedRatio(category.owned_copy_count, category.copy_denominator, category.copy_ratio))
            ), wraplength=760).pack(anchor="w")
            source = inspection.source.distribution.output.provenance
            ttk.Label(shell, text=f"Source: {inspection.source.distribution.module_id} {inspection.source.distribution.module_version}; query {source.source_query_id}", wraplength=760).pack(anchor="w")
            self.freshness = tk.StringVar(value=freshness)
            ttk.Label(shell, textvariable=self.freshness, wraplength=760).pack(anchor="w")
            ttk.Label(shell, text=("Membership, copies and totals are from the displayed Portfolio calculation. "
                "Catalogue labels were read when this inspection opened and may differ from that calculation."), wraplength=760).pack(anchor="w", pady=5)
            self.status = tk.StringVar(value=inspection.label_error or "Select a release, then explicitly open its Collection Decision.")
            self.status_label = ttk.Label(shell, textvariable=self.status, wraplength=760)
            self.status_label.pack(anchor="w")
            body = ttk.Frame(shell)
            body.pack(fill="both", expand=True, pady=6)
            self.tree = ttk.Treeview(body, columns=("id", "copies", "artist", "title"), show="headings", selectmode="browse")
            for name, title, width in (("id", "Release ID", 90), ("copies", "Copies at calculation", 145), ("artist", "Current catalogue artist", 220), ("title", "Current catalogue title", 280)):
                self.tree.heading(name, text=title)
                self.tree.column(name, width=width, minwidth=width, stretch=name in ("artist", "title"))
            vertical = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
            horizontal = ttk.Scrollbar(body, orient="horizontal", command=self.tree.xview)
            self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
            self.tree.grid(row=0, column=0, sticky="nsew")
            vertical.grid(row=0, column=1, sticky="ns")
            horizontal.grid(row=1, column=0, sticky="ew")
            body.rowconfigure(0, weight=1)
            body.columnconfigure(0, weight=1)
            for member in inspection.members:
                metadata = member.current_metadata
                self.tree.insert("", "end", iid=str(member.release_id), values=(member.release_id, member.copies_at_calculation,
                    (metadata.artist or "Unavailable") if metadata else "Record unavailable",
                    (metadata.title or "Unavailable") if metadata else "Record unavailable"))
            metrics = font.nametofont("TkDefaultFont")
            for column in ("id", "copies", "artist", "title"):
                position = ("id", "copies", "artist", "title").index(column)
                width = max(metrics.measure(self.tree.heading(column, "text")), *(metrics.measure(str(self.tree.item(iid, "values")[position])) for iid in self.tree.get_children())) + 24
                self.tree.column(column, width=width, minwidth=width)
            actions = ttk.Frame(shell)
            # Reserve actions before the expanding member viewport.
            actions.pack(side="bottom", fill="x", before=body)
            self.open_button = ttk.Button(actions, text="Open Collection Decision", command=self.open_selected)
            self.open_button.pack(side="left")
            self.close_button = ttk.Button(actions, text="Close", command=self.close)
            self.close_button.pack(side="right")
            self.heading.bind("<Tab>", lambda _event: self._focus_control(self.tree))
            for key in ("<Shift-Tab>", "<ISO_Left_Tab>"):
                self.heading.bind(key, lambda _event: self._focus_control(self.close_button))
            self.tree.bind("<<TreeviewSelect>>", lambda _event: self._availability())
            for button in (self.open_button, self.close_button):
                for key in ("<Return>", "<space>"):
                    button.bind(key, lambda _event, control=button: self._activate(control))
            self.window.protocol("WM_DELETE_WINDOW", self.close)
            self.window.bind("<Destroy>", self._destroyed, add="+")
            self._availability()
        except Exception:
            self.window.destroy()
            raise

    def alive(self):
        return not self._closed and bool(self.window.winfo_exists())

    def set_run_active(self, active):
        self._active = active
        self._availability()

    def _availability(self):
        selected = self.tree.selection()
        member = next((value for value in self.inspection.members if selected and str(value.release_id) == selected[0]), None)
        enabled = not self._active and not self.inspection.label_error and member is not None and member.current_metadata is not None
        self.open_button.state(["!disabled"] if enabled else ["disabled"])
        if self._active:
            self.status.set("Collection Decision opening is unavailable while Collector Run is active.")
        elif self.inspection.label_error:
            self.status.set(self.inspection.label_error)
        elif member is not None and member.current_metadata is None:
            self.status.set("This retained member has no current catalogue record. Its membership and totals are unchanged.")
        else:
            self.status.set("Select a release, then explicitly open its Collection Decision.")

    def open_selected(self):
        if "disabled" not in self.open_button.state():
            self._on_open(int(self.tree.selection()[0]))

    @staticmethod
    def _focus_control(control):
        control.focus_set()
        return "break"

    @staticmethod
    def _activate(button):
        if "disabled" not in button.state():
            button.invoke()
        return "break"

    def close(self):
        if self._on_close() is not False and self.alive():
            self.window.destroy()

    def _destroyed(self, event):
        if event.widget is self.window:
            self._closed = True
