
from __future__ import annotations
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from dip.app.collector_run import (
    CollectorRunExecutionError,
    CollectorRunProgress,
    CollectorRunResult,
    CollectorRunStatus,
    CollectorRunUnavailableError,
)
from dip.collection.importers import CollectionImportError
from dip.collection.services import ImportService
from dip.collector_review import (
    HiddenGemObservation,
    HotNowObservation,
    ObservationIdentity,
    ObservationSectionStatus,
    WeekendObservationSource,
    WeekendObservationWorkspace,
    WeekendReviewConflictError,
    WeekendReviewItemNotFoundError,
    WeekendReviewQueueItem,
    WeekendReviewStatus,
    WeekendReviewTransitionError,
)
from dip.composition import build_desktop_application_dependencies
from dip.config import SETTINGS
from dip.experience.reporting import ReportingService, render_markdown
from dip.experience.dashboard import (
    DashboardHomepageViewModel,
    DashboardNavigationTarget,
)
from dip.experience.portfolio_workspace import PortfolioWorkspaceDestination
from dip.experience.project_workspace import ProjectWorkspaceNavigationTarget
from dip.experience.desktop.homepage_renderer import (
    DesktopDashboardHomepageRenderer,
)
from dip.exports import export_excel

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
        self.portfolio_overview_controller = dependencies.portfolio_overview_controller
        self.portfolio_controller = dependencies.portfolio_controller
        self.portfolio_workspace_controller = getattr(
            dependencies, "portfolio_workspace_controller", None
        )
        self.intelligence_change_analysis_controller = getattr(
            dependencies, "intelligence_change_analysis_controller", None
        )
        self.intelligence_trend_analysis_controller = getattr(
            dependencies, "intelligence_trend_analysis_controller", None
        )
        self.history_explorer_controller = getattr(
            dependencies, "history_explorer_controller", None
        )
        self.intelligence_insights_controller = getattr(
            dependencies, "intelligence_insights_controller", None
        )
        self.marketplace_workspace_controller = getattr(
            dependencies, "marketplace_workspace_controller", None
        )
        self.dashboard_command_center_controller = getattr(
            dependencies, "dashboard_command_center_controller", None
        )
        self.project_workspace_controller = getattr(
            dependencies, "project_workspace_controller", None
        )
        self.collector_run_service = getattr(
            dependencies, "collector_run", None
        )
        self.collector_review_observations = getattr(
            dependencies, "collector_review_observations", None
        )
        self.collector_review_service = getattr(
            dependencies, "collector_review", None
        )
        self._collector_run_active = False
        self.current_observation_workspace = (
            WeekendObservationWorkspace.unavailable(
                "Collector Review observations are loading."
            )
        )
        self.current_queue_item = None
        self._queue_note_dirty = False
        self._queue_note_loading = False
        self._review_tab_change_guard = False
        self._last_queue_filter = "Active"
        self.current_portfolio_overview_result = None
        self.current_portfolio_distribution_result = None
        self.current_portfolio_concentration_result = None
        self.current_portfolio_opportunity_alignment_result = None
        self.current_intelligence_change_analysis_result = None
        self.current_intelligence_trend_analysis_result = None
        self.current_history_snapshot_view_models = ()
        self.current_history_change_view_models = ()
        self.current_history_trend_view_models = ()
        self.current_intelligence_insight_collections = ()
        self.current_marketplace_workspace_queue = ()
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

        self.import_csv_button = ttk.Button(
            toolbar,
            text="Import Collection CSV",
            command=self.import_csv,
        )
        self.import_csv_button.pack(side="left", padx=3)
        self.refresh_discogs_button = ttk.Button(
            toolbar,
            text="Refresh Discogs Data",
            command=self.start_refresh,
        )
        self.refresh_discogs_button.pack(side="left", padx=3)
        ttk.Button(toolbar, text="Export Excel", command=self.export_report).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Export Intelligence Report", command=self.export_intelligence_report).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Refresh View", command=self.load_table).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Portfolio", command=self.open_portfolio_overview).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Historical Intelligence", command=self.open_intelligence_change_analysis).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Marketplace Workspace", command=self.open_marketplace_workspace).pack(side="left", padx=3)

        self.progress = ttk.Progressbar(toolbar, length=260, mode="determinate")
        self.progress.pack(side="right", padx=5)
        ttk.Label(toolbar, textvariable=self.status_var).pack(side="right", padx=8)

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)

        self.project_tab = ttk.Frame(self.tabs, padding=18)
        self.dashboard_tab = ttk.Frame(self.tabs, padding=18)
        self.review_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.project_tab, text="Project")
        self.tabs.add(self.dashboard_tab, text="Dashboard")
        self.tabs.add(self.review_tab, text="Collection Review")
        self._build_project_workspace()

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

            if key == "hot_now":
                value = ttk.Button(
                    box,
                    text="0",
                    command=lambda: self.open_collection_review_observations(
                        WeekendObservationSource.HOT_NOW
                    ),
                )
                self.hot_now_kpi_button = value
            else:
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
                self.hidden_gems_observations_button = ttk.Button(
                    card,
                    text="Review in Observations",
                    command=lambda: self.open_collection_review_observations(
                        WeekendObservationSource.HIDDEN_GEM
                    ),
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
        self.dashboard_command_vars = {}
        command_cards = (
            ("Portfolio Summary", 6, 0), ("Portfolio Health", 6, 3),
            ("Opportunity Highlights", 7, 0), ("Collection Changes", 7, 3),
            ("Historical Changes", 8, 0), ("Marketplace Highlights", 8, 3),
            ("Research Summary", 9, 0), ("Quick Actions", 9, 3),
        )
        for title, row, column in command_cards:
            card = ttk.LabelFrame(self.dashboard_tab, text=title, padding=14)
            card.grid(row=row, column=column, columnspan=3, padx=8, pady=8, sticky="nsew")
            body = tk.StringVar(value="Workspace summary is loading…")
            ttk.Label(card, textvariable=body, wraplength=350, justify="left").pack(
                anchor="nw", fill="both", expand=True
            )
            actions = ttk.Frame(card)
            actions.pack(anchor="w", fill="x", pady=(10, 0))
            self.dashboard_command_vars[title] = (body, actions)

        self.collection_review_tabs = ttk.Notebook(self.review_tab)
        self.collection_review_tabs.pack(fill="both", expand=True)
        self.observations_tab = ttk.Frame(
            self.collection_review_tabs,
            padding=8,
        )
        self.queue_tab = ttk.Frame(
            self.collection_review_tabs,
            padding=8,
        )
        self.decisions_tab = ttk.Frame(
            self.collection_review_tabs,
            padding=8,
        )
        self.collection_review_tabs.add(
            self.observations_tab,
            text="Observations",
        )
        self.collection_review_tabs.add(
            self.queue_tab,
            text="Weekend Review Queue",
        )
        self.collection_review_tabs.add(
            self.decisions_tab,
            text="Collection Decisions",
        )
        self.collection_review_tabs.bind(
            "<<NotebookTabChanged>>",
            self._on_collection_review_destination_changed,
        )
        self._build_observations_ui()
        self._build_weekend_queue_ui()

        filters = ttk.Frame(self.decisions_tab)
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
        self.tree = ttk.Treeview(self.decisions_tab, columns=cols, show="headings", selectmode="browse")
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

        scroll = ttk.Scrollbar(self.decisions_tab, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)

    def _build_observations_ui(self):
        controls = ttk.Frame(self.observations_tab)
        controls.pack(fill="x", pady=(0, 8))
        ttk.Label(controls, text="Source").pack(side="left")
        self.observation_source_var = tk.StringVar(value="Hot now")
        source = ttk.Combobox(
            controls,
            textvariable=self.observation_source_var,
            state="readonly",
            values=("Hot now", "Hidden Gems"),
            width=18,
        )
        source.pack(side="left", padx=6)
        source.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._render_observations(),
        )
        ttk.Button(
            controls,
            text="Refresh Observations",
            command=self.refresh_collector_review_observations,
        ).pack(side="left", padx=6)
        self.observation_summary_var = tk.StringVar(
            value="Collector Review observations are loading."
        )
        ttk.Label(
            controls,
            textvariable=self.observation_summary_var,
        ).pack(side="left", padx=12)

        content = ttk.Panedwindow(self.observations_tab, orient="horizontal")
        content.pack(fill="both", expand=True)
        left = ttk.Frame(content)
        right = ttk.Frame(content, padding=(10, 0, 0, 0))
        content.add(left, weight=2)
        content.add(right, weight=3)

        columns = ("artist", "title", "signal", "queue")
        self.observation_tree = ttk.Treeview(
            left,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        for column, label, width in (
            ("artist", "Artist", 190),
            ("title", "Title", 260),
            ("signal", "Research signal", 140),
            ("queue", "Queue", 110),
        ):
            self.observation_tree.heading(column, text=label)
            self.observation_tree.column(column, width=width, anchor="w")
        observation_scroll = ttk.Scrollbar(
            left,
            orient="vertical",
            command=self.observation_tree.yview,
        )
        self.observation_tree.configure(
            yscrollcommand=observation_scroll.set
        )
        self.observation_tree.pack(side="left", fill="both", expand=True)
        observation_scroll.pack(side="right", fill="y")
        self.observation_tree.bind(
            "<<TreeviewSelect>>",
            self._on_observation_selected,
        )

        self.observation_detail = tk.Text(
            right,
            wrap="word",
            padx=10,
            pady=10,
        )
        self.observation_detail.configure(state="disabled")
        self.observation_detail.pack(fill="both", expand=True)
        actions = ttk.Frame(right)
        actions.pack(fill="x", pady=(8, 0))
        self.add_observation_button = ttk.Button(
            actions,
            text="Add to Weekend Review Queue",
            command=self._add_selected_observation,
        )
        self.add_observation_button.pack(side="left", padx=(0, 6))
        self.reopen_observation_button = ttk.Button(
            actions,
            text="Reopen",
            command=self._reopen_selected_observation,
        )
        self.reopen_observation_button.pack(side="left", padx=(0, 6))
        self.open_queued_observation_button = ttk.Button(
            actions,
            text="Open queued item",
            command=self._open_selected_observation_queue_item,
        )
        self.open_queued_observation_button.pack(side="left")
        self._set_observation_action_state(None)

    def _build_weekend_queue_ui(self):
        controls = ttk.Frame(self.queue_tab)
        controls.pack(fill="x", pady=(0, 8))
        ttk.Label(controls, text="View").pack(side="left")
        self.queue_filter_var = tk.StringVar(value="Active")
        queue_filter = ttk.Combobox(
            controls,
            textvariable=self.queue_filter_var,
            state="readonly",
            values=("Active", "Resolved", "All"),
            width=14,
        )
        queue_filter.pack(side="left", padx=6)
        queue_filter.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._change_queue_filter(),
        )
        ttk.Button(
            controls,
            text="Refresh Queue",
            command=self.refresh_weekend_review_queue,
        ).pack(side="left", padx=6)
        self.queue_summary_var = tk.StringVar(value="Queue is loading.")
        ttk.Label(
            controls,
            textvariable=self.queue_summary_var,
        ).pack(side="left", padx=12)

        content = ttk.Panedwindow(self.queue_tab, orient="horizontal")
        content.pack(fill="both", expand=True)
        left = ttk.Frame(content)
        right = ttk.Frame(content, padding=(10, 0, 0, 0))
        content.add(left, weight=2)
        content.add(right, weight=3)

        self.queue_tree = ttk.Treeview(
            left,
            columns=("artist", "title", "status", "source"),
            show="headings",
            selectmode="browse",
        )
        for column, label, width in (
            ("artist", "Artist", 180),
            ("title", "Title", 250),
            ("status", "Status", 100),
            ("source", "Source", 100),
        ):
            self.queue_tree.heading(column, text=label)
            self.queue_tree.column(column, width=width, anchor="w")
        queue_scroll = ttk.Scrollbar(
            left,
            orient="vertical",
            command=self.queue_tree.yview,
        )
        self.queue_tree.configure(yscrollcommand=queue_scroll.set)
        self.queue_tree.pack(side="left", fill="both", expand=True)
        queue_scroll.pack(side="right", fill="y")
        self.queue_tree.bind(
            "<<TreeviewSelect>>",
            self._on_queue_selected,
        )

        self.queue_detail_var = tk.StringVar(value="Select a queue item.")
        ttk.Label(
            right,
            textvariable=self.queue_detail_var,
            wraplength=540,
            justify="left",
        ).pack(anchor="w", fill="x")
        ttk.Label(right, text="Review note").pack(
            anchor="w",
            pady=(12, 4),
        )
        self.queue_note = tk.Text(right, height=10, wrap="word")
        self.queue_note.pack(fill="both", expand=True)
        self.queue_note.bind("<KeyRelease>", self._on_queue_note_edited)
        self.queue_note.configure(state="disabled")

        actions = ttk.Frame(right)
        actions.pack(fill="x", pady=(8, 0))
        self.queue_save_button = ttk.Button(
            actions,
            text="Save note",
            command=self._save_queue_note,
        )
        self.queue_save_button.pack(side="left", padx=(0, 5))
        self.queue_status_button = ttk.Button(
            actions,
            text="Start Review",
            command=self._toggle_queue_status,
        )
        self.queue_status_button.pack(side="left", padx=(0, 5))
        self.queue_resolve_button = ttk.Button(
            actions,
            text="Resolve",
            command=self._resolve_or_reopen_queue_item,
        )
        self.queue_resolve_button.pack(side="left", padx=(0, 5))
        self.queue_remove_button = ttk.Button(
            actions,
            text="Remove",
            command=self._remove_queue_item,
        )
        self.queue_remove_button.pack(side="left", padx=(0, 5))
        self.queue_decision_button = ttk.Button(
            actions,
            text="Open Collection Decision",
            command=self._open_queue_collection_decision,
        )
        self.queue_decision_button.pack(side="left")
        self._set_queue_controls_enabled(False)

    def _observation_source(self):
        return (
            WeekendObservationSource.HIDDEN_GEM
            if self.observation_source_var.get() == "Hidden Gems"
            else WeekendObservationSource.HOT_NOW
        )

    def _observation_section(self):
        return (
            self.current_observation_workspace.hidden_gems_section
            if self._observation_source()
            is WeekendObservationSource.HIDDEN_GEM
            else self.current_observation_workspace.hot_now_section
        )

    def _render_observations(self, preserve_identity=None):
        if preserve_identity is None:
            preserve_identity = self._selected_observation_identity()
        for item in self.observation_tree.get_children():
            self.observation_tree.delete(item)
        section = self._observation_section()
        self.observation_summary_var.set(section.summary)
        for observation in section.observations:
            membership = observation.queue_membership
            queue_label = (
                "Not queued"
                if not membership.is_queued
                else "Resolved"
                if membership.status is WeekendReviewStatus.RESOLVED
                else "Queued"
            )
            signal = (
                f"Opportunity {observation.opportunity_score:.1f}"
                if type(observation) is HotNowObservation
                else f"Hidden Gem #{observation.rank}"
            )
            iid = self._observation_iid(observation.observation_id)
            self.observation_tree.insert(
                "",
                "end",
                iid=iid,
                values=(
                    observation.artist,
                    observation.title,
                    signal,
                    queue_label,
                ),
            )
        if (
            preserve_identity is not None
            and self.observation_tree.exists(
                self._observation_iid(preserve_identity)
            )
        ):
            iid = self._observation_iid(preserve_identity)
            self.observation_tree.selection_set(iid)
            self.observation_tree.see(iid)
        else:
            self._show_observation_detail(None)

    @staticmethod
    def _observation_iid(identity):
        return f"{identity.source.value}:{identity.release_id}"

    def _selected_observation_identity(self):
        selection = self.observation_tree.selection()
        if not selection:
            return None
        source, release_id = selection[0].split(":", 1)
        return ObservationIdentity(
            WeekendObservationSource(source),
            int(release_id),
        )

    def _selected_observation(self):
        identity = self._selected_observation_identity()
        if identity is None:
            return None
        return next(
            (
                value
                for value in self._observation_section().observations
                if value.observation_id == identity
            ),
            None,
        )

    def _on_observation_selected(self, _event=None):
        self._show_observation_detail(self._selected_observation())

    def _show_observation_detail(self, observation):
        self.observation_detail.configure(state="normal")
        self.observation_detail.delete("1.0", "end")
        if observation is None:
            self.observation_detail.insert(
                "1.0",
                "Select a calculated observation to inspect its evidence.",
            )
        else:
            lines = [
                f"{observation.artist} — {observation.title}",
                f"Release ID: {observation.release_id}",
            ]
            if type(observation) is HotNowObservation:
                lines.extend(
                    (
                        f"Classification: {observation.sell_window}",
                        f"Opportunity: {observation.opportunity_score:.1f}",
                        f"Momentum: {observation.momentum_score:.1f}",
                        f"Demand: {observation.demand_score:.1f}",
                        f"Liquidity: {observation.liquidity_score:.1f}",
                        f"Value: {observation.value_score:.1f}",
                        f"Explanation: {observation.explanation or 'No explanation supplied.'}",
                    )
                )
            else:
                lines.extend(
                    (
                        f"Rank: {observation.rank}",
                        f"Hidden Gem score: {observation.hidden_gem_score:.1f}",
                        *observation.evidence,
                    )
                )
            evidence = (
                observation.evidence
                if type(observation) is HotNowObservation
                else observation.marketplace_evidence
            )
            if evidence is not None:
                lines.extend(
                    (
                        "",
                        f"Evidence observed: {evidence.observed_at.isoformat()}",
                        f"Wants: {self._optional_value(evidence.wants)}",
                        f"Copies for sale: {self._optional_value(evidence.copies_for_sale)}",
                        f"Lowest price: {self._money_value(evidence)}",
                    )
                )
            if observation.warnings:
                lines.extend(
                    (
                        "",
                        "Evidence warnings",
                        *(
                            f"• {warning.message}"
                            for warning in observation.warnings
                        ),
                    )
                )
            self.observation_detail.insert("1.0", "\n".join(lines))
        self.observation_detail.configure(state="disabled")
        self._set_observation_action_state(observation)

    @staticmethod
    def _optional_value(value):
        return "Unavailable" if value is None else f"{value:,}"

    @staticmethod
    def _money_value(evidence):
        if evidence.lowest_price is None:
            return "Unavailable"
        currency = f" {evidence.currency}" if evidence.currency else ""
        return f"{evidence.lowest_price}{currency}"

    def _set_observation_action_state(self, observation):
        for button in (
            self.add_observation_button,
            self.reopen_observation_button,
            self.open_queued_observation_button,
        ):
            button.state(["disabled"])
        if observation is None or self.collector_review_service is None:
            return
        membership = observation.queue_membership
        if not membership.is_queued:
            self.add_observation_button.state(["!disabled"])
        elif membership.status is WeekendReviewStatus.RESOLVED:
            self.reopen_observation_button.state(["!disabled"])
            self.open_queued_observation_button.state(["!disabled"])
        else:
            self.open_queued_observation_button.state(["!disabled"])

    def refresh_collector_review_observations(self):
        if self.collector_review_observations is None:
            self.current_observation_workspace = (
                WeekendObservationWorkspace.unavailable(
                    "Collector Review observations are unavailable."
                )
            )
        else:
            identity = self._selected_observation_identity()
            try:
                self.current_observation_workspace = (
                    self.collector_review_observations.workspace()
                )
            except Exception:
                self.current_observation_workspace = (
                    WeekendObservationWorkspace.unavailable(
                        "Collector Review observations are unavailable."
                    )
                )
            self._apply_hot_now_dashboard_state()
            self._render_observations(identity)

    def _add_selected_observation(self):
        observation = self._selected_observation()
        if observation is None or self.collector_review_service is None:
            return
        try:
            result = self.collector_review_service.add_from_observation(
                observation
            )
        except Exception:
            messagebox.showerror(
                "Queue unavailable",
                "The release could not be added to the Weekend Review Queue.",
            )
            return
        self.refresh_weekend_review_queue(
            preserve_queue_item_id=result.item.queue_item_id
        )
        self.refresh_collector_review_observations()

    def _reopen_selected_observation(self):
        observation = self._selected_observation()
        if (
            observation is None
            or observation.queue_membership.queue_item_id is None
            or self.collector_review_service is None
        ):
            return
        try:
            item = self.collector_review_service.get(
                observation.queue_membership.queue_item_id
            )
        except Exception:
            messagebox.showwarning(
                "Queue item unavailable",
                "The Weekend Review Queue item could not be loaded.",
            )
            return
        if item is None:
            messagebox.showwarning(
                "Queue item unavailable",
                "The Weekend Review Queue item no longer exists.",
            )
            self.refresh_collector_review_observations()
            return
        try:
            reopened = self.collector_review_service.reopen(
                item.queue_item_id,
                expected_updated_at=item.updated_at,
            )
        except (WeekendReviewConflictError, WeekendReviewItemNotFoundError):
            messagebox.showwarning(
                "Queue item changed",
                "The Weekend Review Queue item changed. Refresh and try again.",
            )
            return
        except WeekendReviewTransitionError:
            messagebox.showwarning(
                "Reopen unavailable",
                "Only a resolved Weekend Review Queue item can be reopened.",
            )
            return
        self.refresh_weekend_review_queue(
            preserve_queue_item_id=reopened.queue_item_id
        )
        self.refresh_collector_review_observations()

    def _open_selected_observation_queue_item(self):
        observation = self._selected_observation()
        if (
            observation is None
            or observation.queue_membership.queue_item_id is None
        ):
            return
        self._open_queue_item(observation.queue_membership.queue_item_id)

    def _queue_statuses(self):
        value = self.queue_filter_var.get()
        if value == "Resolved":
            return (WeekendReviewStatus.RESOLVED,)
        if value == "All":
            return None
        return (
            WeekendReviewStatus.TO_REVIEW,
            WeekendReviewStatus.REVIEWING,
        )

    def _change_queue_filter(self):
        if not self._confirm_unsaved_queue_note():
            self.queue_filter_var.set(self._last_queue_filter)
            return
        self._last_queue_filter = self.queue_filter_var.get()
        self.refresh_weekend_review_queue()

    def refresh_weekend_review_queue(self, preserve_queue_item_id=None):
        if self.collector_review_service is None:
            self.queue_summary_var.set("Weekend Review Queue is unavailable.")
            return
        if preserve_queue_item_id is None and self.current_queue_item is not None:
            preserve_queue_item_id = self.current_queue_item.queue_item_id
        try:
            items = self.collector_review_service.list_queue(
                self._queue_statuses()
            )
        except Exception:
            self.queue_summary_var.set("Weekend Review Queue is unavailable.")
            return
        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)
        for item in items:
            artist, title = self._release_display(item.release_id)
            self.queue_tree.insert(
                "",
                "end",
                iid=str(item.queue_item_id),
                values=(
                    artist,
                    title,
                    item.status.value.replace("_", " ").title(),
                    (
                        "Hot now"
                        if item.source_type is WeekendObservationSource.HOT_NOW
                        else "Hidden Gem"
                    ),
                ),
            )
        self.queue_summary_var.set(
            f"{len(items)} queue {'item' if len(items) == 1 else 'items'}."
        )
        if (
            preserve_queue_item_id is not None
            and self.queue_tree.exists(str(preserve_queue_item_id))
        ):
            self.queue_tree.selection_set(str(preserve_queue_item_id))
            self.queue_tree.see(str(preserve_queue_item_id))
        else:
            self._load_queue_item(None)

    def _release_display(self, release_id):
        for section in (
            self.current_observation_workspace.hot_now_section,
            self.current_observation_workspace.hidden_gems_section,
        ):
            observation = next(
                (
                    value
                    for value in section.observations
                    if value.release_id == release_id
                ),
                None,
            )
            if observation is not None:
                return observation.artist, observation.title
        return f"Release {release_id}", ""

    def _on_queue_selected(self, _event=None):
        selection = self.queue_tree.selection()
        if not selection:
            return
        queue_item_id = int(selection[0])
        if (
            self.current_queue_item is not None
            and queue_item_id != self.current_queue_item.queue_item_id
            and not self._confirm_unsaved_queue_note()
        ):
            self.queue_tree.selection_set(
                str(self.current_queue_item.queue_item_id)
            )
            return
        try:
            item = self.collector_review_service.get(queue_item_id)
        except Exception:
            item = None
        self._load_queue_item(item)

    def _load_queue_item(self, item):
        self.current_queue_item = item
        self._queue_note_loading = True
        self.queue_note.configure(state="normal")
        self.queue_note.delete("1.0", "end")
        if item is None:
            self.queue_detail_var.set("Select a queue item.")
            self.queue_note.configure(state="disabled")
            self._set_queue_controls_enabled(False)
        else:
            self.queue_note.insert("1.0", item.review_note)
            provenance = (
                item.source_marketplace_snapshot_id
                or "Legacy or unavailable Marketplace provenance"
            )
            self.queue_detail_var.set(
                "\n".join(
                    (
                        f"Release ID: {item.release_id}",
                        f"Status: {item.status.value.replace('_', ' ').title()}",
                        f"Added: {item.added_at.isoformat()}",
                        f"Source: {item.source_summary}",
                        f"Marketplace provenance: {provenance}",
                    )
                )
            )
            self._set_queue_controls_enabled(True)
            self.queue_status_button.configure(
                text=(
                    "Return to Review"
                    if item.status is WeekendReviewStatus.REVIEWING
                    else "Start Review"
                )
            )
            self.queue_status_button.state(
                ["disabled"]
                if item.status is WeekendReviewStatus.RESOLVED
                else ["!disabled"]
            )
            self.queue_resolve_button.configure(
                text=(
                    "Reopen"
                    if item.status is WeekendReviewStatus.RESOLVED
                    else "Resolve"
                )
            )
        self._queue_note_dirty = False
        self._queue_note_loading = False

    def _set_queue_controls_enabled(self, enabled):
        state = ["!disabled"] if enabled else ["disabled"]
        self.queue_note.configure(state="normal" if enabled else "disabled")
        for button in (
            self.queue_save_button,
            self.queue_status_button,
            self.queue_resolve_button,
            self.queue_remove_button,
            self.queue_decision_button,
        ):
            button.state(state)

    def _on_queue_note_edited(self, _event=None):
        if not self._queue_note_loading and self.current_queue_item is not None:
            self._queue_note_dirty = (
                self.queue_note.get("1.0", "end-1c")
                != self.current_queue_item.review_note
            )

    def _save_queue_note(self):
        item = self.current_queue_item
        if item is None or self.collector_review_service is None:
            return False
        try:
            persisted = self.collector_review_service.save_note(
                item.queue_item_id,
                self.queue_note.get("1.0", "end-1c"),
                expected_updated_at=item.updated_at,
            )
        except WeekendReviewItemNotFoundError:
            self.queue_detail_var.set(
                "This Weekend Review Queue item no longer exists. "
                "The unsaved note remains visible."
            )
            self._set_queue_controls_enabled(False)
            self.queue_note.configure(state="normal")
            return False
        except WeekendReviewConflictError:
            messagebox.showwarning(
                "Queue item changed",
                "The queue item changed after it was loaded. "
                "Your unsaved note remains available.",
            )
            return False
        except Exception:
            messagebox.showerror(
                "Save unavailable",
                "The Review note could not be saved. "
                "Your unsaved note remains available.",
            )
            return False
        self._load_queue_item(persisted)
        self.queue_tree.selection_set(str(persisted.queue_item_id))
        return True

    def _toggle_queue_status(self):
        item = self.current_queue_item
        if item is None or self.collector_review_service is None:
            return
        if self._queue_note_dirty and not self._save_queue_note():
            return
        target = (
            WeekendReviewStatus.TO_REVIEW
            if item.status is WeekendReviewStatus.REVIEWING
            else WeekendReviewStatus.REVIEWING
        )
        self._mutate_queue_item(
            lambda current: self.collector_review_service.set_active_status(
                current.queue_item_id,
                target,
                expected_updated_at=current.updated_at,
            )
        )

    def _resolve_or_reopen_queue_item(self):
        item = self.current_queue_item
        if item is None or self.collector_review_service is None:
            return
        if self._queue_note_dirty and not self._save_queue_note():
            return
        operation = (
            self.collector_review_service.reopen
            if item.status is WeekendReviewStatus.RESOLVED
            else self.collector_review_service.resolve
        )
        self._mutate_queue_item(
            lambda current: operation(
                current.queue_item_id,
                expected_updated_at=current.updated_at,
            )
        )

    def _mutate_queue_item(self, operation):
        item = self.current_queue_item
        if item is None:
            return
        try:
            updated = operation(item)
        except (WeekendReviewConflictError, WeekendReviewItemNotFoundError):
            messagebox.showwarning(
                "Queue item changed",
                "The Weekend Review Queue item changed. Refresh and try again.",
            )
            return
        except WeekendReviewTransitionError:
            messagebox.showwarning(
                "Status unavailable",
                "That Weekend Review Queue status change is not available.",
            )
            return
        except Exception:
            messagebox.showerror(
                "Queue unavailable",
                "The Weekend Review Queue item could not be updated.",
            )
            return
        self.refresh_weekend_review_queue(
            preserve_queue_item_id=updated.queue_item_id
        )
        self.refresh_collector_review_observations()

    def _remove_queue_item(self):
        item = self.current_queue_item
        if item is None or self.collector_review_service is None:
            return
        artist, title = self._release_display(item.release_id)
        if not messagebox.askyesno(
            "Remove queue item",
            (
                f"Remove {artist} — {title or f'Release {item.release_id}'} "
                "from the Weekend Review Queue?\n\n"
                "The Collection Decision and evidence will not be deleted."
            ),
        ):
            return
        try:
            self.collector_review_service.remove(
                item.queue_item_id,
                expected_updated_at=item.updated_at,
            )
        except WeekendReviewItemNotFoundError:
            messagebox.showwarning(
                "Queue item unavailable",
                "The Weekend Review Queue item no longer exists.",
            )
        except WeekendReviewConflictError:
            messagebox.showwarning(
                "Queue item changed",
                "The Weekend Review Queue item changed. Refresh and try again.",
            )
            return
        except Exception:
            messagebox.showerror(
                "Remove unavailable",
                "The Weekend Review Queue item could not be removed.",
            )
            return
        self._load_queue_item(None)
        self.refresh_weekend_review_queue()
        self.refresh_collector_review_observations()

    def _open_queue_collection_decision(self):
        if self.current_queue_item is not None:
            self.open_collection_decision(self.current_queue_item.release_id)

    def _open_queue_item(self, queue_item_id):
        if self.collector_review_service is None:
            return
        try:
            item = self.collector_review_service.get(queue_item_id)
        except Exception:
            messagebox.showwarning(
                "Queue item unavailable",
                "The Weekend Review Queue item could not be loaded.",
            )
            return
        if item is None:
            messagebox.showwarning(
                "Queue item unavailable",
                "The Weekend Review Queue item no longer exists.",
            )
            return
        self.queue_filter_var.set(
            "Resolved"
            if item.status is WeekendReviewStatus.RESOLVED
            else "Active"
        )
        self.tabs.select(self.review_tab)
        self.collection_review_tabs.select(self.queue_tab)
        self.refresh_weekend_review_queue(
            preserve_queue_item_id=queue_item_id
        )

    def open_collection_review_observations(self, source):
        if type(source) is not WeekendObservationSource:
            raise TypeError("source must be a WeekendObservationSource.")
        section = (
            self.current_observation_workspace.hot_now_section
            if source is WeekendObservationSource.HOT_NOW
            else self.current_observation_workspace.hidden_gems_section
        )
        if section.status is ObservationSectionStatus.UNAVAILABLE:
            return
        self.observation_source_var.set(
            "Hot now"
            if source is WeekendObservationSource.HOT_NOW
            else "Hidden Gems"
        )
        self.tabs.select(self.review_tab)
        self.collection_review_tabs.select(self.observations_tab)
        self._render_observations()

    def open_collection_decision(self, release_id):
        self.tabs.select(self.review_tab)
        self.collection_review_tabs.select(self.decisions_tab)
        self.load_table()
        iid = str(release_id)
        if not self.tree.exists(iid):
            messagebox.showwarning(
                "Collection Decision unavailable",
                "The release is not available in Collection Decisions.",
            )
            return
        self.tree.selection_set(iid)
        self.tree.see(iid)
        self.edit_selected()

    def _confirm_unsaved_queue_note(self):
        if not self._queue_note_dirty:
            return True
        response = messagebox.askyesnocancel(
            "Unsaved Review note",
            (
                "Save the current Review note before continuing?\n\n"
                "Yes: Save\nNo: Discard\nCancel: Stay here"
            ),
        )
        if response is None:
            return False
        if response:
            return self._save_queue_note()
        self._queue_note_dirty = False
        return True

    def _on_collection_review_destination_changed(self, _event=None):
        if self._review_tab_change_guard:
            return
        selected = self.collection_review_tabs.nametowidget(
            self.collection_review_tabs.select()
        )
        previous = getattr(
            self,
            "_last_collection_review_destination",
            selected,
        )
        if (
            previous is self.queue_tab
            and selected is not self.queue_tab
            and not self._confirm_unsaved_queue_note()
        ):
            self._review_tab_change_guard = True
            self.collection_review_tabs.select(self.queue_tab)
            self._review_tab_change_guard = False
            return
        self._last_collection_review_destination = selected
        if selected is self.queue_tab and not self._queue_note_dirty:
            self.refresh_weekend_review_queue()

    def _build_project_workspace(self):
        if self.project_workspace_controller is None:
            ttk.Label(
                self.project_tab, text="Project Workspace is unavailable."
            ).pack(anchor="w")
            return
        rendered = self.project_workspace_controller.open()
        ttk.Label(
            self.project_tab, text=rendered.title, font=("Helvetica", 22, "bold")
        ).pack(anchor="w", pady=(0, 14))
        for section in rendered.sections:
            frame = ttk.LabelFrame(self.project_tab, text=section.title, padding=14)
            frame.pack(fill="x", pady=6)
            ttk.Label(
                frame, text=section.body, wraplength=1000, justify="left"
            ).pack(anchor="w")
            if section.title == "Quick Actions":
                actions = ttk.Frame(frame)
                actions.pack(anchor="w", pady=(10, 0))
                for action in rendered.actions:
                    button = ttk.Button(
                        actions,
                        text=action.label,
                        command=lambda target=action.target: self._open_project_target(target),
                    )
                    if not action.enabled:
                        button.state(["disabled"])
                    button.pack(side="left", padx=(0, 8))

    def _open_project_target(self, target):
        if target is ProjectWorkspaceNavigationTarget.DASHBOARD:
            self.tabs.select(self.dashboard_tab)
        elif target is ProjectWorkspaceNavigationTarget.PORTFOLIO:
            self.open_portfolio_overview()

    def import_csv(self):
        if self._collector_run_active:
            messagebox.showwarning(
                "Import unavailable",
                "Collection import is unavailable while Collector Run is active.",
            )
            return
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
        if self._collector_run_active:
            return
        if self.collector_run_service is None:
            messagebox.showerror(
                "Refresh unavailable",
                "The Collector Run service is unavailable.",
            )
            return
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
        self._collector_run_active = True
        self.refresh_discogs_button.configure(state="disabled")
        self.import_csv_button.configure(state="disabled")
        self.progress.configure(value=0)
        self.status_var.set("Starting Discogs refresh…")
        worker = threading.Thread(
            target=self.refresh_market_data,
            args=(token,),
            daemon=True,
        )
        try:
            worker.start()
        except Exception as exc:
            self._restore_refresh_controls()
            self.status_var.set("Refresh failed")
            messagebox.showerror(
                "Refresh failed",
                "Collector Run could not be started "
                f"({type(exc).__name__}).",
            )

    def refresh_market_data(self, token):
        try:
            result = self.collector_run_service.run(
                token,
                lambda progress: self.after(
                    0, self.update_refresh_progress, progress
                ),
            )
        except CollectorRunUnavailableError as exc:
            self.after(0, self.show_refresh_unavailable, str(exc))
        except CollectorRunExecutionError as exc:
            self.after(0, self.show_refresh_error, str(exc))
        except Exception as exc:
            self.after(
                0,
                self.show_refresh_error,
                f"Collector Run failed unexpectedly ({type(exc).__name__}).",
            )
        else:
            self.after(0, self.finish_refresh, result)

    def update_refresh_progress(
        self,
        progress: CollectorRunProgress,
    ):
        self.progress.configure(
            maximum=progress.total_releases,
            value=progress.attempted_releases,
        )
        self.status_var.set(
            f"Refreshing {progress.attempted_releases:,}/"
            f"{progress.total_releases:,} "
            f"— successful {progress.successful_releases:,}, "
            f"errors {progress.failed_releases:,}"
        )

    def finish_refresh(self, result: CollectorRunResult):
        succeeded = result.successful_releases
        failed = result.failed_releases
        self._restore_refresh_controls()
        if result.status is CollectorRunStatus.FAILED:
            self.status_var.set(
                f"Refresh failed — 0 successful, {failed:,} errors"
            )
            messagebox.showerror(
                "Refresh failed",
                self.status_var.get(),
            )
            return
        self.status_var.set(
            f"Refresh complete — {succeeded:,} successful, "
            f"{failed:,} errors"
        )
        self.refresh_dashboard()
        self.load_table()
        if result.status is CollectorRunStatus.PARTIAL:
            messagebox.showwarning(
                "Refresh partially complete",
                self.status_var.get(),
            )
        else:
            messagebox.showinfo(
                "Refresh complete",
                self.status_var.get(),
            )

    def show_refresh_error(self, error_message):
        self._restore_refresh_controls()
        self.status_var.set("Refresh failed")
        messagebox.showerror(
            "Refresh failed",
            f"An unexpected error occurred:\n\n{error_message}",
        )

    def show_refresh_unavailable(self, error_message):
        self._restore_refresh_controls()
        self.status_var.set("Refresh unavailable")
        messagebox.showwarning("Refresh unavailable", error_message)

    def _restore_refresh_controls(self):
        self._collector_run_active = False
        self.refresh_discogs_button.configure(state="normal")
        self.import_csv_button.configure(state="normal")

    def refresh_dashboard(self):
        row = self.db.dashboard()
        for key, widget in self.kpis.items():
            if key != "hot_now":
                widget.configure(text=f"{int(row[key] or 0):,}")
        if self.collector_review_observations is None:
            self.current_observation_workspace = (
                WeekendObservationWorkspace.unavailable(
                    "Collector Review observations are unavailable."
                )
            )
        else:
            try:
                self.current_observation_workspace = (
                    self.collector_review_observations.workspace()
                )
            except Exception:
                self.current_observation_workspace = (
                    WeekendObservationWorkspace.unavailable(
                        "Collector Review observations are unavailable."
                    )
                )
        self._apply_hot_now_dashboard_state()
        self._render_observations()
        self.refresh_intelligence_dashboard()

    def _apply_hot_now_dashboard_state(self):
        section = self.current_observation_workspace.hot_now_section
        if section.status is ObservationSectionStatus.AVAILABLE:
            self.kpis["hot_now"].configure(
                text=f"{len(self.current_observation_workspace.hot_now):,}"
            )
            self.hot_now_kpi_button.state(["!disabled"])
        else:
            self.kpis["hot_now"].configure(text="—")
            self.hot_now_kpi_button.state(["disabled"])

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
        self._refresh_dashboard_command_center()
        self._update_collection_explorer_navigation()
        self._update_hidden_gems_navigation()

    def _refresh_dashboard_command_center(self):
        if self.dashboard_command_center_controller is None:
            return
        try:
            rendered = self.dashboard_command_center_controller.open(
                self.current_dashboard_homepage,
                portfolio_results=(
                    self.current_portfolio_overview_result,
                    self.current_portfolio_distribution_result,
                    self.current_portfolio_concentration_result,
                    self.current_portfolio_opportunity_alignment_result,
                ),
                marketplace_queue=self.current_marketplace_workspace_queue,
                history_observations=self.current_history_snapshot_view_models,
                history_changes=self.current_history_change_view_models,
                history_trends=self.current_history_trend_view_models,
            )
        except Exception as exc:
            for body, _ in self.dashboard_command_vars.values():
                body.set(f"Workspace summary is unavailable: {type(exc).__name__}.")
            return
        for card in rendered.cards:
            body, actions = self.dashboard_command_vars[card.title]
            body.set(card.body)
            for child in actions.winfo_children():
                child.destroy()
            for action in card.actions:
                ttk.Button(
                    actions,
                    text=action.label,
                    command=lambda target=action.target: self._open_dashboard_target(target),
                ).pack(side="left", padx=(0, 6))

    def _open_dashboard_target(self, target):
        actions = {
            DashboardNavigationTarget.PORTFOLIO: lambda: self.open_portfolio_overview(),
            DashboardNavigationTarget.PORTFOLIO_OPPORTUNITY_ALIGNMENT: lambda: self.open_portfolio_overview(PortfolioWorkspaceDestination.OPPORTUNITY_ALIGNMENT),
            DashboardNavigationTarget.PORTFOLIO_HISTORY: lambda: self.open_portfolio_overview(PortfolioWorkspaceDestination.HISTORY),
            DashboardNavigationTarget.PORTFOLIO_RESEARCH: lambda: self.open_portfolio_overview(PortfolioWorkspaceDestination.RESEARCH),
            DashboardNavigationTarget.COLLECTION_EXPLORER: self.open_intelligence_explorer,
            DashboardNavigationTarget.HISTORICAL_INTELLIGENCE: self.open_intelligence_change_analysis,
            DashboardNavigationTarget.MARKETPLACE_WORKSPACE: self.open_marketplace_workspace,
        }
        actions[target]()

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
        hidden_section = self.current_observation_workspace.hidden_gems_section
        if hidden_section.status in {
            ObservationSectionStatus.AVAILABLE,
            ObservationSectionStatus.NO_HISTORY,
        }:
            self.hidden_gems_observations_button.pack(
                anchor="w",
                pady=(6, 0),
            )
        else:
            self.hidden_gems_observations_button.pack_forget()

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

    def open_portfolio_overview(self, destination=None):
        """Open the separate Portfolio experience from a supplied completed result."""
        if self.portfolio_workspace_controller is None:
            messagebox.showerror("Portfolio unavailable", "Portfolio is not configured.")
            return
        try:
            rendered = self.portfolio_workspace_controller.open(
                self.current_portfolio_overview_result,
                self.current_portfolio_distribution_result,
                self.current_portfolio_concentration_result,
                self.current_portfolio_opportunity_alignment_result,
            )
            if destination is not None:
                rendered = self.portfolio_workspace_controller.navigate(
                    rendered.state, destination
                )
        except Exception as exc:
            messagebox.showerror(
                "Portfolio unavailable",
                f"Portfolio could not be displayed:\n\n{exc}",
            )
            return
        window = tk.Toplevel(self)
        window.title(rendered.title)
        window.geometry("1050x760")
        window.minsize(760, 540)
        window.transient(self)
        workspace = ttk.Frame(window, padding=12)
        workspace.pack(fill="both", expand=True)
        navigation = tk.Listbox(workspace, exportselection=False, width=24)
        navigation.pack(side="left", fill="y", padx=(0, 12))
        content = ttk.Frame(workspace)
        content.pack(side="left", fill="both", expand=True)
        heading = ttk.Label(content, text=rendered.heading, font=("Helvetica", 16, "bold"))
        heading.pack(anchor="w", pady=(0, 8))
        text = tk.Text(content, wrap="word", padx=10, pady=10)
        scrollbar = ttk.Scrollbar(content, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        for item in rendered.navigation:
            navigation.insert("end", item.title)

        current = rendered

        def show(value):
            nonlocal current
            current = value
            heading.configure(text=value.heading)
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.insert("1.0", value.body)
            text.configure(state="disabled")

        def select_destination(event=None):
            selection = navigation.curselection()
            if not selection:
                return
            destination = current.navigation[selection[0]].destination
            show(self.portfolio_workspace_controller.navigate(current.state, destination))

        navigation.bind("<<ListboxSelect>>", select_destination)
        selected_index = next(
            index for index, item in enumerate(rendered.navigation)
            if item.destination is rendered.current_destination
        )
        navigation.selection_set(selected_index)
        navigation.activate(selected_index)
        show(rendered)
        ttk.Button(window, text="Close", command=window.destroy).pack(pady=(0, 12))

    def open_intelligence_change_analysis(self):
        """Render already-produced Change and Trend Analysis results."""
        if self.intelligence_change_analysis_controller is None:
            messagebox.showerror(
                "Historical Intelligence unavailable",
                "Intelligence Change Analysis is not configured.",
            )
            return
        try:
            change_rendered = self.intelligence_change_analysis_controller.open(
                self.current_intelligence_change_analysis_result
            )
            trend_rendered = (
                self.intelligence_trend_analysis_controller.open(
                    self.current_intelligence_trend_analysis_result
                )
                if self.intelligence_trend_analysis_controller is not None
                else None
            )
            explorer_rendered = (
                self.history_explorer_controller.open(
                    self.current_history_snapshot_view_models,
                    self.current_history_change_view_models,
                    self.current_history_trend_view_models,
                )
                if self.history_explorer_controller is not None
                else None
            )
            insights_rendered = (
                self.intelligence_insights_controller.open(
                    self.current_intelligence_insight_collections
                )
                if self.intelligence_insights_controller is not None
                else None
            )
        except Exception as exc:
            messagebox.showerror(
                "Historical Intelligence unavailable",
                f"Intelligence Change Analysis could not be displayed:\n\n{exc}",
            )
            return
        window = tk.Toplevel(self)
        window.title("Historical Intelligence")
        window.geometry("1050x760")
        window.minsize(760, 540)
        window.transient(self)
        notebook = ttk.Notebook(window)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)
        destinations = (
            ("Change Analysis", change_rendered),
            ("Trend Analysis", trend_rendered),
            ("History Explorer", explorer_rendered),
            ("Intelligence Insights", insights_rendered),
        )
        for title, rendered in destinations:
            frame = ttk.Frame(notebook, padding=12)
            notebook.add(frame, text=title)
            text = tk.Text(frame, wrap="word", padx=10, pady=10)
            body = (
                "\n\n".join(
                    f"{section.title}\n{section.body}"
                    for section in rendered.sections
                )
                if rendered is not None and rendered.sections
                else getattr(rendered, "summary", "") if rendered is not None
                else f"{title} is not configured."
            )
            text.insert("1.0", body)
            text.configure(state="disabled")
            text.pack(fill="both", expand=True)
        ttk.Button(window, text="Close", command=window.destroy).pack(pady=(0, 12))

    def open_marketplace_workspace(self):
        """Render one already-supplied Marketplace workflow queue."""
        if self.marketplace_workspace_controller is None:
            messagebox.showerror("Marketplace Workspace unavailable", "Marketplace Workspace is not configured.")
            return
        try:
            rendered = self.marketplace_workspace_controller.open(
                self.current_marketplace_workspace_queue
            )
        except Exception as exc:
            messagebox.showerror(
                "Marketplace Workspace unavailable",
                f"Marketplace Workspace could not be displayed:\n\n{exc}",
            )
            return
        window = tk.Toplevel(self)
        window.title(rendered.title)
        window.geometry("1120x780")
        window.minsize(800, 560)
        window.transient(self)
        notebook = ttk.Notebook(window)
        notebook.pack(fill="both", expand=True, padx=12, pady=12)
        for section in rendered.sections:
            frame = ttk.Frame(notebook, padding=12)
            notebook.add(frame, text=section.title)
            text = tk.Text(frame, wrap="word", padx=10, pady=10)
            text.insert("1.0", section.body)
            text.configure(state="disabled")
            text.pack(fill="both", expand=True)
        ttk.Button(window, text="Close", command=window.destroy).pack(pady=(0, 12))

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
        if not self._confirm_unsaved_queue_note():
            return
        self.db.close()
        self.destroy()

if __name__ == "__main__":
    App().mainloop()
