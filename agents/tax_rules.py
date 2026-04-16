"""
agents/tax_rules.py
────────────────────
Country-specific tax rules and knowledge bases.
Add new countries by extending COUNTRY_RULES.
"""

from __future__ import annotations

COUNTRY_RULES: dict[str, dict] = {
    "India": {
        "currency": "INR (₹)",
        "tax_year": "April 1 – March 31",
        "regimes": [
            "Old Regime (with deductions)",
            "New Regime (lower slabs, fewer deductions)",
        ],
        "slabs_old": [
            {"range": "0 – 2.5L", "rate": "0%"},
            {"range": "2.5L – 5L", "rate": "5%"},
            {"range": "5L – 10L", "rate": "20%"},
            {"range": "10L+", "rate": "30%"},
        ],
        "slabs_new": [
            {"range": "0 – 3L", "rate": "0%"},
            {"range": "3L – 7L", "rate": "5%"},
            {"range": "7L – 10L", "rate": "10%"},
            {"range": "10L – 12L", "rate": "15%"},
            {"range": "12L – 15L", "rate": "20%"},
            {"range": "15L+", "rate": "30%"},
        ],
        "key_deductions": [
            "Section 80C (up to ₹1.5L): ELSS, LIC, PPF, EPF, NSC, home loan principal",
            "Section 80D: Health insurance premiums (up to ₹25,000 / ₹50,000 for seniors)",
            "Section 24(b): Home loan interest (up to ₹2L for self-occupied property)",
            "Section 80E: Education loan interest (no upper limit)",
            "Section 80G: Charitable donations",
            "Section 80TTA/80TTB: Savings account interest",
            "NPS (Section 80CCD): Additional ₹50,000 over 80C",
            "HRA exemption (salary employees)",
            "Standard deduction: ₹50,000 (salaried/pensioners)",
        ],
        "gst_rates": ["0%", "5%", "12%", "18%", "28%"],
        "risk_flags": [
            "Income > ₹50L triggers wealth tax reporting",
            "Foreign assets must be disclosed in ITR (Schedule FA)",
            "Crypto gains classified as VDA (30% flat tax)",
            "Missing TDS deductions risk penalties",
        ],
        "income_types": [
            "Salary / Pension",
            "House Property",
            "Capital Gains (STCG/LTCG)",
            "Business / Professional",
            "Other Sources",
        ],
    },
    "Australia": {
        "currency": "AUD (A$)",
        "tax_year": "July 1 – June 30",
        "regimes": ["Single progressive scale (no choice of regime)"],
        "slabs": [
            {"range": "0 – $18,200", "rate": "0%"},
            {"range": "$18,201 – $45,000", "rate": "19%"},
            {"range": "$45,001 – $120,000", "rate": "32.5%"},
            {"range": "$120,001 – $180,000", "rate": "37%"},
            {"range": "$180,001+", "rate": "45%"},
        ],
        "key_deductions": [
            "Work-related expenses (tools, uniforms, vehicle, travel)",
            "Home office expenses (fixed rate or actual cost method)",
            "Self-education expenses",
            "Investment property: depreciation, repairs, loan interest",
            "Superannuation contributions",
            "Income protection insurance premiums",
            "Charitable donations to DGR organisations",
        ],
        "risk_flags": [
            "PSI (Personal Services Income) rules may deny deductions",
            "Capital gains discount (50%) only available for assets held 12+ months",
            "Rental property negative gearing rules",
            "Fringe benefits tax on non-cash employer perks",
            "CGT applies when selling overseas assets",
        ],
        "income_types": [
            "Employment income",
            "Investment (dividends, interest, rent)",
            "Capital Gains",
            "Business",
            "Foreign income",
        ],
        "gst_rate": "10% (GST)",
    },
}


def get_country_context(country: str) -> str:
    """Return a textual summary of tax rules for prompting the LLM."""
    rules = COUNTRY_RULES.get(country, {})
    if not rules:
        return f"No built-in tax rules found for {country}. Use general tax analysis principles."

    lines = [f"## {country} Tax Rules\n"]
    lines.append(f"**Currency**: {rules.get('currency', 'N/A')}")
    lines.append(f"**Tax Year**: {rules.get('tax_year', 'N/A')}")

    if "slabs_old" in rules:
        lines.append("\n### Old Regime Slabs")
        for s in rules["slabs_old"]:
            lines.append(f"  - {s['range']}: {s['rate']}")
        lines.append("\n### New Regime Slabs")
        for s in rules["slabs_new"]:
            lines.append(f"  - {s['range']}: {s['rate']}")
    elif "slabs" in rules:
        lines.append("\n### Tax Slabs")
        for s in rules["slabs"]:
            lines.append(f"  - {s['range']}: {s['rate']}")

    lines.append("\n### Key Deductions / Offsets")
    for d in rules.get("key_deductions", []):
        lines.append(f"  - {d}")

    lines.append("\n### Risk Flags")
    for r in rules.get("risk_flags", []):
        lines.append(f"  ⚠ {r}")

    return "\n".join(lines)
