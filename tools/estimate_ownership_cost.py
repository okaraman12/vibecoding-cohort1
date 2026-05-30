"""estimate_ownership_cost -- deterministic 5-year TCO calculator.

Pure formula, no LLM. Uses category-based heuristics for depreciation rate,
fuel economy, insurance class, and maintenance cost. Returns a JSON breakdown
suitable for the frontend cost card.
"""

from __future__ import annotations

import json

DEFINITION = {
    "type": "function",
    "function": {
        "name": "estimate_ownership_cost",
        "description": (
            "Estimate total cost of ownership for a car over N years. Returns a JSON "
            "breakdown: depreciation, fuel, insurance, maintenance, total. Uses "
            "category-based heuristics (figures are approximate, not quotes)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model":          {"type": "string", "description": "Car model name, used for the report label."},
                "category":       {"type": "string", "enum": ["economy", "compact", "sedan", "suv", "truck", "luxury", "ev", "hybrid"],
                                   "description": "Vehicle class for heuristic lookup."},
                "msrp":           {"type": "number", "description": "Purchase price in USD."},
                "years":          {"type": "integer", "description": "Ownership horizon (1-10)."},
                "annual_mileage": {"type": "integer", "description": "Miles driven per year."},
                "fuel_price":     {"type": "number", "description": "Price per gallon (or per gallon-equivalent for EV). Defaults to 3.80."},
            },
            "required": ["model", "category", "msrp", "years", "annual_mileage"],
        },
    },
}

# Per-category heuristic table:
# (5yr depreciation %, mpg-equivalent, annual insurance USD, annual maintenance USD)
_HEURISTICS = {
    "economy": (0.45, 35, 1400, 700),
    "compact": (0.48, 32, 1500, 800),
    "sedan":   (0.50, 28, 1600, 900),
    "suv":     (0.52, 24, 1750, 1100),
    "truck":   (0.45, 20, 1900, 1300),
    "luxury":  (0.58, 22, 2400, 1900),
    "ev":      (0.55, 110, 1700, 600),   # mpg-e
    "hybrid":  (0.46, 48, 1550, 850),
}


def run(model: str, category: str, msrp: float, years: int, annual_mileage: int,
        fuel_price: float = 3.80) -> str:
    cat = category.lower().strip()
    if cat not in _HEURISTICS:
        cat = "sedan"
    years = max(1, min(10, int(years)))

    dep_pct_5y, mpg, ann_ins, ann_maint = _HEURISTICS[cat]
    # Linearize 5y depreciation to N years (capped at 80% for long horizons)
    dep_pct = min(0.80, dep_pct_5y * (years / 5))
    depreciation = round(msrp * dep_pct, 0)

    total_miles = annual_mileage * years
    fuel_cost = round((total_miles / mpg) * fuel_price, 0) if mpg > 0 else 0
    insurance = round(ann_ins * years, 0)
    maintenance = round(ann_maint * years, 0)
    total = depreciation + fuel_cost + insurance + maintenance

    breakdown = {
        "model": model,
        "category": cat,
        "horizon_years": years,
        "annual_mileage": annual_mileage,
        "msrp": msrp,
        "fuel_price_per_gal": fuel_price,
        "components": [
            {"label": "Depreciation", "amount": depreciation,
             "note": f"~{int(dep_pct*100)}% of MSRP over {years} years"},
            {"label": "Fuel",         "amount": fuel_cost,
             "note": f"{mpg} mpg-eq · {total_miles:,} miles · ${fuel_price:.2f}/gal"},
            {"label": "Insurance",    "amount": insurance,
             "note": f"~${ann_ins}/yr · {cat} class"},
            {"label": "Maintenance",  "amount": maintenance,
             "note": f"~${ann_maint}/yr · {cat} class"},
        ],
        "total":         total,
        "cost_per_mile": round(total / total_miles, 3) if total_miles else 0,
        "disclaimer":    "Heuristic estimate. Real costs vary by region, driver profile, and trim.",
    }
    return json.dumps(breakdown, ensure_ascii=False, indent=2)
