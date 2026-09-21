"""Read-only Tk surface for the Current Collection Portfolio presentation."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

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

    def __init__(self, parent, on_refresh, on_close):
        self.window = tk.Toplevel(parent)
        self.window.title("Current Collection Portfolio")
        self.window.geometry("880x650")
        self.window.minsize(800, 560)
        self.window.transient(parent)
        self._on_close = on_close
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
        body = ttk.Frame(shell)
        body.pack(fill="both", expand=True)
        self.text = tk.Text(body, wrap="word", state="disabled", padx=10, pady=10, takefocus=True)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self._focus_order = (self.navigation, self.refresh_button, self.text, self.close_button)
        for widget in self._focus_order:
            widget.configure(takefocus=1)
            widget.bind("<Tab>", lambda _event, current=widget: self._traverse(current, 1))
            widget.bind("<Shift-Tab>", lambda _event, current=widget: self._traverse(current, -1))
            widget.bind("<ISO_Left_Tab>", lambda _event, current=widget: self._traverse(current, -1))
        for button in (self.refresh_button, self.close_button):
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

    def _select(self, _event=None) -> None:
        if self._workspace is None:
            return
        from dataclasses import replace
        destination = (PortfolioDestination.DISTRIBUTION, PortfolioDestination.CONCENTRATION)[self.navigation.current()]
        self.show(replace(self._workspace, selected_destination=destination), freshness=self.freshness.get(), error=self.error.get())

    def set_run_active(self, active: bool) -> None:
        self.refresh_button.state(["disabled"] if active else ["!disabled"])

    def _traverse(self, current, step: int) -> str:
        if not self.alive():
            return "break"
        try:
            position = self._focus_order.index(current)
        except ValueError:
            return "break"
        for offset in range(1, len(self._focus_order) + 1):
            widget = self._focus_order[(position + step * offset) % len(self._focus_order)]
            if "disabled" not in getattr(widget, "state", lambda: ())():
                widget.focus_set()
                break
        return "break"

    @staticmethod
    def _activate(button) -> str:
        if "disabled" not in button.state():
            button.invoke()
        return "break"

    def close(self) -> None:
        if not self._closed:
            self.window.destroy()

    def _destroyed(self, event) -> None:
        if event.widget is self.window and not self._closed:
            self._closed = True
            self._on_close()
