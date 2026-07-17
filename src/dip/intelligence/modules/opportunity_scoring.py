
from __future__ import annotations
import math

def _n(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0

def calculate(current, previous=None):
    wants = _n(current.get("wants"))
    haves = _n(current.get("haves"))
    supply = _n(current.get("copies_for_sale"))
    price = _n(current.get("lowest_price"))

    want_have = wants / max(haves, 1)
    wants_supply = wants / max(supply, 1)

    value = min(100, math.log1p(price) * 21)
    demand = min(100, math.log1p(wants) * 13)
    liquidity = min(100, math.log1p(wants_supply) * 20 + math.log1p(wants) * 5)

    momentum = 0
    changes = []
    if previous:
        old_wants = _n(previous["wants"])
        old_supply = _n(previous["copies_for_sale"])
        old_price = _n(previous["lowest_price"])

        wants_growth = (wants - old_wants) / max(old_wants, 1)
        supply_tightening = (old_supply - supply) / max(old_supply, 1)
        price_growth = (price - old_price) / max(old_price, 1) if old_price else 0

        momentum = max(0, min(100,
            45 * wants_growth + 35 * supply_tightening + 20 * price_growth
        ))

        if wants_growth >= 0.10:
            changes.append(f"Wants rose {wants_growth:.0%}")
        if supply_tightening >= 0.20:
            changes.append(f"supply fell {supply_tightening:.0%}")
        if price_growth >= 0.15:
            changes.append(f"lowest listing rose {price_growth:.0%}")

    opportunity = 0.30 * value + 0.30 * demand + 0.30 * liquidity + 0.10 * momentum

    if momentum >= 35 and price >= 12:
        window = "Hot now"
    elif momentum >= 15:
        window = "Rising"
    elif liquidity >= 70 and price >= 15:
        window = "Liquid / sellable"
    elif value >= 70 and liquidity < 45:
        window = "Valuable but slower"
    else:
        window = "Stable"

    if opportunity >= 75 and price >= 15:
        priority = "High-priority review"
    elif opportunity >= 60 and price >= 10:
        priority = "Worth reviewing"
    elif price >= 20 or liquidity >= 65:
        priority = "Possible candidate"
    else:
        priority = "Low priority"

    reasons = []
    if price >= 20:
        reasons.append(f"current lowest listing {price:.2f}")
    if wants >= 100:
        reasons.append(f"{int(wants):,} people want it")
    if supply <= 5 and wants >= 25:
        reasons.append(f"only {int(supply)} copies currently for sale")
    if wants_supply >= 20:
        reasons.append("strong demand relative to supply")
    reasons.extend(changes)
    explanation = "; ".join(reasons) if reasons else "No standout market signal yet."

    return {
        "value_score": round(value, 1),
        "demand_score": round(demand, 1),
        "liquidity_score": round(liquidity, 1),
        "momentum_score": round(momentum, 1),
        "opportunity_score": round(opportunity, 1),
        "sell_window": window,
        "priority": priority,
        "explanation": explanation,
    }
