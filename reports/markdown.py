from __future__ import annotations

from decimal import Decimal

from .models import IntelligenceReport, ReportMover


def render_markdown(report: IntelligenceReport) -> str:
    """Render a structured intelligence report as Markdown."""

    lines: list[str] = [
        f"# {report.title}",
        "",
        f"Generated: {report.generated_at:%Y-%m-%d %H:%M:%S}",
        "",
        "## Collection Summary",
        "",
        f"- Unique releases: {report.collection.unique_releases:,}",
        f"- Owned copies: {report.collection.owned_copies:,}",
        f"- High-priority reviews: {report.collection.high_priority:,}",
        f"- Worth reviewing: {report.collection.worth_reviewing:,}",
        f"- Hot now: {report.collection.hot_now:,}",
        f"- Protected / Keep: {report.collection.protected:,}",
        "",
        "## Latest Analysis Run",
        "",
    ]

    if report.latest_run is None:
        lines.extend(
            [
                "No completed marketplace analysis run is available.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"- Run ID: {report.latest_run.run_id}",
                f"- Status: {report.latest_run.status}",
                f"- Started: {report.latest_run.started_at}",
                f"- Completed: {report.latest_run.completed_at or 'Not completed'}",
                f"- Releases attempted: {report.latest_run.releases_attempted:,}",
                f"- Releases succeeded: {report.latest_run.releases_succeeded:,}",
                f"- Releases failed: {report.latest_run.releases_failed:,}",
                "",
            ]
        )

    lines.extend(
        [
            "## Historical Comparison",
            "",
        ]
    )

    if report.historical is None:
        lines.extend(
            [
                "At least two completed marketplace runs are required "
                "for historical comparison.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                f"- Latest run: {report.historical.latest_run_id}",
                f"- Previous run: {report.historical.previous_run_id}",
                f"- Releases compared: {report.historical.total_comparisons:,}",
                f"- Changed: {report.historical.changed:,}",
                f"- Unchanged: {report.historical.unchanged:,}",
                f"- Newly observed: {report.historical.new:,}",
                f"- Missing from latest run: {report.historical.missing:,}",
                f"- Percentage changed: {report.historical.percent_changed:.2f}%",
                "",
            ]
        )

    _append_movers(
        lines,
        "Top Price Movers",
        report.top_price_movers,
    )
    _append_movers(
        lines,
        "Top Demand Movers",
        report.top_demand_movers,
    )
    _append_movers(
        lines,
        "Top Scarcity Movers",
        report.top_scarcity_movers,
    )

    lines.extend(
        [
            "---",
            "",
            "*This report presents observed marketplace changes only. "
            "It does not provide buy or sell recommendations.*",
            "",
        ]
    )

    return "\n".join(lines)


def _append_movers(
    lines: list[str],
    heading: str,
    movers: list[ReportMover],
) -> None:
    lines.extend(
        [
            f"## {heading}",
            "",
        ]
    )

    if not movers:
        lines.extend(
            [
                "No qualifying movers were identified.",
                "",
            ]
        )
        return

    lines.extend(
        [
            "| Release | Artist | Title | Wants Δ | For Sale Δ | Price Δ | Price % Δ |",
            "|---:|---|---|---:|---:|---:|---:|",
        ]
    )

    for mover in movers:
        lines.append(
            "| "
            f"{mover.release_id} | "
            f"{_escape(mover.artist)} | "
            f"{_escape(mover.title)} | "
            f"{_signed_integer(mover.wants_change)} | "
            f"{_signed_integer(mover.copies_for_sale_change)} | "
            f"{_signed_decimal(mover.lowest_price_change)} | "
            f"{_signed_percent(mover.lowest_price_percent_change)} |"
        )

    lines.append("")


def _signed_integer(value: int | None) -> str:
    if value is None:
        return "—"

    return f"{value:+,}"


def _signed_decimal(value: Decimal | None) -> str:
    if value is None:
        return "—"

    return f"{value:+.2f}"


def _signed_percent(value: Decimal | None) -> str:
    if value is None:
        return "—"

    return f"{value:+.2f}%"


def _escape(value: str) -> str:
    return value.replace("|", r"\|")