"""Read-only Tk surface for the Current Collection Portfolio presentation."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from dip.app.portfolio_artist_inspection import PortfolioDistributionDimension

from dip.experience.current_collection_portfolio import (
    CurrentCollectionPortfolioPresentation,
    PortfolioDestination,
)


def _ratio(value) -> str:
    return f"{value.numerator:,}/{value.denominator:,} ({value.percentage})"


def _decimal(value) -> str:
    return value.value_text + (f" ({value.percentage})" if value.percentage else "")


def portfolio_lines(workspace: CurrentCollectionPortfolioPresentation) -> tuple[str, ...]:
    """Project only the closed presentation's factual fields into readable lines."""
    if type(workspace) is not CurrentCollectionPortfolioPresentation:
        raise TypeError("workspace must be a Current Collection Portfolio presentation.")
    if workspace.distribution is None:
        return (workspace.message,)
    if workspace.selected_destination is PortfolioDestination.DISTRIBUTION:
        view = workspace.distribution
        lines = [
            view.state_copy,
            f"Owned releases: {view.unique_owned_releases:,}    Owned copies: {view.owned_copies:,}    Additional copies: {view.duplicate_copies:,}",
            view.rounding_copy,
            f"Evidence coverage: {view.evidence_coverage}",
            f"Source: {view.module_id} {view.module_version}; rules {view.rule_set_version}; query {view.source_query_id}; ownership {view.ownership_data_version}; collection snapshot {view.collection_snapshot}",
        ]
        for dimension in view.dimensions:
            lines.extend((
                "", dimension.title,
                f"Metadata: {_ratio(dimension.release_coverage)} releases; {_ratio(dimension.copy_coverage)} copies",
                f"Missing metadata: {dimension.releases_missing_metadata:,} releases, {dimension.copies_missing_metadata:,} copies; release IDs: {', '.join(map(str, dimension.missing_release_ids)) or 'None'}",
                dimension.missing_metadata_copy,
                f"Categories: {dimension.represented_category_count:,}",
                f"Largest release categories: {', '.join(item.label for item in dimension.largest_release_categories) or 'Unavailable'}",
                f"Largest copy categories: {', '.join(item.label for item in dimension.largest_copy_categories) or 'Unavailable'}",
            ))
            for category in dimension.categories:
                lines.append(
                    f"{category.label} [{category.category_id}] — releases {_ratio(category.release_share)}; "
                    f"copies {_ratio(category.copy_share)}; release IDs {', '.join(map(str, category.release_ids))}"
                )
        return tuple(lines)

    view = workspace.concentration
    lines = [
        view.state_copy,
        f"Owned releases: {view.unique_owned_releases:,}    Owned copies: {view.owned_copies:,}    Additional copies: {view.duplicate_copies:,}",
        view.interpretation_copy,
        f"Evidence coverage: {view.evidence_coverage}; Distribution coverage: {view.source_evidence_coverage}",
        f"Source: {view.module_id} {view.module_version}; rules {view.rule_set_version}; Distribution {view.source_module_id} {view.source_module_version}; source rules {view.source_rule_set_version}; query {view.source_query_id}; ownership {view.ownership_data_version}; collection snapshot {view.collection_snapshot}",
    ]
    for dimension in view.dimensions:
        lines.extend((
            "", dimension.title, dimension.denominator_copy,
            f"Full collection metadata coverage: {_ratio(dimension.release_coverage)} releases; {_ratio(dimension.copy_coverage)} copies",
            f"Missing release IDs: {', '.join(map(str, dimension.missing_release_ids)) or 'None'}",
            f"Represented categories: {dimension.represented_category_count:,}",
        ))
        for basis in (dimension.release_basis, dimension.copy_basis):
            lines.extend((
                basis.title,
                f"Represented memberships: {basis.membership_total:,} {basis.denominator_label}; {basis.state_copy}",
                f"Largest-category share: {_ratio(basis.largest_share) if basis.largest_share else 'Unavailable'}; "
                f"largest: {', '.join(item.label for item in basis.largest_categories) or 'Unavailable'}",
                f"HHI: {_decimal(basis.hhi)}; normalized HHI: {_decimal(basis.normalized_hhi)}; effective categories: {_decimal(basis.effective_category_count)}",
            ))
            for first in (basis.first_three, basis.first_five):
                if first is not None:
                    lines.append(
                        f"{first.title}: {_ratio(first.membership_share)}; "
                        f"{first.included_count} included; {', '.join(item.label for item in first.contributors) or 'None'}"
                    )
        difference = dimension.difference
        lines.append(
            "Copy minus release: largest share " + _decimal(difference.largest_category_share_delta)
            + "; first three " + _decimal(difference.first_three_share_delta)
            + "; first five " + _decimal(difference.first_five_share_delta)
            + "; HHI " + _decimal(difference.hhi_delta)
            + "; normalized HHI " + _decimal(difference.normalized_hhi_delta)
            + "; effective categories " + _decimal(difference.effective_category_count_delta)
        )
    if view.unusable_dimensions:
        lines.append("Unusable dimensions: " + ", ".join(view.unusable_dimensions))
    return tuple(lines)


