"""
formatter.py
Takes the structured data dict and formats it into a clean .txt file
matching the slide layout structure shown in the TCS template.
"""

from datetime import datetime


def section(title: str, char: str = "=") -> str:
    line = char * len(title)
    return f"\n{line}\n{title}\n{line}\n"


def format_output(data: dict, company_name: str) -> str:
    lines = []
    current_year = datetime.now().year

    # ── Header ─────────────────────────────────────────────────────────────
    lines.append("=" * 60)
    lines.append(f"  COMPANY RESEARCH BRIEF")
    lines.append(f"  {data.get('company_name', company_name).upper()}")
    lines.append(f"  Generated: {datetime.now().strftime('%B %d, %Y')}")
    lines.append("=" * 60)

    # ── 1. Key Facts ───────────────────────────────────────────────────────
    lines.append(section("1. KEY FACTS"))
    lines.append(f"Founded              : {data.get('founded', 'N/A')}")
    lines.append(f"Parent Organization  : {data.get('parent_organization', 'N/A')}")
    lines.append(f"Headquarters         : {data.get('headquarters', 'N/A')}")
    lines.append(f"No. of Employees     : {data.get('num_employees', 'N/A')}")
    lines.append(f"Industry             : {data.get('industry', 'N/A')}")

    key_people = data.get("key_people", [])
    if key_people:
        lines.append("\nKey People:")
        for person in key_people:
            lines.append(f"  - {person.get('name', '')} — {person.get('role', '')}")

    # ── 2. Business Description ────────────────────────────────────────────
    lines.append(section("2. BUSINESS DESCRIPTION"))
    lines.append(data.get("business_description", "N/A"))

    # ── 3. Therapeutic Areas ───────────────────────────────────────────────
    lines.append(section("3. THERAPEUTIC AREAS"))
    for area in data.get("therapeutic_areas", []):
        lines.append(f"  • {area}")

    # ── 4. Key Subsidiaries ────────────────────────────────────────────────
    lines.append(section("4. KEY SUBSIDIARIES"))
    for sub in data.get("subsidiaries", []):
        lines.append(f"  • {sub}")

    # ── 5. Revenue (Last 3 Years) ──────────────────────────────────────────
    lines.append(section("5. REVENUE (LAST 3 YEARS — USD BILLIONS)"))
    revenue = data.get("revenue_usd_billions", {})
    for year in sorted(revenue.keys()):
        val = revenue[year]
        if val is not None:
            lines.append(f"  {year}  :  ${float(val):.2f}B")
        else:
            lines.append(f"  {year}  :  Not available")
    cagr = data.get("revenue_cagr_3yr_pct")
    if cagr is not None:
        lines.append(f"\n  3-Year CAGR  :  {float(cagr):.2f}%")
    lines.append("\n  [See attached revenue chart PNG for bar graph]")

    # ── 6. Blockbuster Drugs (Last 5 Years) ───────────────────────────────
    yr_cutoff_5 = current_year - 5
    lines.append(section(f"6. NEW BLOCKBUSTER DRUGS (Last 5 Years: {yr_cutoff_5}–{current_year})"))
    drugs = data.get("blockbuster_drugs_last_5yr", [])
    if drugs:
        for drug in drugs:
            abbr = f" ({drug.get('abbreviation', '')})" if drug.get("abbreviation") else ""
            lines.append(f"  • {drug.get('drug_name', '')} ({drug.get('year_launched', '')})")
            lines.append(f"    Disease Area : {drug.get('disease_area', '')}{abbr}")
    else:
        lines.append("  No blockbuster drugs launched in this period.")

    # ── 7. Pipeline & Approvals (Last 5 Years) ─────────────────────────────
    lines.append(section(f"7. PIPELINE & APPROVALS (Last 5 Years: {yr_cutoff_5}–{current_year})"))
    pipeline = data.get("pipeline_approvals_last_5yr", [])
    if pipeline:
        for item in pipeline:
            lines.append(f"  • {item.get('drug_name', '')} ({item.get('year', '')})")
            lines.append(f"    Status     : {item.get('status', '')}")
            lines.append(f"    Indication : {item.get('indication', '')}")
    else:
        lines.append("  No significant pipeline/approvals data in this period.")

    # ── 8. MedTech & Innovation (Last 5 Years) ─────────────────────────────
    lines.append(section(f"8. MEDTECH & INNOVATION (Last 5 Years: {yr_cutoff_5}–{current_year})"))
    medtech = data.get("medtech_innovation_last_5yr", [])
    if medtech:
        for item in medtech:
            lines.append(f"  • {item.get('initiative', '')} ({item.get('year', '')})")
            lines.append(f"    {item.get('description', '')}")
    else:
        lines.append("  No significant MedTech/Innovation activity in this period.")

    # ── 9. Acquisitions (Last 2 Years) ────────────────────────────────────
    yr_cutoff_2 = current_year - 2
    lines.append(section(f"9. ACQUISITIONS (Last 2 Years: {yr_cutoff_2}–{current_year})"))
    acquisitions = data.get("acquisitions_last_2yr", [])
    if acquisitions:
        for acq in acquisitions:
            lines.append(f"  • {acq.get('company', '')} — {acq.get('date', '')}")
            lines.append(f"    Value   : {acq.get('value_usd', 'Undisclosed')}")
            lines.append(f"    Purpose : {acq.get('purpose', '')}")
    else:
        lines.append("  No significant acquisitions in this period.")

    # ── 10. Partnerships (Last 2 Years) ────────────────────────────────────
    lines.append(section(f"10. PARTNERSHIPS (Last 2 Years: {yr_cutoff_2}–{current_year})"))
    partnerships = data.get("partnerships_last_2yr", [])
    if partnerships:
        for p in partnerships:
            lines.append(f"  • {p.get('partner', '')} — {p.get('date', '')}")
            lines.append(f"    Value : {p.get('value_usd', 'Undisclosed')}")
            lines.append(f"    Focus : {p.get('focus', '')}")
    else:
        lines.append("  No significant partnerships in this period.")

    # ── Footer ─────────────────────────────────────────────────────────────
    lines.append("\n" + "=" * 60)
    lines.append("  END OF BRIEF")
    lines.append("=" * 60 + "\n")

    return "\n".join(lines)
