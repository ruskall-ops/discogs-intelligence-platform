
from __future__ import annotations
from pathlib import Path
import xlsxwriter

from dip.experience.results_presentation import (
    PresentationSurface,
    PresentationTerm,
    presentation_label,
)

def export_excel(path: Path, rows):
    wb = xlsxwriter.Workbook(path)
    ws = wb.add_worksheet("Review")
    title = wb.add_format({
        "bold": True, "font_size": 18, "font_color": "white",
        "bg_color": "#1F4E78"
    })
    header = wb.add_format({
        "bold": True, "font_color": "white", "bg_color": "#305496",
        "border": 1, "text_wrap": True
    })
    money = wb.add_format({"num_format": "£#,##0.00"})
    score = wb.add_format({"num_format": "0.0"})
    note = wb.add_format({"font_color": "#666666", "italic": True})

    columns = [
        ("Release ID", "release_id"), ("Decision", "decision"),
        ("Would I Miss It?", "miss_rating"), ("Protected", "protected"),
        ("Priority", "priority"), ("Sell Window", "sell_window"),
        ("Opportunity", "opportunity_score"), ("Value", "value_score"),
        ("Demand", "demand_score"), ("Liquidity", "liquidity_score"),
        ("Momentum", "momentum_score"), ("Artist", "artist"),
        ("Title", "title"), ("Label", "label"), ("Catalog#", "catalog_no"),
        ("Wants", "wants"), ("Haves", "haves"),
        ("For Sale", "copies_for_sale"), ("Lowest Price", "lowest_price"),
        ("Why highlighted", "explanation"), ("Personal Notes", "personal_notes"),
        ("Discogs", "discogs_uri"),
    ]

    legacy_title = presentation_label(
        PresentationTerm.LEGACY_COLLECTOR_RUN_REVIEW_ANALYSIS,
        PresentationSurface.LEGACY_EXCEL,
    )
    ws.merge_range(
        0, 0, 0, len(columns)-1,
        f"Discogs Intelligence Platform — {legacy_title}", title,
    )
    ws.write(
        1,
        0,
        "Legacy scores, wants, scarcity, rankings, movers, and percentages are "
        "unchanged. SQLite remains the source of truth.",
        note,
    )

    for c, (label, _) in enumerate(columns):
        ws.write(3, c, label, header)

    for r, row in enumerate(rows, start=4):
        for c, (_, key) in enumerate(columns):
            value = row[key] if key in row.keys() else ""
            if key == "lowest_price":
                ws.write_number(r, c, float(value or 0), money)
            elif key.endswith("_score"):
                ws.write_number(r, c, float(value or 0), score)
            elif key == "discogs_uri" and value:
                ws.write_url(r, c, value, string="Open release")
            else:
                ws.write(r, c, value)

    widths = [11,16,17,10,22,18,12,10,10,10,10,25,38,20,15,10,10,10,13,55,32,14]
    for i, width in enumerate(widths):
        ws.set_column(i, i, width)
    ws.freeze_panes(4, 11)
    ws.autofilter(3, 0, 3 + len(rows), len(columns)-1)
    ws.conditional_format(4, 6, 3+len(rows), 10, {
        "type": "3_color_scale",
        "min_color": "#F8696B", "mid_color": "#FFEB84", "max_color": "#63BE7B"
    })
    wb.close()