class CurrentCollectionPortfolioWindow:
    """One transient window; all scroll bindings live on its own text widget."""

    def __init__(self, parent, on_refresh, on_close, on_inspect=None, before_close=None):
        self.window = tk.Toplevel(parent)
        self.window.title("Current Collection Portfolio")
        self.window.geometry("880x650")
        self.window.minsize(800, 560)
        self.window.transient(parent)
        self._on_close = on_close
        self._on_inspect = on_inspect
        self._before_close = before_close
        self._run_active = False
        self._closed = False
        self._workspace = None
        shell = ttk.Frame(self.window, padding=10)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="Current Collection", font=("Helvetica", 16, "bold")).pack(anchor="w")
        ttk.Label(shell, text="Calculated from current ownership and catalogue metadata", wraplength=760).pack(anchor="w")
        self.freshness = tk.StringVar(value="Loading…")
        ttk.Label(shell, textvariable=self.freshness).pack(anchor="w")
        self.error = tk.StringVar(value="")
        ttk.Label(shell, textvariable=self.error, wraplength=760).pack(anchor="w")
        controls = ttk.Frame(shell)
        controls.pack(fill="x", pady=(8, 6))
        self.navigation = ttk.Combobox(controls, state="readonly", values=("Distribution", "Concentration"), width=22)
        self.navigation.pack(side="left", padx=(0, 8))
        self.navigation.current(0)
        self.navigation.bind("<<ComboboxSelected>>", self._select)
        self.refresh_button = ttk.Button(controls, text="Refresh Portfolio", command=on_refresh)
        self.refresh_button.pack(side="left")
        self.close_button = ttk.Button(controls, text="Close", command=self.close)
        self.close_button.pack(side="right")
        self.artist_controls = ttk.Frame(shell)
        ttk.Label(self.artist_controls, text="Dimension:").grid(row=0, column=0, sticky="w")
        self.inspection_dimension = ttk.Combobox(self.artist_controls, state="readonly", width=22)
        self.inspection_dimension.grid(row=0, column=1, sticky="ew", padx=5, pady=(0, 3))
        self.inspection_dimension.bind("<<ComboboxSelected>>", self._select_inspection_dimension)
        ttk.Label(self.artist_controls, text="Category:").grid(row=1, column=0, sticky="w")
        self.artist_category = ttk.Combobox(self.artist_controls, state="readonly", width=30)
        self.artist_category.grid(row=1, column=1, sticky="ew", padx=5)
        self.inspect_button = ttk.Button(self.artist_controls, text="Inspect releases", command=self._inspect)
        self.inspect_button.grid(row=1, column=2)
        self.artist_controls.columnconfigure(1, weight=1)
        self.artist_reason = tk.StringVar(value="")
        ttk.Label(self.artist_controls, textvariable=self.artist_reason, wraplength=760).grid(row=2, column=0, columnspan=3, sticky="w")
        body = ttk.Frame(shell)
        body.pack(fill="both", expand=True)
        self.text = tk.Text(body, wrap="word", state="disabled", padx=10, pady=10, takefocus=True)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._body = body
        self._focus_order = (self.navigation, self.refresh_button, self.inspection_dimension, self.artist_category, self.inspect_button, self.text, self.close_button)
        for widget in self._focus_order:
            widget.configure(takefocus=1)
            widget.bind("<Tab>", lambda _event, current=widget: self._traverse(current, 1))
            widget.bind("<Shift-Tab>", lambda _event, current=widget: self._traverse(current, -1))
            widget.bind("<ISO_Left_Tab>", lambda _event, current=widget: self._traverse(current, -1))
        for button in (self.refresh_button, self.inspect_button, self.close_button):
            for key in ("<Return>", "<space>"):
                button.bind(key, lambda _event, control=button: self._activate(control))
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Destroy>", self._destroyed, add="+")

    def alive(self) -> bool:
        return not self._closed and bool(self.window.winfo_exists())

    def focus(self) -> None:
        self.window.deiconify()
        self.window.lift()
        self.window.focus_set()

    def show(self, workspace: CurrentCollectionPortfolioPresentation, *, freshness: str, error: str = "") -> None:
        self._workspace = workspace
        self.freshness.set(freshness)
        self.error.set(error)
        self.navigation.current(0 if workspace.selected_destination is PortfolioDestination.DISTRIBUTION else 1)
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(portfolio_lines(workspace)))
        self.text.configure(state="disabled")
        self.text.yview_moveto(0)
        previous_dimensions = getattr(self, "_inspection_dimensions", ())
        previous_index = self.inspection_dimension.current()
        previous_dimension = (previous_dimensions[previous_index].dimension_id
                              if 0 <= previous_index < len(previous_dimensions) else "artist")
        previous_category_index = self.artist_category.current()
        previous_categories = getattr(self, "_artist_categories", ())
        previous_category = (previous_categories[previous_category_index].category_id
                             if 0 <= previous_category_index < len(previous_categories) else None)
        self._inspection_dimensions = tuple(workspace.distribution.dimensions if workspace.distribution else ())
        self.inspection_dimension.configure(values=tuple(value.title for value in self._inspection_dimensions))
        self.inspection_dimension.set("")
        if self._inspection_dimensions:
            index = next((i for i, value in enumerate(self._inspection_dimensions)
                          if value.dimension_id == previous_dimension), 0)
            self.inspection_dimension.current(index)
        self._set_inspection_categories(previous_category)
        if workspace.selected_destination is PortfolioDestination.DISTRIBUTION:
            self.artist_controls.pack(before=self._body, fill="x", pady=(0, 5))
        else:
            self.artist_controls.pack_forget()
        self.set_run_active(self._run_active)

    def _select(self, _event=None) -> None:
        if self._workspace is None:
            return
        from dataclasses import replace
        destination = (PortfolioDestination.DISTRIBUTION, PortfolioDestination.CONCENTRATION)[self.navigation.current()]
        self.show(replace(self._workspace, selected_destination=destination), freshness=self.freshness.get(), error=self.error.get())

    def _set_inspection_categories(self, category_id=None):
        position = self.inspection_dimension.current()
        dimension = (self._inspection_dimensions[position]
                     if 0 <= position < len(self._inspection_dimensions) else None)
        # Preserve authoritative source order; IDs are scoped to this dimension.
        self._category_dimension_id = dimension.dimension_id if dimension else None
        self._artist_categories = tuple(dimension.categories if dimension else ())
        self.artist_category.configure(values=tuple(f"{value.label} [{value.category_id}]" for value in self._artist_categories))
        self.artist_category.set("")
        if self._artist_categories:
            self.artist_category.current(next((i for i, value in enumerate(self._artist_categories)
                                               if value.category_id == category_id), 0))

    def _select_inspection_dimension(self, _event=None):
        # No lookup/execution and no replacement of an existing inspection/draft.
        self._set_inspection_categories()
        self.set_run_active(self._run_active)

    def set_run_active(self, active: bool) -> None:
        self._run_active = active
        self.refresh_button.state(["disabled"] if active else ["!disabled"])
        available = not active and self._on_inspect is not None and bool(getattr(self, "_inspection_dimensions", ()))
        self.inspection_dimension.configure(state="readonly" if available else "disabled")
        enabled = available and bool(getattr(self, "_artist_categories", ()))
        self.artist_category.configure(state="readonly" if enabled else "disabled")
        self.inspect_button.state(["!disabled"] if enabled else ["disabled"])
        self.artist_reason.set(
            "Category inspection is unavailable while Collector Run is active." if active
            else "Category inspection is unavailable." if self._on_inspect is None
            else "No represented categories in this dimension." if not getattr(self, "_artist_categories", ())
            else ""
        )

    def _inspect(self):
        if "disabled" not in self.inspect_button.state() and self._workspace.selected_destination is PortfolioDestination.DISTRIBUTION:
            dimension_position = self.inspection_dimension.current()
            position = self.artist_category.current()
            if (0 <= dimension_position < len(self._inspection_dimensions)
                    and self._inspection_dimensions[dimension_position].dimension_id == self._category_dimension_id
                    and 0 <= position < len(self._artist_categories)):
                self._on_inspect(self._artist_categories[position].category_id,
                                 dimension=PortfolioDistributionDimension(self._category_dimension_id))

    def _traverse(self, current, step: int) -> str:
        if not self.alive():
            return "break"
        try:
            position = self._focus_order.index(current)
        except ValueError:
            return "break"
        for offset in range(1, len(self._focus_order) + 1):
            widget = self._focus_order[(position + step * offset) % len(self._focus_order)]
            if getattr(widget, "winfo_ismapped", lambda: True)() and "disabled" not in getattr(widget, "state", lambda: ())():
                widget.focus_set()
                break
        return "break"

    @staticmethod
    def _activate(button) -> str:
        if "disabled" not in button.state():
            button.invoke()
        return "break"

    def close(self) -> None:
        if not self._closed and (self._before_close is None or self._before_close() is not False):
            self.window.destroy()

    def _destroyed(self, event) -> None:
        if event.widget is self.window and not self._closed:
            self._closed = True
            self._on_close()
