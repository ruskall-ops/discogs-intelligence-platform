
from __future__ import annotations
import threading
from datetime import datetime, timezone
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
from dip.app.database_backup import DatabaseBackupValidationError
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
from dip.collection_decision_vocabulary import (
    CANONICAL_DECISIONS,
    ReviewFilterChoice,
    ReviewFilterChoiceKind,
    ReviewFilterField,
    review_filter_choices,
)
from dip.composition import build_desktop_application_dependencies
from dip.config import SETTINGS
from dip.experience.reporting import ReportingService, render_markdown
from dip.experience.collector_review_presentation import (
    COLLECTION_DECISION_COLUMNS,
    DisabledActionReason,
    ReviewDetailSectionKind,
    decision_row_values,
    observation_detail_sections,
)
from dip.experience.dashboard import (
    DashboardHomepageViewModel,
    DashboardNavigationTarget,
)
from dip.experience.portfolio_workspace import PortfolioWorkspaceDestination
from dip.experience.explorer import (
    CollectionExplorerDestination,
    ENABLED_EXPLORER_DESTINATIONS,
    UNAVAILABLE_EXPLORER_DESTINATIONS,
    UNAVAILABLE_EXPLORER_EXPLANATION,
)
from dip.experience.project_workspace import ProjectWorkspaceNavigationTarget
from dip.experience.desktop.homepage_renderer import (
    DesktopDashboardHomepageRenderer,
)
from dip.experience.results_presentation import (
    PresentationStateKind,
    presentation_state_copy,
)
from dip.exports import export_excel
from dip.session import (
    CollectionReviewDestination,
    DecisionPriorityFilter,
    DecisionStateFilter,
    DesktopSessionCapture,
    MAX_COORDINATE,
    MAX_WINDOW_DIMENSION,
    MIN_COORDINATE,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    QueueStatusFilter,
    SessionValidationError,
    TopLevelDestination,
)


_SOURCE_LABELS = {
    WeekendObservationSource.HOT_NOW: "Hot now",
    WeekendObservationSource.HIDDEN_GEM: "Hidden Gems",
}
_QUEUE_FILTER_LABELS = {
    QueueStatusFilter.ACTIVE: "Active",
    QueueStatusFilter.RESOLVED: "Resolved",
    QueueStatusFilter.ALL: "All",
}
_PRIORITY_FILTER_LABELS = {
    DecisionPriorityFilter.ALL: "All",
    DecisionPriorityFilter.HIGH_PRIORITY_REVIEW: "High-priority review",
    DecisionPriorityFilter.WORTH_REVIEWING: "Worth reviewing",
    DecisionPriorityFilter.POSSIBLE_CANDIDATE: "Possible candidate",
    DecisionPriorityFilter.LOW_PRIORITY: "Low priority",
    DecisionPriorityFilter.NOT_SCORED: "Not scored",
}
_DECISION_FILTER_LABELS = {
    DecisionStateFilter.ALL: "All",
    DecisionStateFilter.REVIEW: "Review",
    DecisionStateFilter.KEEP: "Keep",
    DecisionStateFilter.LIST_FOR_SALE: "List for sale",
    DecisionStateFilter.MAYBE: "Maybe",
    DecisionStateFilter.IGNORE: "Ignore",
}
_UNAVAILABLE_EXPLORER_DESTINATIONS = frozenset(UNAVAILABLE_EXPLORER_DESTINATIONS)
_STALE_MARKETPLACE_COPY = (
    "Newer history is available\n"
    "These cached results predate the latest completed Collector Run."
)
_MARKETPLACE_REFRESH_EXPLANATION = (
    "Recalculate Price and Supply Changes from saved Marketplace history. "
    "No Discogs request is made."
)
_MARKETPLACE_REFRESH_BLOCKED = (
    "Marketplace refresh is unavailable while Collector Run is active."
)


def _show_message_safely(show_message, title, body):
    try:
        show_message(title, body)
    except Exception:
        pass


def _show_import_display_refresh_failure():
    _show_message_safely(
        messagebox.showerror,
        "Collection imported",
        (
            "The collection was imported, but the displayed data could not be "
            "refreshed. Reopen the view or application; do not import the file "
            "again."
        ),
    )


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        dependencies = build_desktop_application_dependencies()
        self.title(SETTINGS.application_name)
        self.geometry(

    f"{SETTINGS.window_width}x{SETTINGS.window_height}"

)
        self.minsize(800, 560)
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
        self.project_management = getattr(
            dependencies, "project_management", None
        )
        self.session_restoration_service = getattr(
            dependencies, "session_restoration", None
        )
        self.database_backup_service = getattr(
            dependencies, "database_backup", None
        )
        self._collector_run_active = False
        set_refresh_allowed = getattr(
            self.collection_explorer_controller,
            "set_marketplace_refresh_allowed",
            None,
        )
        if set_refresh_allowed is not None:
            set_refresh_allowed(lambda: not self._collector_run_active)
        self._marketplace_explorer_handles = {}
        self._database_backup_active = False
        self._session_restoring = True
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
        self._register_close_handlers()

        self.status_var = tk.StringVar(value="Ready")
        self.search_var = tk.StringVar()
        self.priority_var = tk.StringVar(value="All")
        self.decision_filter_var = tk.StringVar(value="All")
        self._priority_filter_choices = review_filter_choices(
            ReviewFilterField.PRIORITY, ()
        )
        self._decision_filter_choices = review_filter_choices(
            ReviewFilterField.DECISION, ()
        )
        self._last_normal_geometry = (
            SETTINGS.window_width,
            SETTINGS.window_height,
            0,
            0,
        )

        self.build_ui()
        self.bind("<Configure>", self._record_normal_geometry)
        self._restore_session_and_load()

    def _build_main_toolbar(self):
        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")

        primary_toolbar = ttk.Frame(toolbar)
        primary_toolbar.pack(fill="x")

        self.import_csv_button = ttk.Button(
            primary_toolbar,
            text="Import Collection CSV",
            command=self.import_csv,
        )
        self.import_csv_button.grid(row=0, column=0, padx=3, sticky="ew")
        self.refresh_discogs_button = ttk.Button(
            primary_toolbar,
            text="Refresh Discogs Data",
            command=self.start_refresh,
        )
        self.refresh_discogs_button.grid(row=0, column=1, padx=3, sticky="ew")
        self.database_backup_button = ttk.Button(
            primary_toolbar,
            text="Back Up Database…",
            command=self.back_up_database,
        )
        self.database_backup_button.grid(row=0, column=2, padx=3, sticky="ew")
        self.export_excel_button = ttk.Button(primary_toolbar, text="Export Excel", command=self.export_report)
        self.export_excel_button.grid(row=1, column=0, padx=3, pady=(5, 0), sticky="ew")
        self.export_intelligence_button = ttk.Button(primary_toolbar, text="Export Intelligence Report", command=self.export_intelligence_report)
        self.export_intelligence_button.grid(row=1, column=1, padx=3, pady=(5, 0), sticky="ew")
        self.refresh_view_button = ttk.Button(primary_toolbar, text="Refresh View", command=self.load_table)
        self.refresh_view_button.grid(row=1, column=2, padx=3, pady=(5, 0), sticky="ew")
        for column in range(3):
            primary_toolbar.columnconfigure(column, weight=1)

        secondary_toolbar = ttk.Frame(toolbar)
        secondary_toolbar.pack(fill="x", pady=(6, 0))
        self.portfolio_button = ttk.Button(
            secondary_toolbar, text="Portfolio", command=self.open_portfolio_overview
        )
        self.portfolio_button.state(["disabled"])
        self.portfolio_button.grid(row=0, column=0, padx=3, sticky="ew")
        self.historical_intelligence_button = ttk.Button(
            secondary_toolbar,
            text="Historical Intelligence",
            command=self.open_intelligence_change_analysis,
        )
        self.historical_intelligence_button.state(["disabled"])
        self.historical_intelligence_button.grid(row=0, column=1, padx=3, sticky="ew")
        self.marketplace_workspace_button = ttk.Button(
            secondary_toolbar,
            text="Marketplace",
            command=self.open_marketplace_workspace,
        )
        self.marketplace_workspace_button.state(["disabled"])
        self.marketplace_workspace_button.grid(row=0, column=2, padx=3, sticky="ew")
        ttk.Label(
            secondary_toolbar,
            text="Portfolio, Historical Intelligence, and Marketplace Workspace: "
            "Not available in this release",
        ).grid(row=1, column=0, columnspan=3, padx=3, pady=(4, 0), sticky="w")

        self.progress = ttk.Progressbar(secondary_toolbar, length=220, mode="determinate")
        self.progress.grid(row=2, column=0, padx=3, pady=(4, 0), sticky="ew")
        ttk.Label(secondary_toolbar, textvariable=self.status_var).grid(row=2, column=1, columnspan=2, padx=8, pady=(4, 0), sticky="e")
        for column in range(3):
            secondary_toolbar.columnconfigure(column, weight=1)

        return toolbar

    def build_ui(self):
        self._build_main_toolbar()

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)

        self.project_tab = ttk.Frame(self.tabs, padding=18)
        self.dashboard_tab = ttk.Frame(self.tabs)
        self.review_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.project_tab, text="Project")
        self.tabs.add(self.dashboard_tab, text="Dashboard")
        self.tabs.add(self.review_tab, text="Collection Review")
        self._build_project_workspace()

        dashboard_canvas = tk.Canvas(
            self.dashboard_tab,
            highlightthickness=0,
            takefocus=True,
        )
        dashboard_scroll = ttk.Scrollbar(
            self.dashboard_tab,
            orient="vertical",
            command=dashboard_canvas.yview,
        )
        dashboard_canvas.configure(yscrollcommand=dashboard_scroll.set)
        dashboard_scroll.pack(side="right", fill="y")
        dashboard_canvas.pack(side="left", fill="both", expand=True)
        dashboard_content = ttk.Frame(dashboard_canvas, padding=12)
        dashboard_window = dashboard_canvas.create_window(
            (0, 0), window=dashboard_content, anchor="nw"
        )
        self.dashboard_canvas = dashboard_canvas
        self.dashboard_content = dashboard_content
        self.dashboard_window = dashboard_window
        dashboard_content.bind(
            "<Configure>",
            lambda _event: dashboard_canvas.configure(
                scrollregion=dashboard_canvas.bbox("all")
            ),
        )
        dashboard_canvas.bind(
            "<Configure>",
            self._layout_dashboard_cards,
        )
        for column in range(6):
            dashboard_content.columnconfigure(column, weight=1)

        self.kpis = {}

        collection_labels = [
            ("unique_releases", "Unique releases"),
            ("owned_copies", "Owned copies"),
            ("protected", "Protected / Keep"),
        ]
        current_collection = ttk.LabelFrame(
            dashboard_content,
            text="Current collection",
            padding=10,
        )
        current_collection.grid(
            row=0, column=0, columnspan=6, padx=8, pady=8, sticky="ew"
        )
        self.dashboard_collection_heading_label = ttk.Label(
            current_collection,
            text="Current Collection · single-collection data",
            justify="left",
        )
        self.dashboard_collection_heading_label.grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        self.dashboard_collection_state_var = tk.StringVar(value="Loading collection facts…")
        self.dashboard_collection_state_label = ttk.Label(
            current_collection,
            textvariable=self.dashboard_collection_state_var,
            wraplength=700,
            justify="left",
        )
        self.dashboard_collection_state_label.grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(2, 6)
        )
        self.dashboard_collection_state_label.bind(
            "<Configure>", self._wrap_dashboard_label
        )

        for index, (key, label) in enumerate(collection_labels):
            box = ttk.LabelFrame(
                current_collection,
                text=label,
                padding=8,
            )
            box.grid(
                row=2,
                column=index % 3,
                padx=4,
                pady=4,
                sticky="nsew",
            )

            value = ttk.Label(
                box,
                text="0",
                font=("Helvetica", 24, "bold"),
            )
            value.pack()

            self.kpis[key] = value
            current_collection.columnconfigure(index % 3, weight=1)
        self.dashboard_collection_persistence_label = ttk.Label(
            current_collection,
            text=(
            "SQLite is now the source of truth. Collection details, market snapshots, "
            "scores, decisions and notes persist between runs. Excel is generated only "
            "when you want an export."
            ),
            wraplength=700,
            justify="left",
        )
        self.dashboard_collection_persistence_label.grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(6, 0)
        )
        self.dashboard_collection_persistence_label.bind(
            "<Configure>", self._wrap_dashboard_label
        )

        latest_intelligence = ttk.LabelFrame(
            dashboard_content,
            text="Latest completed intelligence",
            padding=10,
        )
        latest_intelligence.grid(
            row=1, column=0, columnspan=6, padx=8, pady=8, sticky="ew"
        )
        self.dashboard_intelligence_state_var = tk.StringVar(
            value="Intelligence is loading…"
        )
        self.dashboard_intelligence_state_label = ttk.Label(
            latest_intelligence,
            textvariable=self.dashboard_intelligence_state_var,
            wraplength=700,
            justify="left",
        )
        self.dashboard_intelligence_state_label.grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 6)
        )
        self.dashboard_intelligence_state_label.bind(
            "<Configure>", self._wrap_dashboard_label
        )
        self.dashboard_homepage_vars = {}
        homepage_sections = (
            ("collection_overview", "Execution overview", 1, 0, 3),
            ("latest_execution", "Execution provenance", 1, 3, 3),
            ("collection_health", "Collection Health", 2, 0, 3),
            ("hidden_gems", "Hidden Gems", 2, 3, 3),
            ("what_changed", "What Changed", 3, 0, 6),
        )
        self.dashboard_homepage_cards = []
        self.dashboard_card_preferred_wraplengths = {}
        for section_id, title, row, column, columnspan in homepage_sections:
            card = ttk.LabelFrame(latest_intelligence, text=title, padding=14)
            card.grid(
                row=row,
                column=column,
                columnspan=columnspan,
                padx=8,
                pady=8,
                sticky="nsew",
            )
            body = tk.StringVar(value="Intelligence is loading…")
            label = ttk.Label(
                card,
                textvariable=body,
                wraplength=350,
                justify="left",
            )
            label.pack(anchor="nw", fill="both", expand=True)
            label.bind("<Configure>", self._wrap_dashboard_label)
            self.dashboard_homepage_cards.append((card, label))
            self.dashboard_card_preferred_wraplengths[label] = 350
            self.dashboard_homepage_vars[section_id] = body
        for column in range(6):
            latest_intelligence.columnconfigure(column, weight=1)
        available = ttk.LabelFrame(dashboard_content, text="Available destinations", padding=10)
        available.grid(row=2, column=0, columnspan=6, padx=8, pady=8, sticky="ew")
        available_actions = ttk.Frame(available)
        available_actions.pack(fill="x")
        self.collection_explorer_button = ttk.Button(available_actions, text="Open Collection Explorer", command=self.open_intelligence_explorer)
        self.collection_explorer_button.grid(row=0, column=0, padx=(0, 6), pady=(0, 6), sticky="w")
        self.dashboard_health_button = ttk.Button(available_actions, text="Open Collection Health", command=self.open_collection_health)
        self.dashboard_health_button.grid(row=0, column=1, padx=(0, 6), pady=(0, 6), sticky="w")
        self.hot_now_button = ttk.Button(
            available_actions,
            text="Review Hot Now",
            command=lambda: self.open_collection_review_observations(
                WeekendObservationSource.HOT_NOW
            ),
        )
        self.hot_now_button.grid(row=1, column=0, padx=(0, 6), sticky="w")
        self.hidden_gems_button = ttk.Button(available_actions, text="Open Hidden Gems", command=self.open_hidden_gems)
        self.hidden_gems_observations_button = ttk.Button(
            available_actions,
            text="Review in Observations",
            command=lambda: self.open_collection_review_observations(
                WeekendObservationSource.HIDDEN_GEM
            ),
        )
        self.dashboard_available_copy_label = ttk.Label(
            available,
            text="Price Changes and Supply Changes are available through Collection Explorer.",
            wraplength=700,
            justify="left",
        )
        self.dashboard_available_copy_label.pack(
            anchor="w", fill="x", pady=(8, 0)
        )
        self.dashboard_available_copy_label.bind(
            "<Configure>", self._wrap_dashboard_label
        )
        self.dashboard_command_vars = {}
        command_cards = (
            ("Portfolio Summary", 7, 0),
            ("Opportunity Highlights", 7, 3),
            ("Historical Changes", 8, 0),
            ("Marketplace Highlights", 8, 3),
            ("Research Summary", 9, 0),
        )
        unavailable = ttk.LabelFrame(dashboard_content, text="Unavailable destinations", padding=10)
        unavailable.grid(row=3, column=0, columnspan=6, padx=8, pady=8, sticky="ew")
        self.dashboard_command_cards = []
        for title, row, column in command_cards:
            card = ttk.LabelFrame(unavailable, text=title, padding=14)
            card.grid(row=row - 7, column=column, columnspan=3, padx=8, pady=8, sticky="nsew")
            body = tk.StringVar(value="Workspace summary is loading…")
            label = ttk.Label(
                card, textvariable=body, wraplength=350, justify="left"
            )
            label.pack(anchor="nw", fill="both", expand=True)
            label.bind("<Configure>", self._wrap_dashboard_label)
            actions = ttk.Frame(card)
            actions.pack(anchor="w", fill="x", pady=(10, 0))
            self.dashboard_command_cards.append((card, label))
            self.dashboard_card_preferred_wraplengths[label] = 350
            self.dashboard_command_vars[title] = (body, actions)
        for column in range(6):
            unavailable.columnconfigure(column, weight=1)
        self.dashboard_primary_sections = (
            current_collection, latest_intelligence, available, unavailable
        )
        self.dashboard_card_sections = (latest_intelligence, unavailable)
        self._dashboard_card_layout = None
        latest_intelligence.bind(
            "<Configure>", lambda _event: self._layout_dashboard_cards()
        )
        self._layout_dashboard_cards()

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
        ttk.Label(filters, text="Search").grid(row=0, column=0, sticky="w")
        search = ttk.Entry(filters, textvariable=self.search_var)
        search.grid(row=0, column=1, padx=5, sticky="ew")
        search.bind("<Return>", lambda e: self.load_table())

        ttk.Label(filters, text="Priority").grid(row=0, column=2, padx=(12,0), sticky="w")
        priority_filter = ttk.Combobox(filters, textvariable=self.priority_var, state="readonly", width=22,
                     values=tuple(choice.label for choice in self._priority_filter_choices))
        priority_filter.grid(row=0, column=3, padx=5, sticky="ew")

        ttk.Label(filters, text="Decision").grid(row=1, column=0, sticky="w", pady=(6, 0))
        decision_filter = ttk.Combobox(filters, textvariable=self.decision_filter_var, state="readonly", width=20,
                     values=tuple(choice.label for choice in self._decision_filter_choices))
        decision_filter.grid(row=1, column=1, padx=5, pady=(6, 0), sticky="ew")
        apply_filter = ttk.Button(filters, text="Apply", command=self.load_table)
        apply_filter.grid(row=1, column=3, padx=5, pady=(6, 0), sticky="e")
        filters.columnconfigure(1, weight=1)
        filters.columnconfigure(3, weight=1)
        self.decision_filter_controls = (
            search,
            priority_filter,
            decision_filter,
            apply_filter,
        )
        self.priority_filter = priority_filter
        self.decision_filter = decision_filter

        table = ttk.Frame(self.decisions_tab)
        table.pack(fill="both", expand=True)
        cols = tuple(column.column_id.value for column in COLLECTION_DECISION_COLUMNS)
        self.tree = ttk.Treeview(table, columns=cols, show="headings", selectmode="browse")
        for column in COLLECTION_DECISION_COLUMNS:
            self.tree.heading(column.column_id.value, text=column.label)
            self.tree.column(column.column_id.value, width=column.width, anchor=column.anchor.value, stretch=False)
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", self.edit_selected)

        self.decision_vertical_scrollbar = ttk.Scrollbar(
            table, orient="vertical", command=self.tree.yview
        )
        self.decision_vertical_scrollbar.grid(row=0, column=1, sticky="ns")
        self.decision_horizontal_scrollbar = ttk.Scrollbar(table, orient="horizontal", command=self.tree.xview)
        self.decision_horizontal_scrollbar.grid(row=1, column=0, sticky="ew")
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        self.tree.configure(
            yscrollcommand=self.decision_vertical_scrollbar.set,
            xscrollcommand=self.decision_horizontal_scrollbar.set,
        )
        self._configure_dashboard_wheel_scrolling()
        self._configure_slice_four_keyboard()

    def _layout_dashboard_cards(self, event=None):
        """Reflow Dashboard cards from the final canvas viewport allocation."""

        canvas = self.dashboard_canvas
        width = getattr(event, "width", 0) or canvas.winfo_width()
        canvas.itemconfigure(self.dashboard_window, width=width)
        if not hasattr(self, "dashboard_homepage_cards"):
            return

        def preferred_card_width(card, label):
            preferred_body = self.dashboard_card_preferred_wraplengths[label]
            native_chrome = max(0, card.winfo_reqwidth() - label.winfo_reqwidth())
            return preferred_body + native_chrome + 16

        homepage = self.dashboard_homepage_cards
        commands = self.dashboard_command_cards
        two_column_content = max(
            preferred_card_width(*homepage[0]) + preferred_card_width(*homepage[1]),
            preferred_card_width(*homepage[2]) + preferred_card_width(*homepage[3]),
            preferred_card_width(*commands[0]) + preferred_card_width(*commands[1]),
            preferred_card_width(*commands[2]) + preferred_card_width(*commands[3]),
        )
        section = self.dashboard_card_sections[0]
        outer_chrome = max(0, canvas.winfo_width() - section.winfo_width())
        mode = "wide" if width >= two_column_content + outer_chrome else "compact"
        if mode == self._dashboard_card_layout:
            return

        homepage_positions = (
            ((1, 0, 3), (1, 3, 3), (2, 0, 3), (2, 3, 3), (3, 0, 6))
            if mode == "wide"
            else ((1, 0, 6), (2, 0, 6), (3, 0, 6), (4, 0, 6), (5, 0, 6))
        )
        command_positions = (
            ((0, 0, 3), (0, 3, 3), (1, 0, 3), (1, 3, 3), (2, 0, 3))
            if mode == "wide"
            else ((0, 0, 6), (1, 0, 6), (2, 0, 6), (3, 0, 6), (4, 0, 6))
        )
        for (card, _label), (row, column, columnspan) in zip(
            homepage, homepage_positions
        ):
            card.grid_configure(row=row, column=column, columnspan=columnspan)
        for (card, _label), (row, column, columnspan) in zip(
            commands, command_positions
        ):
            card.grid_configure(row=row, column=column, columnspan=columnspan)
        self._dashboard_card_layout = mode

    @staticmethod
    def _wrap_dashboard_label(event):
        """Wrap a Dashboard body to its final allocated label width."""

        width = getattr(event, "width", 0)
        if width > 1 and int(event.widget.cget("wraplength")) != width:
            event.widget.configure(wraplength=width)

    def _configure_dashboard_wheel_scrolling(self):
        """Route wheel input from the live primary scrollable page subtrees."""

        self.bind("<MouseWheel>", self._scroll_dashboard_from_wheel, add="+")
        self.bind("<Button-4>", self._scroll_dashboard_from_wheel, add="+")
        self.bind("<Button-5>", self._scroll_dashboard_from_wheel, add="+")
        self.bind("<MouseWheel>", self._scroll_project_from_wheel, add="+")
        self.bind("<Button-4>", self._scroll_project_from_wheel, add="+")
        self.bind("<Button-5>", self._scroll_project_from_wheel, add="+")

    def _scroll_dashboard_from_wheel(self, event):
        """Scroll only when the wheel originated inside the live Dashboard."""

        if not self._is_live_dashboard_widget(getattr(event, "widget", None)):
            return None
        units = self._wheel_scroll_units(event)
        if units == 0:
            return None
        try:
            self.dashboard_canvas.yview_scroll(units, "units")
        except tk.TclError:
            return None
        return "break"

    def _is_live_dashboard_widget(self, widget):
        if widget is None:
            return False
        try:
            if not widget.winfo_exists() or not self.dashboard_canvas.winfo_exists():
                return False
            current = widget
            while current is not None:
                if current in (self.dashboard_canvas, self.dashboard_content):
                    return True
                parent_name = current.winfo_parent()
                if not parent_name:
                    return False
                current = current._nametowidget(parent_name)
        except (KeyError, tk.TclError):
            return False
        return False

    def _scroll_project_from_wheel(self, event):
        """Scroll only when the wheel originated inside the live Project page."""

        if not self._is_live_project_widget(getattr(event, "widget", None)):
            return None
        units = self._wheel_scroll_units(event)
        if units == 0:
            return None
        try:
            self.project_canvas.yview_scroll(units, "units")
        except tk.TclError:
            return None
        return "break"

    def _is_live_project_widget(self, widget):
        if widget is None:
            return False
        try:
            if not widget.winfo_exists() or not self.project_canvas.winfo_exists():
                return False
            current = widget
            while current is not None:
                if current in (self.project_canvas, self.project_content):
                    return True
                parent_name = current.winfo_parent()
                if not parent_name:
                    return False
                current = current._nametowidget(parent_name)
        except (KeyError, tk.TclError):
            return False
        return False

    @staticmethod
    def _wheel_scroll_units(event):
        number = getattr(event, "num", None)
        if number == 4:
            return -1
        if number == 5:
            return 1
        delta = getattr(event, "delta", 0)
        if not isinstance(delta, (int, float)) or delta == 0:
            return 0
        if abs(delta) >= 120:
            return -max(-1, min(1, int(delta / 120)))
        return -max(-1, min(1, int(delta)))

    def _configure_slice_four_keyboard(self):
        """Define local keyboard activation and traversal without global bindings."""

        dashboard_controls = (
            self.import_csv_button,
            self.refresh_discogs_button,
            self.database_backup_button,
            self.export_excel_button,
            self.export_intelligence_button,
            self.refresh_view_button,
            self.dashboard_canvas,
            self.hot_now_button,
            self.collection_explorer_button,
            self.dashboard_health_button,
            self.hidden_gems_button,
            self.hidden_gems_observations_button,
        )
        review_controls = (
            self.observation_tree,
            self.observation_detail,
            self.add_observation_button,
            self.reopen_observation_button,
            self.open_queued_observation_button,
            self.observation_action_reason_label,
            self.queue_tree,
            self.queue_note,
            self.queue_save_button,
            self.queue_status_button,
            self.queue_resolve_button,
            self.queue_remove_button,
            self.queue_decision_button,
            self.queue_action_reason_label,
            self.tree,
            *self.decision_filter_controls,
        )
        project_controls = (
            self.project_canvas,
            *self.project_action_buttons,
        )
        for control in (*project_controls, *dashboard_controls, *review_controls):
            control.configure(takefocus="1")
            control.bind(
                "<Tab>",
                lambda _event, widget=control: self._move_scoped_focus(widget, True),
                add="+",
            )
            control.bind(
                "<Shift-Tab>",
                lambda _event, widget=control: self._move_scoped_focus(widget, False),
                add="+",
            )
            control.bind(
                "<ISO_Left_Tab>",
                lambda _event, widget=control: self._move_scoped_focus(widget, False),
                add="+",
            )
        for button in (
            *self.project_action_buttons,
            self.import_csv_button,
            self.refresh_discogs_button,
            self.database_backup_button,
            self.export_excel_button,
            self.export_intelligence_button,
            self.refresh_view_button,
            self.hot_now_button,
            self.collection_explorer_button,
            self.dashboard_health_button,
            self.hidden_gems_button,
            self.hidden_gems_observations_button,
            self.add_observation_button,
            self.reopen_observation_button,
            self.open_queued_observation_button,
            self.queue_save_button,
            self.queue_status_button,
            self.queue_resolve_button,
            self.queue_remove_button,
            self.queue_decision_button,
            self.decision_filter_controls[-1],
        ):
            button.bind(
                "<Return>",
                lambda _event, value=button: self._invoke_button(value),
                add="+",
            )
            button.bind(
                "<space>",
                lambda _event, value=button: self._invoke_button(value),
                add="+",
            )
        self._dip_dashboard_focus_order = dashboard_controls
        self._dip_project_focus_order = project_controls
        self._dip_review_focus_order = review_controls

    def _move_scoped_focus(self, widget, forward):
        declared = (
            self._dip_dashboard_focus_order
            if widget in self._dip_dashboard_focus_order
            else self._dip_project_focus_order
            if widget in self._dip_project_focus_order
            else self._dip_review_focus_order
        )
        cycle = tuple(value for value in declared if self._focus_eligible(value))
        if not cycle:
            return "break"
        try:
            index = cycle.index(widget)
        except ValueError:
            index = -1 if forward else 0
        target = cycle[(index + (1 if forward else -1)) % len(cycle)]
        target.focus_set()
        if target in self._dip_dashboard_focus_order:
            self._reveal_dashboard_control(target)
        elif target in self._dip_project_focus_order:
            self._reveal_project_control(target)
        return "break"

    @staticmethod
    def _focus_eligible(widget):
        try:
            if not widget.winfo_exists() or not widget.winfo_viewable():
                return False
            state = getattr(widget, "state", None)
            return state is None or "disabled" not in state()
        except tk.TclError:
            return False

    def _reveal_dashboard_control(self, widget):
        try:
            canvas = self.dashboard_canvas
            canvas.update_idletasks()
            top = widget.winfo_rooty() - self.dashboard_content.winfo_rooty()
            bottom = top + widget.winfo_height()
            total = max(1, self.dashboard_content.winfo_reqheight())
            view_top, view_bottom = (value * total for value in canvas.yview())
            if top < view_top:
                canvas.yview_moveto(max(0.0, top / total))
            elif bottom > view_bottom:
                canvas.yview_moveto(min(1.0, max(0.0, (bottom - canvas.winfo_height()) / total)))
        except tk.TclError:
            return

    def _reveal_project_control(self, widget):
        try:
            canvas = self.project_canvas
            canvas.update_idletasks()
            top = widget.winfo_rooty() - self.project_content.winfo_rooty()
            bottom = top + widget.winfo_height()
            total = max(1, self.project_content.winfo_reqheight())
            view_top, view_bottom = (value * total for value in canvas.yview())
            if top < view_top:
                canvas.yview_moveto(max(0.0, top / total))
            elif bottom > view_bottom:
                canvas.yview_moveto(
                    min(
                        1.0,
                        max(0.0, (bottom - canvas.winfo_height()) / total),
                    )
                )
        except tk.TclError:
            return

    @staticmethod
    def _invoke_button(button):
        button.invoke()
        return "break"

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
        self.observation_summary_label = ttk.Label(
            controls,
            textvariable=self.observation_summary_var,
            justify="left",
        )
        self.observation_summary_label.pack(
            side="left", fill="x", expand=True, padx=12
        )
        self.observation_summary_label.bind(
            "<Configure>", self._wrap_observation_summary
        )

        self.observation_panes = ttk.Panedwindow(
            self.observations_tab, orient="horizontal"
        )
        self.observation_panes.pack(fill="both", expand=True)
        self.observation_table_panel = ttk.Frame(self.observation_panes)
        self.observation_detail_panel = ttk.Frame(
            self.observation_panes, padding=(10, 0, 0, 0)
        )
        self.observation_panes.add(self.observation_table_panel, weight=1)
        self.observation_panes.add(self.observation_detail_panel, weight=1)
        self.observation_panes.bind(
            "<Configure>", self._layout_observation_panes
        )

        columns = ("artist", "title", "signal", "queue", "scroll_end")
        self.observation_tree = ttk.Treeview(
            self.observation_table_panel,
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
            self.observation_tree.column(
                column,
                width=width,
                minwidth=width,
                stretch=False,
                anchor="w",
            )
        # A non-data terminal gutter keeps the final Queue column clear of
        # native Treeview borders when the horizontal viewport is fully right.
        self.observation_tree.heading("scroll_end", text="")
        self.observation_tree.column(
            "scroll_end",
            width=20,
            minwidth=20,
            stretch=False,
            anchor="w",
        )
        self.observation_vertical_scroll = ttk.Scrollbar(
            self.observation_table_panel,
            orient="vertical",
            command=self.observation_tree.yview,
        )
        self.observation_horizontal_scroll = ttk.Scrollbar(
            self.observation_table_panel,
            orient="horizontal",
            command=self.observation_tree.xview,
        )
        self.observation_tree.configure(
            yscrollcommand=self.observation_vertical_scroll.set,
            xscrollcommand=self.observation_horizontal_scroll.set,
        )
        self.observation_table_panel.rowconfigure(0, weight=1)
        self.observation_table_panel.columnconfigure(0, weight=1)
        self.observation_tree.grid(row=0, column=0, sticky="nsew")
        self.observation_vertical_scroll.grid(row=0, column=1, sticky="ns")
        self.observation_horizontal_scroll.grid(row=1, column=0, sticky="ew")
        self.observation_tree.bind(
            "<<TreeviewSelect>>",
            self._on_observation_selected,
        )
        for sequence in (
            "<Shift-MouseWheel>",
            "<Shift-Button-4>",
            "<Shift-Button-5>",
        ):
            self.observation_tree.bind(
                sequence,
                self._scroll_observation_table_horizontally,
                add="+",
            )

        self.observation_detail_viewport = ttk.Frame(
            self.observation_detail_panel
        )
        self.observation_detail = tk.Text(
            self.observation_detail_viewport,
            wrap="word",
            padx=10,
            pady=10,
            takefocus=True,
        )
        self.observation_detail_scroll = ttk.Scrollbar(
            self.observation_detail_viewport,
            orient="vertical",
            command=self.observation_detail.yview,
        )
        self.observation_detail.configure(
            yscrollcommand=self.observation_detail_scroll.set
        )
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.observation_detail.bind(
                sequence,
                self._scroll_observation_detail,
                add="+",
            )
        self.observation_detail_viewport.rowconfigure(0, weight=1)
        self.observation_detail_viewport.columnconfigure(0, weight=1)
        self.observation_detail.grid(row=0, column=0, sticky="nsew")
        self.observation_detail_scroll.grid(row=0, column=1, sticky="ns")
        self.observation_detail.configure(state="disabled")
        actions = ttk.Frame(self.observation_detail_panel)
        self.add_observation_button = ttk.Button(
            actions,
            text="Add to Weekend Review Queue",
            command=self._add_selected_observation,
        )
        self.reopen_observation_button = ttk.Button(
            actions,
            text="Reopen",
            command=self._reopen_selected_observation,
        )
        self.open_queued_observation_button = ttk.Button(
            actions,
            text="Open queued item",
            command=self._open_selected_observation_queue_item,
        )
        self.add_observation_button.grid(row=0, column=0, columnspan=2, sticky="w")
        self.reopen_observation_button.grid(row=1, column=0, padx=(0, 6), sticky="w")
        self.open_queued_observation_button.grid(row=1, column=1, sticky="w")
        self.observation_action_reason_var = tk.StringVar()
        self.observation_action_reason_label = ttk.Label(
            self.observation_detail_panel,
            textvariable=self.observation_action_reason_var,
            wraplength=520,
            justify="left",
            takefocus=True,
        )
        self.observation_action_reason_label.pack(
            side="bottom", anchor="w", fill="x", pady=(6, 0)
        )
        self.observation_action_reason_label.bind(
            "<Configure>", self._wrap_observation_action_reason
        )
        actions.pack(side="bottom", fill="x", pady=(8, 0))
        self.observation_detail_viewport.pack(fill="both", expand=True)
        self._set_observation_action_state(None)

    def _layout_observation_panes(self, event=None):
        """Allocate equal useful widths after the observation pane is final."""

        width = getattr(event, "width", 0) or self.observation_panes.winfo_width()
        if width <= 1:
            return
        sash_width = max(0, width - sum(
            self.observation_panes.nametowidget(name).winfo_width()
            for name in self.observation_panes.panes()
        ))
        target = max(1, (width - sash_width) // 2)
        if self.observation_panes.sashpos(0) != target:
            self.observation_panes.sashpos(0, target)

    def _wrap_observation_summary(self, event):
        """Wrap observation status copy to its final control allocation."""

        width = getattr(event, "width", 0)
        if width > 1:
            self.observation_summary_label.configure(wraplength=width)

    def _wrap_observation_action_reason(self, event):
        """Wrap the complete observation action reason to its final pane."""

        width = getattr(event, "width", 0)
        if width > 1:
            self.observation_action_reason_label.configure(wraplength=width)

    def _scroll_observation_detail(self, event):
        """Route platform wheel input only to the live observation detail."""

        try:
            units = self._wheel_scroll_units(event)
            if units and self.observation_detail.winfo_exists():
                self.observation_detail.yview_scroll(units, "units")
        except tk.TclError:
            return "break"
        return "break"

    def _scroll_observation_table_horizontally(self, event):
        """Route scoped cross-platform horizontal gestures to the table."""

        units = self._wheel_scroll_units(event)
        if units == 0:
            return None
        try:
            self.observation_tree.xview_scroll(units, "units")
        except tk.TclError:
            return None
        return "break"

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

        self.queue_panes = ttk.Panedwindow(
            self.queue_tab, orient="horizontal"
        )
        self.queue_panes.pack(fill="both", expand=True)
        self.queue_table_panel = ttk.Frame(self.queue_panes)
        right = ttk.Frame(self.queue_panes, padding=(10, 0, 0, 0))
        self.queue_panes.add(self.queue_table_panel, weight=1)
        self.queue_panes.add(right, weight=2)
        self.queue_panes.bind("<Configure>", self._layout_queue_panes)

        self.queue_tree = ttk.Treeview(
            self.queue_table_panel,
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
            self.queue_table_panel,
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
        self.queue_detail_viewport = ttk.Frame(right)
        self.queue_detail_text = tk.Text(
            self.queue_detail_viewport,
            height=5,
            wrap="word",
            padx=4,
            pady=4,
            takefocus=False,
        )
        self.queue_detail_scroll = ttk.Scrollbar(
            self.queue_detail_viewport,
            orient="vertical",
            command=self.queue_detail_text.yview,
        )
        self.queue_detail_text.configure(
            yscrollcommand=self.queue_detail_scroll.set,
            state="disabled",
        )
        self.queue_detail_viewport.rowconfigure(0, weight=1)
        self.queue_detail_viewport.columnconfigure(0, weight=1)
        self.queue_detail_text.grid(row=0, column=0, sticky="nsew")
        self.queue_detail_scroll.grid(row=0, column=1, sticky="ns")
        self.queue_detail_viewport.pack(anchor="w", fill="x")
        self.queue_detail_var.trace_add(
            "write", self._render_queue_detail_text
        )
        self._render_queue_detail_text()
        ttk.Label(right, text="Review note").pack(
            anchor="w",
            pady=(12, 4),
        )
        self.queue_note = tk.Text(right, height=10, wrap="word")
        self.queue_note.bind("<KeyRelease>", self._on_queue_note_edited)
        self.queue_note.configure(state="disabled")

        actions = ttk.Frame(right)
        self.queue_save_button = ttk.Button(
            actions,
            text="Save note",
            command=self._save_queue_note,
        )
        self.queue_status_button = ttk.Button(
            actions,
            text="Start Review",
            command=self._toggle_queue_status,
        )
        self.queue_resolve_button = ttk.Button(
            actions,
            text="Resolve",
            command=self._resolve_or_reopen_queue_item,
        )
        self.queue_remove_button = ttk.Button(
            actions,
            text="Remove",
            command=self._remove_queue_item,
        )
        self.queue_decision_button = ttk.Button(
            actions,
            text="Open Collection Decision",
            command=self._open_queue_collection_decision,
        )
        self.queue_actions = actions
        self.queue_detail_panel = right
        self._queue_action_layout = None
        right.bind("<Configure>", self._layout_queue_actions)
        self._layout_queue_actions()
        self.queue_action_reason_var = tk.StringVar()
        self.queue_action_reason_label = ttk.Label(
            right,
            textvariable=self.queue_action_reason_var,
            wraplength=520,
            justify="left",
            takefocus=True,
        )
        self.queue_action_reason_label.pack(
            side="bottom", anchor="w", fill="x", pady=(6, 0)
        )
        self.queue_action_reason_label.bind(
            "<Configure>", self._wrap_queue_action_reason
        )
        actions.pack(side="bottom", fill="x", pady=(8, 0))
        self.queue_note.pack(fill="both", expand=True)
        self._set_queue_controls_enabled(False)

    def _render_queue_detail_text(self, *_args):
        """Render complete queue metadata in its bounded read-only viewport."""

        self.queue_detail_text.configure(state="normal")
        self.queue_detail_text.delete("1.0", "end")
        self.queue_detail_text.insert("1.0", self.queue_detail_var.get())
        self.queue_detail_text.configure(state="disabled")
        self.queue_detail_text.yview_moveto(0.0)

    def _layout_queue_actions(self, event=None):
        """Keep every queue action visible in narrow and expanded panes."""

        width = (
            getattr(event, "width", 0)
            or self.queue_detail_panel.winfo_width()
        )
        width = max(0, width - 10)
        buttons = (
            self.queue_save_button,
            self.queue_status_button,
            self.queue_resolve_button,
            self.queue_remove_button,
            self.queue_decision_button,
        )
        expanded_width = self._queue_expanded_action_width()
        mode = "expanded" if width >= expanded_width else "compact"
        for button in buttons:
            button.grid_forget()
        for column in range(5):
            self.queue_actions.columnconfigure(
                column,
                weight=1 if mode == "compact" and column < 2 else 0,
                minsize=(
                    max(
                        self.queue_save_button.winfo_reqwidth(),
                        self.queue_resolve_button.winfo_reqwidth(),
                    )
                    if mode == "compact" and column == 0
                    else max(
                        self.queue_status_button.winfo_reqwidth(),
                        self.queue_remove_button.winfo_reqwidth(),
                    )
                    if mode == "compact" and column == 1
                    else 0
                ),
            )
        if mode == "expanded":
            for button, row, column, last_in_row in (
                (self.queue_save_button, 0, 0, False),
                (self.queue_status_button, 0, 1, False),
                (self.queue_resolve_button, 0, 2, True),
                (self.queue_remove_button, 1, 0, False),
                (self.queue_decision_button, 1, 1, True),
            ):
                button.grid(
                    row=row,
                    column=column,
                    padx=(0, 5) if not last_in_row else 0,
                    sticky="w",
                )
        else:
            for button, row, column in (
                (self.queue_save_button, 0, 0),
                (self.queue_status_button, 0, 1),
                (self.queue_resolve_button, 1, 0),
                (self.queue_remove_button, 1, 1),
            ):
                button.grid(
                    row=row,
                    column=column,
                    sticky="ew",
                )
            self.queue_decision_button.grid(
                row=2, column=0, columnspan=2, sticky="ew"
            )
        self._queue_action_layout = mode

    def _layout_queue_panes(self, event=None):
        """Allocate detail width from the current native workflow labels."""

        width = getattr(event, "width", 0) or self.queue_panes.winfo_width()
        if width <= 1:
            return
        sash_width = max(
            0,
            width
            - self.queue_table_panel.winfo_width()
            - self.queue_detail_panel.winfo_width(),
        )
        usable_width = max(1, width - sash_width)
        compact_detail_width = self._queue_compact_action_width() + 10
        expanded_detail_width = self._queue_expanded_action_width() + 10
        detail_width = (
            expanded_detail_width
            if usable_width >= expanded_detail_width * 2
            else compact_detail_width
        )
        detail_width = min(detail_width, max(1, usable_width - 1))
        target = max(1, usable_width - detail_width)
        if self.queue_panes.sashpos(0) != target:
            self.queue_panes.sashpos(0, target)

    def _refresh_queue_action_geometry(self):
        """Re-measure and reflow after authoritative action text changes."""

        self.queue_actions.update_idletasks()
        self._layout_queue_panes()
        self.queue_detail_panel.update_idletasks()
        self._layout_queue_actions()

    def _queue_compact_action_width(self):
        """Return the native width required by the widest compact row."""

        return max(
            self.queue_save_button.winfo_reqwidth()
            + self.queue_status_button.winfo_reqwidth(),
            self.queue_resolve_button.winfo_reqwidth()
            + self.queue_remove_button.winfo_reqwidth(),
            self.queue_decision_button.winfo_reqwidth(),
        )

    def _queue_expanded_action_width(self):
        """Return the shared-column width required by expanded action rows."""

        return (
            max(
                self.queue_save_button.winfo_reqwidth(),
                self.queue_remove_button.winfo_reqwidth(),
            )
            + max(
                self.queue_status_button.winfo_reqwidth(),
                self.queue_decision_button.winfo_reqwidth(),
            )
            + self.queue_resolve_button.winfo_reqwidth()
            + 10
        )

    def _wrap_queue_action_reason(self, event):
        """Wrap the complete disabled reason to its real pane allocation."""

        width = getattr(event, "width", 0)
        if width > 1:
            self.queue_action_reason_label.configure(wraplength=width)

    def _observation_source(self):
        return _enum_for_label(
            self.observation_source_var.get(),
            _SOURCE_LABELS,
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
        try:
            source, release_id = selection[0].split(":", 1)
            return ObservationIdentity(
                WeekendObservationSource(source),
                int(release_id),
            )
        except Exception as exc:
            raise SessionValidationError(
                "Desktop session selection cannot be captured."
            ) from exc

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
            for section in observation_detail_sections(observation):
                heading_tag = (
                    "provenance_heading"
                    if section.kind is ReviewDetailSectionKind.TECHNICAL_PROVENANCE
                    else "detail_heading"
                )
                body_tag = (
                    "provenance_body"
                    if section.kind is ReviewDetailSectionKind.TECHNICAL_PROVENANCE
                    else "detail_body"
                )
                self.observation_detail.insert("end", f"{section.title}\n", heading_tag)
                self.observation_detail.insert("end", "\n".join(section.lines), body_tag)
                self.observation_detail.insert("end", "\n\n")
            self.observation_detail.tag_configure(
                "detail_heading", font=("Helvetica", 12, "bold")
            )
            self.observation_detail.tag_configure(
                "provenance_heading", font=("Helvetica", 10, "bold"), lmargin1=14, lmargin2=14
            )
            self.observation_detail.tag_configure(
                "provenance_body", font=("Helvetica", 10), lmargin1=14, lmargin2=14
            )
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
        reason = DisabledActionReason.NO_OBSERVATION.value
        if observation is None or self.collector_review_service is None:
            if self.collector_review_service is None:
                reason = DisabledActionReason.OBSERVATION_SERVICE_UNAVAILABLE.value
            self.observation_action_reason_var.set(reason)
            return
        membership = observation.queue_membership
        if not membership.is_queued:
            self.add_observation_button.state(["!disabled"])
            reason = DisabledActionReason.NOT_QUEUED.value
        elif membership.status is WeekendReviewStatus.RESOLVED:
            self.reopen_observation_button.state(["!disabled"])
            self.open_queued_observation_button.state(["!disabled"])
            reason = DisabledActionReason.RESOLVED_OBSERVATION.value
        else:
            self.open_queued_observation_button.state(["!disabled"])
            reason = DisabledActionReason.ALREADY_QUEUED.value
        self.observation_action_reason_var.set(reason)

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
        if self.__dict__.get("_session_restoring", False):
            return
        if not self._confirm_unsaved_queue_note():
            self.queue_filter_var.set(self._last_queue_filter)
            return
        self._last_queue_filter = self.queue_filter_var.get()
        self.refresh_weekend_review_queue()

    def refresh_weekend_review_queue(self, preserve_queue_item_id=None):
        if self.collector_review_service is None:
            self._show_queue_unavailable()
            return
        if preserve_queue_item_id is None and self.current_queue_item is not None:
            preserve_queue_item_id = self.current_queue_item.queue_item_id
        try:
            items = self.collector_review_service.list_queue(
                self._queue_statuses()
            )
        except Exception:
            self._show_queue_unavailable()
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

    def _show_queue_unavailable(self):
        """Render truthful unavailable state without discarding a dirty note."""

        self.queue_summary_var.set("Weekend Review Queue is unavailable.")
        for queue_item_id in self.queue_tree.get_children():
            self.queue_tree.delete(queue_item_id)
        self.queue_detail_var.set("Weekend Review Queue is unavailable.")
        self.queue_status_button.configure(text="Start Review")
        self.queue_resolve_button.configure(text="Resolve")
        dirty_note = self._queue_note_dirty
        if not dirty_note:
            self.current_queue_item = None
            self._queue_note_loading = True
            self.queue_note.configure(state="normal")
            self.queue_note.delete("1.0", "end")
            self._queue_note_loading = False
        self._set_queue_controls_enabled(False)
        self.queue_action_reason_var.set(
            DisabledActionReason.QUEUE_SERVICE_UNAVAILABLE.value
        )
        if dirty_note:
            self.queue_note.configure(state="normal")
        self._refresh_queue_action_geometry()

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
            self.queue_status_button.configure(text="Start Review")
            self.queue_resolve_button.configure(text="Resolve")
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
            self.queue_action_reason_var.set(
                DisabledActionReason.RESOLVED_START_REVIEW.value
                if item.status is WeekendReviewStatus.RESOLVED
                else DisabledActionReason.QUEUE_ACTIONS_AVAILABLE.value
            )
            self.queue_resolve_button.configure(
                text=(
                    "Reopen"
                    if item.status is WeekendReviewStatus.RESOLVED
                    else "Resolve"
                )
            )
        self._refresh_queue_action_geometry()
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
        self.queue_action_reason_var.set(
            DisabledActionReason.QUEUE_ACTIONS_AVAILABLE.value
            if enabled
            else (
                DisabledActionReason.QUEUE_SERVICE_UNAVAILABLE.value
                if self.collector_review_service is None
                else DisabledActionReason.NO_QUEUE_ITEM.value
            )
        )

    def _on_queue_note_edited(self, _event=None):
        if not self._queue_note_loading and self.current_queue_item is not None:
            self._queue_note_dirty = (
                self.queue_note.get("1.0", "end-1c")
                != self.current_queue_item.review_note
            )
            if self._queue_note_dirty:
                self.queue_action_reason_var.set(
                    DisabledActionReason.UNSAVED_NOTE.value
                )
            else:
                self.queue_action_reason_var.set(
                    DisabledActionReason.QUEUE_ACTIONS_AVAILABLE.value
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
        self._queue_note_discarded = True
        return True

    def _on_collection_review_destination_changed(self, _event=None):
        if (
            self._review_tab_change_guard
            or self.__dict__.get("_session_restoring", False)
        ):
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
        self.project_canvas = tk.Canvas(
            self.project_tab,
            highlightthickness=0,
            takefocus=True,
        )
        self.project_scrollbar = ttk.Scrollbar(
            self.project_tab,
            orient="vertical",
            command=self.project_canvas.yview,
        )
        self.project_canvas.configure(yscrollcommand=self.project_scrollbar.set)
        self.project_scrollbar.pack(side="right", fill="y")
        self.project_canvas.pack(side="left", fill="both", expand=True)
        self.project_content = ttk.Frame(self.project_canvas)
        self.project_window = self.project_canvas.create_window(
            (0, 0), window=self.project_content, anchor="nw"
        )
        self.project_content.bind(
            "<Configure>",
            lambda _event: self.project_canvas.configure(
                scrollregion=self.project_canvas.bbox("all")
            ),
        )
        self.project_canvas.bind("<Configure>", self._layout_project_viewport)
        self.project_action_buttons = []
        self.project_section_cards = []
        self.project_body_labels = []
        if self.project_workspace_controller is None:
            ttk.Label(
                self.project_content, text="Project Workspace is unavailable."
            ).pack(anchor="w")
            return
        rendered = self.project_workspace_controller.open()
        self.project_title_label = ttk.Label(
            self.project_content,
            text=rendered.title,
            font=("Helvetica", 22, "bold"),
        )
        self.project_title_label.pack(anchor="w", pady=(0, 14))
        for section in rendered.sections:
            frame = ttk.LabelFrame(
                self.project_content, text=section.title, padding=14
            )
            frame.pack(fill="x", pady=6)
            label = ttk.Label(
                frame, text=section.body, wraplength=1000, justify="left"
            )
            label.pack(anchor="w", fill="x")
            label.bind("<Configure>", self._wrap_project_label)
            self.project_section_cards.append(frame)
            self.project_body_labels.append(label)
            if section.title == "Quick Actions":
                actions = ttk.Frame(frame)
                actions.pack(anchor="w", fill="x", pady=(10, 0))
                for row, action in enumerate(rendered.actions):
                    button = ttk.Button(
                        actions,
                        text=action.label,
                        command=lambda target=action.target: self._open_project_target(target),
                    )
                    if not action.enabled:
                        button.state(["disabled"])
                    button.grid(row=row, column=0, pady=(0, 4), sticky="w")
                    self.project_action_buttons.append(button)

    def _layout_project_viewport(self, event=None):
        """Fit Project content to its final canvas viewport width."""

        width = getattr(event, "width", 0) or self.project_canvas.winfo_width()
        if width > 1:
            self.project_canvas.itemconfigure(self.project_window, width=width)

    @staticmethod
    def _wrap_project_label(event):
        """Wrap Project body copy to its final card allocation."""

        width = getattr(event, "width", 0)
        if width > 1 and int(event.widget.cget("wraplength")) != width:
            event.widget.configure(wraplength=width)

    def _open_project_target(self, target):
        if target is ProjectWorkspaceNavigationTarget.DASHBOARD:
            self.tabs.select(self.dashboard_tab)

    def back_up_database(self):
        if self._collector_run_active:
            messagebox.showinfo(
                "Backup unavailable",
                "Database backup is unavailable while Collector Run is active.",
            )
            return
        if self._database_backup_active:
            messagebox.showinfo(
                "Backup already active",
                "A database backup is already in progress.",
            )
            return
        if self.database_backup_service is None:
            messagebox.showerror(
                "Backup unavailable",
                "The database backup could not be created. The existing database "
                "and any previous backup were not changed.",
            )
            return
        self._queue_note_discarded = False
        if not self._confirm_unsaved_queue_note():
            return
        if self._queue_note_discarded:
            current = self.__dict__.get("current_queue_item")
            if current is not None:
                self._load_queue_item(current)
        suggested = (
            "discogs-intelligence-backup-"
            f"{datetime.now(timezone.utc):%Y%m%d-%H%M%SZ}.sqlite3"
        )
        selected = filedialog.asksaveasfilename(
            title="Back Up Database",
            defaultextension=".sqlite3",
            initialfile=suggested,
            filetypes=[
                ("SQLite database", "*.sqlite3"),
                ("All files", "*.*"),
            ],
            confirmoverwrite=False,
        )
        if not selected:
            return
        destination = Path(selected)
        destination_exists = destination.exists()
        try:
            self.database_backup_service.validate_destination(
                destination,
                overwrite=destination_exists,
            )
        except Exception:
            messagebox.showerror(
                "Backup unavailable",
                "Choose a different existing folder and a filename ending in "
                ".sqlite3.",
            )
            return
        overwrite = False
        if destination_exists:
            overwrite = messagebox.askyesno(
                "Replace existing backup?",
                "A file with this name already exists. Replace it with the new backup?",
            )
            if not overwrite:
                return

        try:
            previous_status = self.status_var.get()
        except Exception:
            previous_status = "Ready"
        result = None
        failure = False
        try:
            self._database_backup_active = True
            self.database_backup_button.state(["disabled"])
            self.refresh_discogs_button.configure(state="disabled")
            self.status_var.set("Backing up database…")
            self.configure(cursor="watch")
            self.update_idletasks()
            result = self.database_backup_service.backup(
                destination,
                overwrite=overwrite,
            )
        except Exception:
            failure = True
        finally:
            self._database_backup_active = False
            try:
                self.configure(cursor="")
            except Exception:
                pass
            try:
                self.status_var.set(previous_status)
            except Exception:
                pass
            try:
                if self._collector_run_active:
                    self.database_backup_button.state(["disabled"])
                else:
                    self.database_backup_button.state(["!disabled"])
            except Exception:
                pass
            try:
                self.refresh_discogs_button.configure(
                    state=(
                        "disabled"
                        if self._collector_run_active
                        else "normal"
                    )
                )
            except Exception:
                pass
        if failure or result is None:
            try:
                messagebox.showerror(
                    "Backup failed",
                    "The database backup could not be created. The existing "
                    "database and any previous backup were not changed.",
                )
            except Exception:
                pass
            return
        try:
            messagebox.showinfo(
                "Backup complete",
                f"Database backup created:\n\n{result.filename}",
            )
        except Exception:
            pass

    def import_csv(self):
        if self._collector_run_active:
            messagebox.showwarning(
                "Import unavailable",
                "Collection import is unavailable while Collector Run is active.",
            )
            return
        try:
            path = filedialog.askopenfilename(
                title="Select Discogs collection export",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
        except Exception:
            _show_message_safely(
                messagebox.showerror,
                "Import unavailable",
                "The collection file selector could not be opened.",
            )
            return

        if not path:
            return

        try:
            result = self.import_service.import_collection(Path(path))
        except Exception:
            _show_message_safely(
                messagebox.showerror,
                "Import failed",
                "The selected collection file could not be imported.",
            )
            return

        try:
            self.status_var.set(
                f"Imported {result.imported_records:,} collection rows "
                f"({result.invalid_release_ids:,} invalid rows skipped)"
            )
        except Exception:
            pass

        try:
            dashboard_refreshed = self.refresh_dashboard()
        except Exception:
            dashboard_refreshed = False

        try:
            table_refreshed = self.load_table(report_failure=False)
        except Exception:
            table_refreshed = False

        if dashboard_refreshed is not True or table_refreshed is not True:
            try:
                self.status_var.set(
                    "Collection imported; displayed data could not be refreshed."
                )
            except Exception:
                pass
            _show_import_display_refresh_failure()
            return

        try:
            messagebox.showinfo(
                "Import complete",
                (
                    f"Imported or updated {result.imported_records:,} records.\n\n"
                    f"CSV rows: {result.total_rows:,}\n"
                    f"Valid release IDs: {result.valid_release_ids:,}\n"
                    f"Invalid release IDs: {result.invalid_release_ids:,}"
                ),
            )
        except Exception:
            pass

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
        self._update_marketplace_refresh_availability()
        self.refresh_discogs_button.configure(state="disabled")
        self.import_csv_button.configure(state="disabled")
        backup_button = self.__dict__.get("database_backup_button")
        if backup_button is not None:
            backup_button.state(["disabled"])
        self.progress.configure(value=0)
        self.status_var.set("Starting Discogs refresh…")
        worker = threading.Thread(
            target=self.refresh_market_data,
            args=(token,),
            daemon=True,
        )
        try:
            worker.start()
        except Exception:
            self._restore_refresh_controls()
            self.status_var.set("Refresh failed")
            messagebox.showerror(
                "Refresh failed",
                "Collector Run could not be completed. Existing saved data has "
                "been preserved.",
            )

    def refresh_market_data(self, token):
        try:
            result = self.collector_run_service.run(
                token,
                lambda progress: self.after(
                    0, self.update_refresh_progress, progress
                ),
            )
        except CollectorRunUnavailableError:
            self.after(0, self.show_refresh_unavailable)
        except CollectorRunExecutionError:
            self.after(0, self.show_refresh_error)
        except Exception:
            self.after(
                0,
                self.show_refresh_error,
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
        self._mark_marketplace_explorers_stale()
        if result.status is CollectorRunStatus.FAILED:
            self.status_var.set(
                f"Refresh failed — 0 successful, {failed:,} errors"
            )
            messagebox.showerror(
                "Refresh failed",
                self.status_var.get(),
            )
            return
        terminal_status = (
            f"Refresh complete — {succeeded:,} successful, "
            f"{failed:,} errors"
        )
        self.status_var.set(terminal_status)
        self.refresh_dashboard()
        self.load_table()
        self.status_var.set(terminal_status)
        if result.status is CollectorRunStatus.PARTIAL:
            messagebox.showwarning(
                "Refresh partially complete",
                terminal_status,
            )
        else:
            messagebox.showinfo(
                "Refresh complete",
                terminal_status,
            )

    def show_refresh_error(self, _error_message=None):
        self._restore_refresh_controls()
        self.status_var.set("Refresh failed")
        messagebox.showerror(
            "Refresh failed",
            "Collector Run could not be completed. Existing saved data has "
            "been preserved.",
        )

    def show_refresh_unavailable(self, _error_message=None):
        self._restore_refresh_controls()
        self.status_var.set("Refresh unavailable")
        messagebox.showwarning(
            "Refresh unavailable",
            "Collector Run is unavailable. Confirm that a collection has been "
            "imported and try again.",
        )

    def _restore_refresh_controls(self):
        self._collector_run_active = False
        self._update_marketplace_refresh_availability()
        self.refresh_discogs_button.configure(state="normal")
        self.import_csv_button.configure(state="normal")
        if not self.__dict__.get("_database_backup_active", False):
            backup_button = self.__dict__.get("database_backup_button")
            if backup_button is not None:
                backup_button.state(["!disabled"])

    def refresh_dashboard(self) -> bool:
        try:
            row = self.db.dashboard()
        except Exception:
            self.status_var.set("Dashboard information could not be loaded.")
            return False
        for key in ("unique_releases", "owned_copies", "protected"):
            if key in self.kpis:
                self.kpis[key].configure(text=f"{int(row[key] or 0):,}")
        self._dashboard_summary_row = row
        collection_state_var = self.__dict__.get("dashboard_collection_state_var")
        if collection_state_var is not None:
            has_collection = int(row["unique_releases"] or 0) > 0
            state_copy = presentation_state_copy(
                PresentationStateKind.IMPORTED_NOT_ANALYSED
                if has_collection
                else PresentationStateKind.NO_IMPORTED_COLLECTION
            )
            collection_state_var.set(
                f"{state_copy.heading}\n{state_copy.body}"
            )
            self.dashboard_intelligence_state_var.set(
                f"{state_copy.heading}\n{state_copy.body}"
            )
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
        return True

    def _apply_hot_now_dashboard_state(self):
        section = self.current_observation_workspace.hot_now_section
        button = self.__dict__.get("hot_now_button")
        if button is None:  # Compatibility for non-production focused test presenters.
            legacy = self.__dict__.get("hot_now_kpi_button")
            if section.status is ObservationSectionStatus.AVAILABLE:
                self.kpis["hot_now"].configure(
                    text=f"{len(self.current_observation_workspace.hot_now):,}"
                )
                legacy.state(["!disabled"])
            else:
                self.kpis["hot_now"].configure(text="—")
                legacy.state(["disabled"])
            return
        if section.status in {
            ObservationSectionStatus.AVAILABLE,
            ObservationSectionStatus.NO_HISTORY,
        }:
            button.state(["!disabled"])
        else:
            button.state(["disabled"])

    def refresh_intelligence_dashboard(self):
        try:
            homepage = self.dashboard_homepage_service.homepage()
            self.current_dashboard_homepage = homepage
            latest = homepage.section_for("latest_execution")
            if latest.run_id is not None and self.__dict__.get(
                "dashboard_collection_state_var"
            ) is not None:
                self.dashboard_collection_state_var.set(
                    "Collection facts are shown separately above. "
                    "Calculated values use the latest completed Collector Run intelligence."
                )
                self.dashboard_intelligence_state_var.set(
                    "Calculated values use the latest completed Collector Run execution."
                )
            sections = self.desktop_homepage_renderer.render(homepage)
            rendered = {
                section.section_id.value: section.body
                for section in sections
            }
        except Exception:
            self.current_dashboard_homepage = DashboardHomepageViewModel.loading()
            rendered = {
                section_id: "Dashboard information could not be loaded."
                for section_id in self.dashboard_homepage_vars
            }

        self._apply_hot_now_dashboard_state()

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
        except Exception:
            for body, _ in self.dashboard_command_vars.values():
                body.set("Dashboard information could not be loaded.")
            return
        for card in rendered.cards:
            if card.title not in self.dashboard_command_vars:
                continue
            body, actions = self.dashboard_command_vars[card.title]
            unavailable = presentation_state_copy(PresentationStateKind.UNAVAILABLE)
            body.set(f"{unavailable.heading}\n{unavailable.body}")
            for child in actions.winfo_children():
                child.destroy()
            for action in card.actions:
                button = ttk.Button(
                    actions,
                    text=action.label,
                    command=lambda target=action.target: self._open_dashboard_target(target),
                )
                if not action.enabled:
                    button.state(["disabled"])
                button.pack(side="left", padx=(0, 6))

    def _open_dashboard_target(self, target):
        if target is DashboardNavigationTarget.COLLECTION_EXPLORER:
            self.open_intelligence_explorer()

    def open_collection_health(self):
        try:
            rendered = self.collection_health_controller.open(
                self.current_dashboard_homepage
            )
        except Exception:
            messagebox.showerror(
                "Collection Health unavailable",
                "Collection Health could not be displayed.",
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
            self.hidden_gems_button.grid(row=1, column=1, padx=(0, 6), sticky="w")
        else:
            self.hidden_gems_button.grid_remove()
        hidden_section = self.current_observation_workspace.hidden_gems_section
        if hidden_section.status in {
            ObservationSectionStatus.AVAILABLE,
            ObservationSectionStatus.NO_HISTORY,
        }:
            self.hidden_gems_observations_button.grid(
                row=2, column=0, columnspan=2, pady=(6, 0), sticky="w"
            )
        else:
            self.hidden_gems_observations_button.grid_remove()

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
        except Exception:
            messagebox.showerror(
                "Hidden Gems unavailable",
                "Hidden Gems could not be displayed.",
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

    def open_intelligence_explorer(self, *, refresh_marketplace=False, selected_destination=CollectionExplorerDestination.OVERVIEW, _rendered=None, _register=True):
        window = None
        try:
            rendered = _rendered or self.collection_explorer_controller.open(
                    self.current_dashboard_homepage,
                    refresh_marketplace=refresh_marketplace,
                    selected_destination=selected_destination,
                    collector_run_active=self._collector_run_active,
                )
            window = tk.Toplevel(self)
            return self._populate_intelligence_explorer_window(window, rendered, register=_register)
        except (KeyboardInterrupt, SystemExit):
            if window is not None:
                self._marketplace_explorer_handles.pop(window, None)
                self._destroy_marketplace_window(window)
            raise
        except Exception:
            if window is not None:
                self._marketplace_explorer_handles.pop(window, None)
                self._destroy_marketplace_window(window)
            messagebox.showerror("Collection Explorer unavailable", "Collection Explorer could not be displayed.")
            return None

    def _populate_intelligence_explorer_window(self, window, rendered, *, register=True):
        window.title(rendered.title)
        window.geometry("1050x720")
        window.minsize(800, 560)
        window.transient(self)

        navigation_frame = ttk.Frame(window, padding=(12, 12, 12, 4))
        navigation_frame.pack(fill="x")
        ttk.Label(navigation_frame, text="Destination").pack(side="left", padx=(0, 8))
        enabled = tuple(item for item in rendered.navigation if item.available)
        enabled_labels = tuple(item.label for item in enabled)
        selected_index = next(
            index for index, item in enumerate(enabled)
            if item.destination is rendered.selected_destination
        )
        navigation = ttk.Combobox(
            navigation_frame,
            values=enabled_labels,
            state="readonly",
            width=max(len(value) for value in enabled_labels),
            takefocus=True,
        )
        navigation.current(selected_index)
        navigation.pack(side="left", fill="x", expand=True)

        content = ttk.Frame(window, padding=(12, 4, 12, 6))
        content.pack(fill="both", expand=True)
        text = tk.Text(content, wrap="word", padx=10, pady=10, takefocus=True)
        scrollbar = ttk.Scrollbar(content, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        sections = {section.destination: section for section in rendered.sections}

        def show_selected(_event=None):
            if _event is not None:
                try:
                    if (
                        not window.winfo_exists()
                        or window not in self._marketplace_explorer_handles
                    ):
                        return "break"
                except Exception:
                    return "break"
            index = navigation.current()
            if index < 0 or index >= len(enabled):
                return "break"
            destination = enabled[index].destination
            section = sections[destination]
            window._dip_selected_destination = destination
            text.configure(state="normal")
            text.delete("1.0", "end")
            if destination in {
                CollectionExplorerDestination.PRICE_CHANGES,
                CollectionExplorerDestination.SUPPLY_CHANGES,
            }:
                self._insert_marketplace_summary_first(text, section.body)
            else:
                text.insert("1.0", section.body)
            text.configure(state="disabled")
            text.yview_moveto(0.0)
            return "break" if _event is not None else None

        navigation.bind("<<ComboboxSelected>>", show_selected, add="+")

        def handle_selector_key(event):
            try:
                if (
                    not window.winfo_exists()
                    or window not in self._marketplace_explorer_handles
                ):
                    return "break"
            except Exception:
                return "break"
            if event.keysym in {"Left", "Up", "Right", "Down"}:
                delta = -1 if event.keysym in {"Left", "Up"} else 1
                current = navigation.current()
                if current < 0:
                    return "break"
                target = min(max(current + delta, 0), len(enabled) - 1)
                if target != current:
                    navigation.current(target)
                    show_selected()
                return "break"
            if event.keysym in {"Return", "KP_Enter", "space"}:
                show_selected()
                return "break"
            return None

        def focus_selector(_event):
            try:
                if window.winfo_exists() and window in self._marketplace_explorer_handles:
                    navigation.focus_set()
            except Exception:
                pass

        navigation.bind("<KeyPress>", handle_selector_key, add="+")
        navigation.bind("<ButtonPress-1>", focus_selector, add="+")
        show_selected()

        unavailable = tuple(item for item in rendered.navigation if not item.available)
        unavailable_frame = ttk.LabelFrame(
            window, text="Unavailable in this release", padding=(12, 8)
        )
        unavailable_frame.pack(fill="x", padx=12, pady=(0, 6), before=content)
        ttk.Label(
            unavailable_frame,
            text="\n".join(item.label for item in unavailable),
            justify="left",
        ).pack(side="left", anchor="nw", padx=(0, 18))
        ttk.Label(
            unavailable_frame,
            text=UNAVAILABLE_EXPLORER_EXPLANATION,
            justify="left",
            wraplength=480,
        ).pack(side="left", anchor="nw", fill="x", expand=True)
        controls = ttk.Frame(window)
        controls.pack(pady=(0, 12), before=content)
        stale = ttk.Label(controls, text="", justify="left")
        stale.pack(side="top", pady=2)
        ttk.Label(
            controls,
            text=_MARKETPLACE_REFRESH_EXPLANATION,
            justify="left",
        ).pack(side="top", pady=2)
        shortcut = "Command-R" if self.tk.call("tk", "windowingsystem") == "aqua" else "Control-R"
        ttk.Label(controls, text=f"Shortcut: {shortcut} (Control-R also supported)").pack(side="top", pady=2)
        active_explanation = ttk.Label(
            controls,
            text=_MARKETPLACE_REFRESH_BLOCKED if self._collector_run_active else "",
        )
        active_explanation.pack(side="top", pady=2)
        refresh_button = ttk.Button(
            controls,
            text="Refresh Marketplace Changes",
            takefocus=True,
            command=lambda: self._marketplace_refresh_callback(
                window, navigation, rendered
            ),
        )
        refresh_button.pack(side="left", padx=4)
        if self._collector_run_active:
            refresh_button.state(["disabled"])
        close = lambda: (self._marketplace_explorer_handles.pop(window, None), window.destroy())
        close_button = ttk.Button(
            controls, text="Close", takefocus=True, command=close
        )
        close_button.pack(side="left", padx=4)
        close_button.bind("<Return>", lambda _event: close(), add="+")
        close_button.bind("<space>", lambda _event: close(), add="+")
        focus_cycle = (navigation, text, refresh_button, close_button)
        for control in focus_cycle:
            control.configure(takefocus="1")

        def move_focus(index, delta):
            def move(_event):
                try:
                    if (
                        not window.winfo_exists()
                        or window not in self._marketplace_explorer_handles
                    ):
                        return "break"
                except Exception:
                    return "break"
                focus_cycle[(index + delta) % len(focus_cycle)].focus_force()
                return "break"
            return move

        focus_bindings = tuple(
            (move_focus(index, 1), move_focus(index, -1))
            for index in range(len(focus_cycle))
        )
        for control, (move_forward, move_backward) in zip(
            focus_cycle, focus_bindings
        ):
            control.bind("<Tab>", move_forward, add="+")
            control.bind("<Shift-Tab>", move_backward, add="+")
            control.bind("<ISO_Left_Tab>", move_backward, add="+")
        window._dip_marketplace_registration = (stale, refresh_button, close)
        window._dip_explorer_navigation = navigation
        window._dip_explorer_text = text
        window._dip_explorer_focus_cycle = focus_cycle
        window._dip_explorer_focus_bindings = focus_bindings
        window._dip_active_run_explanation = active_explanation
        window._dip_rendered_explorer = rendered
        self._bind_marketplace_refresh_shortcuts(
            window,
            lambda event: self._marketplace_refresh_callback(
                window, navigation, rendered, event
            ),
        )
        refresh_button.bind(
            "<Return>",
            lambda event: self._marketplace_refresh_callback(window, navigation, rendered, event),
            add="+",
        )
        refresh_button.bind(
            "<space>",
            lambda event: self._marketplace_refresh_callback(window, navigation, rendered, event),
            add="+",
        )
        if register:
            self._register_marketplace_explorer_window(window)
        return window

    @staticmethod
    def _insert_marketplace_summary_first(text, body):
        """Apply a small shared visual hierarchy to an already-rendered model."""

        section_headings = {
            "Comparison period",
            "Summary",
            "Evidence limitations",
            "Current catalogue metadata",
            "Detailed provenance",
        }
        group_prefixes = (
            "Increased (",
            "Decreased (",
            "Unchanged (",
            "Incomparable (",
            "Price observation became available (",
            "Price observation no longer available (",
            "Became available for sale (",
            "No copies observed for sale (",
        )
        lines = body.splitlines()
        in_provenance = False
        for index, line in enumerate(lines):
            suffix = "\n" if index < len(lines) - 1 else ""
            tag = None
            if index == 0:
                tag = "state_heading"
            elif line == "Detailed provenance":
                tag = "provenance_heading"
                in_provenance = True
            elif in_provenance:
                tag = "provenance_body"
            elif line in section_headings:
                tag = "section_heading"
            elif line.startswith(group_prefixes):
                tag = "group_heading"
            text.insert("end", line + suffix, tag or ())
        text.tag_configure("state_heading", font=("Helvetica", 16, "bold"), spacing3=6)
        text.tag_configure("section_heading", font=("Helvetica", 12, "bold"), spacing1=12, spacing3=4)
        text.tag_configure("group_heading", font=("Helvetica", 12, "bold"), spacing1=14, spacing3=4)
        text.tag_configure(
            "provenance_heading",
            font=("Helvetica", 10, "bold"),
            spacing1=12,
            spacing3=3,
        )
        text.tag_configure(
            "provenance_body",
            font=("Helvetica", 10),
            lmargin1=12,
            lmargin2=12,
        )

    def _register_marketplace_explorer_window(self, window):
        """Register only a fully populated Explorer replacement."""

        stale, refresh_button, close = window._dip_marketplace_registration
        self._marketplace_explorer_handles[window] = (stale, refresh_button)
        try:
            window.protocol("WM_DELETE_WINDOW", close)
            window.bind("<Destroy>", lambda event: self._marketplace_explorer_handles.pop(window, None) if event.widget is window else None, add="+")
        except (KeyboardInterrupt, SystemExit):
            self._marketplace_explorer_handles.pop(window, None)
            raise
        except Exception:
            self._marketplace_explorer_handles.pop(window, None)
            raise

    @staticmethod
    def _destroy_marketplace_window(window):
        """Contain ordinary Tk cleanup failures without hiding process control."""

        try:
            window.destroy()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            pass

    def _create_marketplace_replacement_toplevel(self):
        """Create one unregistered replacement Toplevel."""

        return tk.Toplevel(self)

    def _populate_marketplace_replacement(self, window, rendered):
        """Fully populate one replacement without registering it."""

        return self._populate_intelligence_explorer_window(
            window, rendered, register=False
        )

    def _unregister_marketplace_window(self, window):
        """Remove one retired window from authoritative bookkeeping."""

        self._marketplace_explorer_handles.pop(window, None)

    def _marketplace_refresh_callback(
        self, window, notebook, rendered, event=None
    ):
        """Shared button and keyboard boundary for explicit Marketplace refresh."""

        try:
            if not window.winfo_exists():
                return "break" if event is not None else None
        except Exception:
            return "break" if event is not None else None
        if window not in self._marketplace_explorer_handles:
            return "break" if event is not None else None
        self._refresh_marketplace_explorer(window, notebook, rendered)
        return "break" if event is not None else None

    @staticmethod
    def _bind_marketplace_refresh_shortcuts(window, callback):
        """Bind both supported shortcuts to the shared refresh callback."""

        window.bind("<Command-r>", callback, add="+")
        window.bind("<Control-r>", callback, add="+")

    def _refresh_marketplace_explorer(self, window, notebook, rendered):
        """Explicitly rebuild while preserving an enabled Explorer destination."""

        if self._collector_run_active:
            return
        replacement = None
        installed_previous = None
        cache_installed = False
        destination = self._selected_explorer_destination(window, notebook, rendered)
        if destination in _UNAVAILABLE_EXPLORER_DESTINATIONS:
            destination = CollectionExplorerDestination.OVERVIEW
        old_position = self._marketplace_view_position(window)
        old_section = next(
            (section for section in rendered.sections if section.destination is destination),
            None,
        )
        try:
            candidate = self.collection_explorer_controller.refresh_marketplace_changes()
            if candidate is None:
                raise RuntimeError("safe Marketplace refresh failure")
            candidate_presentation = self.collection_explorer_controller.present_marketplace_candidate(
                self.current_dashboard_homepage,
                candidate,
                selected_destination=destination,
            )
            candidate_rendered = self.collection_explorer_controller.render_marketplace_presentation(
                candidate_presentation
            )
            replacement = self._create_marketplace_replacement_toplevel()
            self._populate_marketplace_replacement(replacement, candidate_rendered)
            if replacement is None:
                raise RuntimeError("Marketplace presentation refresh failure")
            installed_previous = self.collection_explorer_controller.install_marketplace_changes(candidate)
            cache_installed = True
            try:
                self._register_marketplace_explorer_window(replacement)
            except BaseException:
                self.collection_explorer_controller.restore_marketplace_changes(installed_previous)
                cache_installed = False
                raise
        except (KeyboardInterrupt, SystemExit):
            if replacement is not None:
                self._marketplace_explorer_handles.pop(replacement, None)
                self._destroy_marketplace_window(replacement)
            raise
        except Exception:
            if cache_installed:
                self.collection_explorer_controller.restore_marketplace_changes(installed_previous)
            if replacement is not None:
                self._marketplace_explorer_handles.pop(replacement, None)
                self._destroy_marketplace_window(replacement)
            handle = self._marketplace_explorer_handles.get(window)
            if handle is not None:
                handle[1].state(["!disabled"])
            messagebox.showerror("Marketplace Changes", "Marketplace changes could not be refreshed. The previous results remain available and stale.")
            return
        try:
            self._unregister_marketplace_window(window)
        except (KeyboardInterrupt, SystemExit):
            self._marketplace_explorer_handles.pop(window, None)
            raise
        except Exception:
            self._marketplace_explorer_handles.pop(window, None)
        self._destroy_marketplace_window(window)
        new_section = next(
            (
                section
                for section in getattr(candidate_rendered, "sections", ())
                if section.destination is destination
            ),
            None,
        )
        if old_section is not None and new_section == old_section:
            self._restore_marketplace_view_position(replacement, old_position)
        self._clear_marketplace_window_stale(replacement)

    @staticmethod
    def _selected_explorer_destination(window, navigation, rendered):
        selected = getattr(window, "_dip_selected_destination", None)
        if selected in ENABLED_EXPLORER_DESTINATIONS:
            return selected
        try:
            current = navigation.current()
            enabled = tuple(item for item in rendered.navigation if item.available)
            if 0 <= current < len(enabled):
                return enabled[current].destination
        except Exception:
            pass
        try:
            index = navigation.index(navigation.select())
            return rendered.sections[index].destination
        except Exception:
            return CollectionExplorerDestination.OVERVIEW

    @staticmethod
    def _marketplace_view_position(window):
        text = getattr(window, "_dip_explorer_text", None)
        if text is None:
            return 0.0
        try:
            value = float(text.yview()[0])
        except Exception:
            return 0.0
        return min(1.0, max(0.0, value))

    @staticmethod
    def _restore_marketplace_view_position(window, position):
        text = getattr(window, "_dip_explorer_text", None)
        if text is None:
            return
        try:
            text.update_idletasks()
            text.yview_moveto(min(1.0, max(0.0, float(position))))
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            pass

    def _clear_marketplace_window_stale(self, window):
        """Leave a published replacement visibly current after safe cleanup."""

        handle = self._marketplace_explorer_handles.get(window)
        if handle is None:
            return
        try:
            handle[0].configure(text="")
            handle[1].state(["!disabled"])
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            pass

    def _mark_marketplace_explorers_stale(self):
        """Mark every live Explorer stale on the Tk callback thread."""

        handles = self.__dict__.setdefault("_marketplace_explorer_handles", {})
        for window, (label, button) in tuple(handles.items()):
            try:
                if not window.winfo_exists():
                    handles.pop(window, None)
                    continue
                label.configure(text=_STALE_MARKETPLACE_COPY)
                button.state(["!disabled"])
                active = getattr(window, "_dip_active_run_explanation", None)
                if active is not None:
                    active.configure(text="")
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                handles.pop(window, None)

    def _update_marketplace_refresh_availability(self):
        """Keep every live Explorer's refresh affordance truthful."""

        handles = self.__dict__.setdefault("_marketplace_explorer_handles", {})
        for window, (_stale, button) in tuple(handles.items()):
            try:
                if not window.winfo_exists():
                    handles.pop(window, None)
                    continue
                button.state(
                    ["disabled"] if self._collector_run_active else ["!disabled"]
                )
                explanation = getattr(
                    window, "_dip_active_run_explanation", None
                )
                if explanation is not None:
                    explanation.configure(
                        text=(
                            _MARKETPLACE_REFRESH_BLOCKED
                            if self._collector_run_active
                            else ""
                        )
                    )
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                handles.pop(window, None)

    def open_portfolio_overview(self, destination=None):
        """Open the separate Portfolio experience from a supplied completed result."""
        return
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
        except Exception:
            messagebox.showerror(
                "Portfolio unavailable",
                "Portfolio could not be displayed.",
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
        return
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
        except Exception:
            messagebox.showerror(
                "Historical Intelligence unavailable",
                "Intelligence Change Analysis could not be displayed.",
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
        return
        if self.marketplace_workspace_controller is None:
            messagebox.showerror("Marketplace Workspace unavailable", "Marketplace Workspace is not configured.")
            return
        try:
            rendered = self.marketplace_workspace_controller.open(
                self.current_marketplace_workspace_queue
            )
        except Exception:
            messagebox.showerror(
                "Marketplace Workspace unavailable",
                "Marketplace Workspace could not be displayed.",
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

    def load_table(self, *, report_failure: bool = True) -> bool:
        selection = getattr(self.tree, "selection", None)
        previous_selection = selection() if selection is not None else ()
        previous_id = previous_selection[0] if previous_selection else None
        for item in self.tree.get_children():
            self.tree.delete(item)
        try:
            self._refresh_review_filter_choices()
            rows = self.db.review_rows(
                search=self.search_var.get().strip(),
                priority=self._review_filter_query_value(
                    self.priority_var.get(), self._priority_filter_choices
                ),
                decision=self._review_filter_query_value(
                    self.decision_filter_var.get(),
                    self._decision_filter_choices,
                ),
            )
        except Exception:
            self.status_var.set("Collection Decisions could not be loaded.")
            if report_failure:
                _show_message_safely(
                    messagebox.showerror,
                    "Collection Decisions unavailable",
                    "Collection Decisions could not be loaded.",
                )
            return False
        for row in rows:
            self.tree.insert(
                "", "end", iid=str(row["release_id"]), values=decision_row_values(row)
            )
        if previous_id is not None and self.tree.exists(previous_id):
            self.tree.selection_set(previous_id)
            self.tree.see(previous_id)
        elif hasattr(self.tree, "selection_remove"):
            self.tree.selection_remove(self.tree.selection())
        self.status_var.set(f"Showing {len(rows):,} records")
        return True

    def _refresh_review_filter_choices(self) -> None:
        read_values = getattr(self.db, "review_filter_values", None)
        values = read_values() if callable(read_values) else ((), ())
        if type(values) is not tuple or len(values) != 2:
            values = ((), ())
        priority_values, decision_values = values
        previous_priorities = self.__dict__.get(
            "_priority_filter_choices",
            review_filter_choices(ReviewFilterField.PRIORITY, ()),
        )
        previous_decisions = self.__dict__.get(
            "_decision_filter_choices",
            review_filter_choices(ReviewFilterField.DECISION, ()),
        )
        self._priority_filter_choices = self._replace_review_filter_choices(
            self.priority_var,
            self.__dict__.get("priority_filter"),
            previous_priorities,
            review_filter_choices(
                ReviewFilterField.PRIORITY, tuple(priority_values)
            ),
        )
        self._decision_filter_choices = self._replace_review_filter_choices(
            self.decision_filter_var,
            self.__dict__.get("decision_filter"),
            previous_decisions,
            review_filter_choices(
                ReviewFilterField.DECISION, tuple(decision_values)
            ),
        )

    @staticmethod
    def _replace_review_filter_choices(
        variable,
        combobox,
        previous: tuple[ReviewFilterChoice, ...],
        current: tuple[ReviewFilterChoice, ...],
    ) -> tuple[ReviewFilterChoice, ...]:
        selected = next(
            (choice for choice in previous if choice.label == variable.get()),
            previous[0],
        )
        replacement = next(
            (
                choice
                for choice in current
                if choice.kind is selected.kind
                and choice.query_value == selected.query_value
            ),
            current[0],
        )
        if combobox is not None:
            combobox.configure(values=tuple(choice.label for choice in current))
        if variable.get() != replacement.label:
            variable.set(replacement.label)
        return current

    @staticmethod
    def _review_filter_query_value(
        label: str,
        choices: tuple[ReviewFilterChoice, ...],
    ) -> ReviewFilterChoice:
        matches = tuple(choice for choice in choices if choice.label == label)
        if len(matches) != 1:
            raise ValueError("Collection Decisions filter selection is invalid.")
        return matches[0]

    def edit_selected(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        rid = int(selection[0])
        try:
            row = self.db.review_rows(limit=5000)
        except Exception:
            messagebox.showerror(
                "Collection Decisions unavailable",
                "Collection Decisions could not be loaded.",
            )
            return
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
                     values=CANONICAL_DECISIONS).grid(row=0,column=1,sticky="ew",pady=6)

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
            try:
                self.db.save_decision(
                    rid,
                    decision.get(),
                    miss.get(),
                    notes.get("1.0", "end").strip(),
                    protected.get(),
                )
            except Exception:
                messagebox.showerror(
                    "Collection Decision unavailable",
                    "The Collection Decision could not be saved. Your editor "
                    "remains open.",
                )
                return
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
                f"Intelligence report created:\n\n{Path(path).name}",
            )

        except Exception:
            messagebox.showerror(
                "Report export failed",
                "The Intelligence report could not be exported.",
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
        try:
            rows = self.db.review_rows(limit=10000)
            export_excel(Path(path), rows)
        except Exception:
            messagebox.showerror(
                "Export failed",
                "The Excel report could not be exported.",
            )
            return
        messagebox.showinfo(
            "Export complete",
            f"Excel report created:\n{Path(path).name}",
        )

    def _restore_session_and_load(self):
        self._session_restoring = True
        session = None
        load_failed = False
        try:
            try:
                if self.session_restoration_service is not None:
                    session = self.session_restoration_service.load()
            except Exception:
                load_failed = True

            navigation_compatible = False
            if session is not None:
                navigation_compatible = self._session_project_matches(session)
                self._apply_session_geometry(session)
                if navigation_compatible:
                    self.observation_source_var.set(
                        _SOURCE_LABELS[session.observation_source]
                    )
                    self.queue_filter_var.set(
                        _QUEUE_FILTER_LABELS[session.queue_filter]
                    )
                    self._last_queue_filter = self.queue_filter_var.get()
                    self.priority_var.set(
                        _PRIORITY_FILTER_LABELS[
                            session.decision_priority_filter
                        ]
                    )
                    self.decision_filter_var.set(
                        _DECISION_FILTER_LABELS[session.decision_state_filter]
                    )

            self.search_var.set("")
            self.refresh_dashboard()
            queue_identity = (
                session.selected_queue_item_id
                if session is not None and navigation_compatible
                else None
            )
            self.refresh_weekend_review_queue(queue_identity)
            self.load_table()

            if session is not None and navigation_compatible:
                self._restore_session_navigation(session)
                self._restore_session_selections(session)
            if load_failed:
                self.status_var.set(
                    "Previous session settings could not be restored."
                )
        finally:
            self._session_restoring = False
            self._record_normal_geometry()

    def _session_project_matches(self, session):
        if (
            session.active_project_id is None
            or self.project_management is None
        ):
            return False
        try:
            active = self.project_management.active_project()
        except Exception:
            return False
        return (
            active is not None
            and active.project_id == session.active_project_id
        )

    def _restore_session_selections(self, session):
        selected_observation = session.selected_observation
        section = self._observation_section()
        if (
            selected_observation is not None
            and selected_observation.source is session.observation_source
            and section.status is ObservationSectionStatus.AVAILABLE
        ):
            self._render_observations(selected_observation)
        else:
            self.observation_tree.selection_remove(
                *self.observation_tree.selection()
            )
            self._show_observation_detail(None)

        queue_item_id = session.selected_queue_item_id
        if (
            queue_item_id is not None
            and self.queue_tree.exists(str(queue_item_id))
        ):
            self.queue_tree.selection_set(str(queue_item_id))
            self.queue_tree.see(str(queue_item_id))
            try:
                item = self.collector_review_service.get(queue_item_id)
            except Exception:
                item = None
            if item is not None:
                self._load_queue_item(item)
            else:
                self.queue_tree.selection_remove(
                    *self.queue_tree.selection()
                )
                self._load_queue_item(None)
        elif self.queue_tree.selection():
            self.queue_tree.selection_remove(*self.queue_tree.selection())
            self._load_queue_item(None)

        release_id = session.selected_decision_release_id
        if release_id is not None and self.tree.exists(str(release_id)):
            self.tree.selection_set(str(release_id))
            self.tree.see(str(release_id))
        elif self.tree.selection():
            self.tree.selection_remove(*self.tree.selection())

    def _restore_session_navigation(self, session):
        review_tabs = {
            CollectionReviewDestination.OBSERVATIONS: self.observations_tab,
            CollectionReviewDestination.WEEKEND_REVIEW_QUEUE: self.queue_tab,
            CollectionReviewDestination.COLLECTION_DECISIONS:
                self.decisions_tab,
        }
        review_tab = review_tabs[session.collection_review_destination]
        self.collection_review_tabs.select(review_tab)
        self._last_collection_review_destination = review_tab
        top_tabs = {
            TopLevelDestination.PROJECT: self.project_tab,
            TopLevelDestination.DASHBOARD: self.dashboard_tab,
            TopLevelDestination.COLLECTION_REVIEW: self.review_tab,
        }
        self.tabs.select(top_tabs[session.top_level_destination])

    def _apply_session_geometry(self, session):
        try:
            self.update_idletasks()
            bounds = (
                self.winfo_vrootx(),
                self.winfo_vrooty(),
                self.winfo_vrootwidth(),
                self.winfo_vrootheight(),
            )
        except tk.TclError:
            bounds = None
        width, height, x, y = _sanitize_geometry(
            session.window_width,
            session.window_height,
            session.window_x,
            session.window_y,
            bounds,
        )
        if x is None or y is None:
            geometry_values = (f"{width}x{height}",)
        else:
            geometry_values = (
                f"{width}x{height}{x:+d}{y:+d}",
                f"{width}x{height}",
            )
        for geometry_value in geometry_values:
            try:
                self.geometry(geometry_value)
            except tk.TclError:
                continue
            self._last_normal_geometry = (
                width,
                height,
                session.window_x if x is None else x,
                session.window_y if y is None else y,
            )
            break

    def _record_normal_geometry(self, event=None):
        if event is not None and getattr(event, "widget", self) is not self:
            return
        try:
            if self.state() != "normal":
                return
            try:
                full_screen = bool(self.attributes("-fullscreen"))
            except tk.TclError:
                full_screen = False
            if full_screen:
                return
            self.update_idletasks()
            candidate = (
                self.winfo_width(),
                self.winfo_height(),
                self.winfo_x(),
                self.winfo_y(),
            )
        except tk.TclError:
            return
        if _valid_normal_geometry(candidate):
            self._last_normal_geometry = candidate

    def _capture_session(self):
        self._record_normal_geometry()
        width, height, x, y = self._last_normal_geometry
        active_project_id = None
        if self.project_management is not None:
            try:
                active = self.project_management.active_project()
            except Exception:
                active = None
            if active is not None:
                active_project_id = active.project_id
        return DesktopSessionCapture(
            active_project_id,
            width,
            height,
            x,
            y,
            self._top_level_destination(),
            self._collection_review_destination(),
            self._observation_source(),
            _enum_for_label(
                self.queue_filter_var.get(),
                _QUEUE_FILTER_LABELS,
            ),
            _enum_for_label(
                self._canonical_session_filter_label(
                    self.priority_var.get(),
                    self.__dict__.get(
                        "_priority_filter_choices",
                        review_filter_choices(ReviewFilterField.PRIORITY, ()),
                    ),
                ),
                _PRIORITY_FILTER_LABELS,
            ),
            _enum_for_label(
                self._canonical_session_filter_label(
                    self.decision_filter_var.get(),
                    self.__dict__.get(
                        "_decision_filter_choices",
                        review_filter_choices(ReviewFilterField.DECISION, ()),
                    ),
                ),
                _DECISION_FILTER_LABELS,
            ),
            self._selected_observation_identity(),
            _selected_positive_tree_id(self.queue_tree),
            _selected_positive_tree_id(self.tree),
        )

    @staticmethod
    def _canonical_session_filter_label(
        label: str,
        choices: tuple[ReviewFilterChoice, ...],
    ) -> str:
        selected = next(
            (choice for choice in choices if choice.label == label),
            None,
        )
        if selected is None:
            raise SessionValidationError(
                "Desktop session filter cannot be captured."
            )
        return (
            "All"
            if selected.kind is ReviewFilterChoiceKind.RETAINED
            else selected.label
        )

    def _top_level_destination(self):
        selected = _selected_notebook_widget(self.tabs)
        if selected is self.dashboard_tab:
            return TopLevelDestination.DASHBOARD
        if selected is self.review_tab:
            return TopLevelDestination.COLLECTION_REVIEW
        if selected is self.project_tab:
            return TopLevelDestination.PROJECT
        raise SessionValidationError(
            "Desktop session destination cannot be captured."
        )

    def _collection_review_destination(self):
        selected = _selected_notebook_widget(self.collection_review_tabs)
        if selected is self.queue_tab:
            return CollectionReviewDestination.WEEKEND_REVIEW_QUEUE
        if selected is self.decisions_tab:
            return CollectionReviewDestination.COLLECTION_DECISIONS
        if selected is self.observations_tab:
            return CollectionReviewDestination.OBSERVATIONS
        raise SessionValidationError(
            "Desktop session destination cannot be captured."
        )

    def _confirm_close_without_session(self):
        result = {"close": False}
        dialog = tk.Toplevel(self)
        dialog.title("Session could not be saved")
        dialog.transient(self)
        dialog.resizable(False, False)
        ttk.Label(
            dialog,
            text=(
                "The current window and navigation state could not be saved."
            ),
            padding=18,
        ).pack()
        actions = ttk.Frame(dialog, padding=(18, 0, 18, 18))
        actions.pack(fill="x")

        def close_without_saving():
            result["close"] = True
            dialog.destroy()

        ttk.Button(
            actions,
            text="Close Without Saving",
            command=close_without_saving,
        ).pack(side="left", padx=(0, 8))
        ttk.Button(
            actions,
            text="Stay Open",
            command=dialog.destroy,
        ).pack(side="left")
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        dialog.grab_set()
        self.wait_window(dialog)
        return result["close"]

    def _close_database_and_root(self):
        try:
            self.db.close()
        except Exception:
            messagebox.showerror(
                "Unable to close",
                "The application database could not be closed. "
                "The application will remain open.",
            )
            return False
        self.destroy()
        return True

    def _register_close_handlers(self):
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        try:
            windowing_system = self.tk.call("tk", "windowingsystem")
        except tk.TclError:
            return
        if windowing_system == "aqua":
            self.createcommand("::tk::mac::Quit", self.on_close)

    def on_close(self):
        if self.__dict__.get("_collector_run_active", False):
            messagebox.showinfo(
                "Collector Run active",
                "The Collector Run must finish before the application can close.",
            )
            return
        if not self._confirm_unsaved_queue_note():
            return
        service = self.__dict__.get("session_restoration_service")
        if service is not None:
            try:
                service.save(self._capture_session())
            except Exception:
                if not self._confirm_close_without_session():
                    return
        self._close_database_and_root()


def _sanitize_geometry(width, height, x, y, bounds):
    width = min(max(width, MIN_WINDOW_WIDTH), MAX_WINDOW_DIMENSION)
    height = min(max(height, MIN_WINDOW_HEIGHT), MAX_WINDOW_DIMENSION)
    if (
        bounds is None
        or len(bounds) != 4
        or any(type(value) is not int for value in bounds)
        or bounds[2] <= 0
        or bounds[3] <= 0
    ):
        return width, height, None, None
    root_x, root_y, root_width, root_height = bounds
    width = max(MIN_WINDOW_WIDTH, min(width, root_width))
    height = max(MIN_WINDOW_HEIGHT, min(height, root_height))
    root_right = root_x + root_width
    root_bottom = root_y + root_height
    visible_width = max(0, min(x + width, root_right) - max(x, root_x))
    visible_height = max(0, min(y + height, root_bottom) - max(y, root_y))
    if visible_width < 160 or visible_height < 64:
        x = root_x + (root_width - width) // 2
        y = root_y + (root_height - height) // 2
    return width, height, x, y


def _valid_normal_geometry(value):
    width, height, x, y = value
    return (
        type(width) is int
        and MIN_WINDOW_WIDTH <= width <= MAX_WINDOW_DIMENSION
        and type(height) is int
        and MIN_WINDOW_HEIGHT <= height <= MAX_WINDOW_DIMENSION
        and type(x) is int
        and MIN_COORDINATE <= x <= MAX_COORDINATE
        and type(y) is int
        and MIN_COORDINATE <= y <= MAX_COORDINATE
    )


def _enum_for_label(label, mapping):
    matches = tuple(
        enum_value for enum_value, value in mapping.items() if value == label
    )
    if len(matches) != 1:
        raise SessionValidationError(
            "Desktop session selection cannot be captured."
        )
    return matches[0]


def _selected_notebook_widget(notebook):
    try:
        selected = notebook.select()
        if not selected:
            raise SessionValidationError(
                "Desktop session destination cannot be captured."
            )
        return notebook.nametowidget(selected)
    except SessionValidationError:
        raise
    except Exception as exc:
        raise SessionValidationError(
            "Desktop session destination cannot be captured."
        ) from exc


def _selected_positive_tree_id(tree):
    selection = tree.selection()
    if not selection:
        return None
    try:
        value = int(selection[0])
    except Exception as exc:
        raise SessionValidationError(
            "Desktop session selection cannot be captured."
        ) from exc
    if value <= 0:
        raise SessionValidationError(
            "Desktop session selection cannot be captured."
        )
    return value


if __name__ == "__main__":
    App().mainloop()
