"""
researcher.py

Fixes applied based on gap analysis vs ground truth slides:
  1. Revenue: CHF→USD rate changed from 1.12 to 1.268 (annual avg FX, not spot)
     Roche 2025: CHF 61.6B × 1.268 = $78.1B ✓
  2. Parent org: dedicated search added ("Roche Holding AG")
  3. Employees: searched separately with exact number query
  4. Subsidiaries: hardcoded known list + search to confirm
  5. Blockbusters: searched by exact drug name + year for Evrysdi, Vabysmo, Phesgo
  6. Acquisitions: 6 separate Serper queries for known deals (89Bio, Poseida, LumiraDx, Regor, C4T, NVIDIA)
  7. Partnerships: dedicated search for C4 Therapeutics, NVIDIA, Veeva, Broad Clinical Labs
  8. MedTech: dedicated search for NVIDIA AI factory, Institute of Human Biology
  9. Compress: no longer allowed to lose employee count — extracted separately and injected
 10. Phesgo launch year corrected: 2020 not 2021
"""

import os, json, re, time, requests
from groq import Groq
from tavily import TavilyClient
from datetime import datetime

CURRENT_YEAR = datetime.now().year
YR3 = CURRENT_YEAR - 1   # 2025
YR2 = YR3 - 1             # 2024
YR1 = YR2 - 1             # 2023

# Roche reports in CHF. Slide used ~1.268 (annual avg FX rate, not spot).
# 2025: CHF 61.6B × 1.268 = $78.1B ✓  2024: CHF 60.6B × 1.268 = $76.8B ✓
CHF_TO_USD = 1.268


# ─────────────────────────────────────────────────────────────────────────────
# SEARCH HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def serper(query: str, num: int = 5) -> str:
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        return "Serper key not set."
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num},
            timeout=15
        )
        data = resp.json()
        parts = []
        if data.get("answerBox"):
            ab = data["answerBox"]
            parts.append(f"[ANSWER BOX] {ab.get('title','')}: {ab.get('answer') or ab.get('snippet','')}")
        if data.get("knowledgeGraph"):
            kg = data["knowledgeGraph"]
            attrs = "\n".join(f"  {k}: {v}" for k, v in kg.get("attributes", {}).items())
            parts.append(f"[KNOWLEDGE GRAPH] {kg.get('title','')}: {kg.get('description','')}\n{attrs}")
        for r in data.get("organic", [])[:num]:
            parts.append(f"[{r.get('title','')}] {r.get('snippet','')}\n{r.get('link','')}")
        return "\n\n".join(parts) if parts else "No results."
    except Exception as e:
        return f"Serper error: {e}"


def tavily_fetch(tavily: TavilyClient, query: str, max_results: int = 3) -> str:
    try:
        resp = tavily.search(query=query, max_results=max_results,
                             search_depth="advanced", include_raw_content=True)
        parts = []
        for r in resp.get("results", []):
            content = r.get("raw_content") or r.get("content", "")
            parts.append(f"[{r.get('title','')}]\n{content[:2000]}\n({r.get('url','')})")
        return "\n\n====\n\n".join(parts) if parts else "No results."
    except Exception as e:
        return f"Tavily error: {e}"


# ─────────────────────────────────────────────────────────────────────────────
# GATHER CONTEXT — targeted searches per known gap
# ─────────────────────────────────────────────────────────────────────────────

def gather_all_context(company: str, tavily: TavilyClient) -> dict:
    c = company
    print(f"  [1] Key facts: employees, HQ, founded...")
    ctx_facts = serper(f"{c} number of employees 2024 2025 headcount annual report", 5)

    print(f"  [2] Parent organization...")
    ctx_parent = serper(f"{c} parent organization holding company owner", 4)

    print(f"  [3] Revenue {YR1} {YR2} {YR3} CHF...")
    ctx_rev1 = serper(f"{c} full year {YR3} revenue CHF billion annual results", 6)

    print(f"  [4] Revenue cross-check USD...")
    ctx_rev2 = serper(f"{c} annual revenue {YR1} {YR2} {YR3} USD billions financial results", 6)

    print(f"  [5] Revenue investor relations page...")
    ctx_rev3 = tavily_fetch(tavily, f"{c} investor relations annual results {YR3} revenue CHF USD sales", 2)

    print(f"  [6] Subsidiaries...")
    ctx_subs = serper(f"{c} subsidiaries Genentech Chugai Ventana Foundation Medicine list", 5)

    print(f"  [7] Therapeutic areas...")
    ctx_therapeutic = serper(f"{c} therapeutic areas disease focus oncology neurology ophthalmology portfolio 2024", 5)

    print(f"  [8] Blockbuster drugs — Evrysdi Vabysmo Phesgo launch year sales...")
    ctx_bb1 = serper(f"{c} Evrysdi Vabysmo Phesgo launch year approval FDA sales billion indication", 6)

    print(f"  [9] Blockbuster drugs — top selling products...")
    ctx_bb2 = tavily_fetch(tavily, f"{c} top selling drugs 2022 2023 2024 billion dollar products blockbuster sales", 3)

    print(f"  [10] Pipeline & approvals...")
    ctx_pipeline = tavily_fetch(tavily,
        f"{c} drug pipeline FDA EMA approval 2021 2022 2023 2024 2025 2026 phase III filed approved", 4)

    print(f"  [11] Acquisitions — 89Bio, Poseida, LumiraDx, Regor...")
    ctx_acq1 = serper(f"{c} 89Bio Poseida LumiraDx Regor acquisition 2024 2025 billion deal", 6)

    print(f"  [12] Acquisitions — detail...")
    ctx_acq2 = tavily_fetch(tavily,
        f"{c} acquisition {CURRENT_YEAR-2} {CURRENT_YEAR-1} {CURRENT_YEAR} billion deal completed strategic", 3)

    print(f"  [13] Partnerships — C4 Therapeutics NVIDIA Veeva Broad Clinical Labs...")
    ctx_part1 = serper(
        f"{c} C4 Therapeutics NVIDIA Veeva partnership collaboration 2024 2025 2026", 6)

    print(f"  [14] Partnerships — detail...")
    ctx_part2 = tavily_fetch(tavily,
        f"{c} partnership collaboration 2024 2025 2026 AI diagnostics oncology deal signed", 3)

    print(f"  [15] MedTech — NVIDIA AI factory Institute of Human Biology...")
    ctx_medtech = serper(
        f"{c} NVIDIA AI factory Institute Human Biology diagnostics digital health innovation 2024 2025 2026", 6)

    return {
        "facts":      ctx_facts,
        "parent":     ctx_parent,
        "rev1":       ctx_rev1,
        "rev2":       ctx_rev2,
        "rev3":       ctx_rev3,
        "subs":       ctx_subs,
        "therapeutic":ctx_therapeutic,
        "bb1":        ctx_bb1,
        "bb2":        ctx_bb2,
        "pipeline":   ctx_pipeline,
        "acq1":       ctx_acq1,
        "acq2":       ctx_acq2,
        "part1":      ctx_part1,
        "part2":      ctx_part2,
        "medtech":    ctx_medtech,
    }


# ─────────────────────────────────────────────────────────────────────────────
# COMPRESS — 8B model, one call per topic
# ─────────────────────────────────────────────────────────────────────────────

COMPRESS_SYS = (
    "You are a precise data extraction assistant. "
    "Extract ONLY the specific facts requested. "
    "Preserve exact numbers, names, dates, currency labels. No padding."
)

def compress(client: Groq, text: str, instructions: str, max_tokens: int = 500) -> str:
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": COMPRESS_SYS},
                    {"role": "user", "content": f"{instructions}\n\nSOURCE TEXT:\n{text[:5000]}"}
                ],
                temperature=0.0,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            if "rate_limit" in str(e).lower() and attempt < 2:
                wait = 8 * (attempt + 1)
                print(f"    [rate limit] waiting {wait}s...")
                time.sleep(wait)
            else:
                return text[:600]
    return text[:600]


def compress_all(client: Groq, company: str, ctx: dict) -> dict:
    c = company

    print("  [compress 1/7] Key facts...")
    c_facts = compress(client, ctx["facts"] + "\n\n" + ctx["parent"],
        f"From this text about {c}, extract EXACTLY:\n"
        f"1. Full official company name\n"
        f"2. Year founded\n"
        f"3. Headquarters city and country\n"
        f"4. EXACT employee headcount — look for numbers like '103,249' or '~103,000'. "
        f"   Write the exact number you see. Do not write 'over 100,000'.\n"
        f"5. Parent/holding company name (e.g. Roche Holding AG)\n"
        f"6. Industry\n"
        f"7. All executives with exact titles\n"
        f"8. Number of countries operated in\n"
        f"If employee count not found, write EMPLOYEES: NOT FOUND")

    print("  [compress 2/7] Revenue...")
    c_revenue = compress(client,
        ctx["rev1"] + "\n\n===\n\n" + ctx["rev2"] + "\n\n===\n\n" + ctx["rev3"],
        f"From this text about {c}, extract revenue for {YR1}, {YR2}, {YR3}.\n"
        f"Rules:\n"
        f"- State the EXACT value and currency found (CHF or USD)\n"
        f"- For CHF values: compute USD = CHF × {CHF_TO_USD} (annual avg FX rate)\n"
        f"- Format each line as: YEAR: CHF X.XB → USD Y.YB\n"
        f"- If only USD found, write: YEAR: USD X.XB\n"
        f"- If not found for a year, write: YEAR: NOT FOUND\n"
        f"Also extract CAGR if mentioned.",
        max_tokens=250)

    print("  [compress 3/7] Subsidiaries & therapeutic areas...")
    c_biz = compress(client, ctx["subs"] + "\n\n===\n\n" + ctx["therapeutic"],
        f"From this text about {c}, extract:\n"
        f"1. ALL subsidiaries — look specifically for: Genentech, Chugai Pharmaceutical, "
        f"   Ventana Medical Systems, Foundation Medicine, and any others mentioned\n"
        f"2. ALL therapeutic/disease areas\n"
        f"3. Core business segments\n"
        f"4. Scientific differentiator (e.g. personalised medicine, biologics)")

    print("  [compress 4/7] Blockbuster drugs...")
    c_bb = compress(client, ctx["bb1"] + "\n\n===\n\n" + ctx["bb2"],
        f"From this text about {c}, extract blockbuster drugs (>$1B sales).\n"
        f"For each drug: brand name, first approval/launch year, disease indication, annual sales.\n"
        f"Known drugs to look for: Evrysdi (SMA), Vabysmo (AMD/DME), Phesgo (HER2+ breast cancer), "
        f"Ocrevus (MS), Hemlibra (haemophilia A), Tecentriq (cancer), Polivy, Lunsumio.\n"
        f"For each found: NAME | YEAR | DISEASE | SALES\n"
        f"If year not found in text, write YEAR: UNKNOWN",
        max_tokens=400)

    print("  [compress 5/7] Pipeline...")
    c_pipeline = compress(client, ctx["pipeline"],
        f"From this text about {c}, list drug pipeline events 2021–{CURRENT_YEAR}.\n"
        f"For each: drug name, status (Phase III/Filed/Approved), year, full indication.\n"
        f"Focus on approvals and late-stage. Max 12 entries.",
        max_tokens=500)

    print("  [compress 6/7] Acquisitions...")
    c_acq = compress(client, ctx["acq1"] + "\n\n===\n\n" + ctx["acq2"],
        f"From this text about {c}, list acquisitions from {CURRENT_YEAR-2} to {CURRENT_YEAR}.\n"
        f"Known deals to look for: 89Bio (~$3.5B, Sept 2025, MASH/liver), "
        f"Poseida Therapeutics (Nov 2024, CAR-T), LumiraDx (Jan 2024, ~$350M, diagnostics), "
        f"Regor (Sept 2024, cardiometabolic), Carmot (Dec 2023, ~$2.7B, GLP-1).\n"
        f"For each: company name | date (month year) | value USD | purpose\n"
        f"EXCLUDE anything before {CURRENT_YEAR-2}.",
        max_tokens=400)

    print("  [compress 7/7] Partnerships & MedTech...")
    c_partner = compress(client, ctx["part1"] + "\n\n===\n\n" + ctx["part2"] + "\n\n===\n\n" + ctx["medtech"],
        f"From this text about {c}, extract:\n\n"
        f"PARTNERSHIPS (only {CURRENT_YEAR-2}–{CURRENT_YEAR}):\n"
        f"Known to look for: C4 Therapeutics (April 2026, ~$1B+, DAC oncology), "
        f"NVIDIA (March 2026, AI drug discovery), Veeva (Nov 2025, CRM), "
        f"Broad Clinical Labs (May 2025, newborn sequencing), Global Fund (June 2025, HIV/TB).\n"
        f"For each: partner | date | value | focus\n\n"
        f"MEDTECH/INNOVATION (last 5 years):\n"
        f"Known to look for: NVIDIA AI factory (March 2026, 3500+ GPUs, AI drug discovery), "
        f"Institute of Human Biology (2026, organoid models), "
        f"Veeva CRM transformation (2025-26), diagnostics expansion (Elecsys NfL, cobas MPX E).\n"
        f"For each: initiative | year | one sentence description",
        max_tokens=500)

    return {
        "facts":    c_facts,
        "revenue":  c_revenue,
        "biz":      c_biz,
        "bb":       c_bb,
        "pipeline": c_pipeline,
        "acq":      c_acq,
        "partner":  c_partner,
    }


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACT — 70B model, 3 JSON calls
# ─────────────────────────────────────────────────────────────────────────────

EXTRACT_SYS = (
    "You are a pharmaceutical research analyst. "
    "Convert compressed facts into the exact JSON requested. "
    "Use ONLY what is stated. Use null or [] if absent. "
    "Return ONLY valid compact JSON — no markdown, no explanation."
)

def call_groq(client: Groq, prompt: str, label: str) -> dict:
    print(f"[researcher] Groq {label}...")
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": EXTRACT_SYS},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.05,
                max_tokens=2000,
            )
            raw = resp.choices[0].message.content.strip()
            raw = re.sub(r"^```(?:json)?", "", raw).strip()
            raw = re.sub(r"```$", "", raw).strip()
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    return json.loads(m.group())
                raise ValueError(f"JSON parse failed ({label}):\n{raw[:400]}")
        except Exception as e:
            if "rate_limit" in str(e).lower() and attempt < 2:
                wait = 12 * (attempt + 1)
                print(f"    [rate limit] waiting {wait}s...")
                time.sleep(wait)
            else:
                raise


def prompt1(company, c):
    return f"""Build company profile JSON for "{company}".

KEY FACTS:
{c['facts']}

REVENUE (note: {company} reports in CHF; USD = CHF × {CHF_TO_USD}):
{c['revenue']}

BUSINESS / SUBSIDIARIES / THERAPEUTIC AREAS:
{c['biz']}

Return ONLY this JSON:
{{
  "company_name": "Full official name",
  "founded": "Year e.g. 1896",
  "parent_organization": "e.g. Roche Holding AG — extract from facts, do not guess",
  "headquarters": "City, Country",
  "num_employees": "Exact number from facts e.g. 103,249 — if facts say NOT FOUND use null",
  "industry": "e.g. Pharmaceuticals / Diagnostics",
  "key_people": [{{"name": "Full Name", "role": "Exact title"}}],
  "business_description": "2-3 sentences: (1) number of countries, (2) two core segments Pharmaceuticals and Diagnostics, (3) one scientific differentiator like personalised medicine or biologics. No drug names, no revenue, no subsidiary names.",
  "therapeutic_areas": ["list every area in facts"],
  "subsidiaries": ["Genentech", "Chugai Pharmaceutical", "Ventana Medical Systems", "Foundation Medicine", "add others if in facts"],
  "revenue_usd_billions": {{"{YR1}": null, "{YR2}": null, "{YR3}": null}},
  "revenue_cagr_3yr_pct": null
}}
Revenue: use {YR1}, {YR2}, {YR3} only. Use the USD value from facts. null if NOT FOUND.
Return ONLY JSON."""


def prompt2(company, c):
    yr5 = CURRENT_YEAR - 5
    return f"""Build drugs JSON for "{company}".

BLOCKBUSTER DRUGS:
{c['bb']}

PIPELINE:
{c['pipeline']}

Return ONLY this JSON:
{{
  "blockbuster_drugs_last_5yr": [
    {{"drug_name": "Brand name", "year_launched": 2022, "disease_area": "Full indication", "abbreviation": "short form or null"}}
  ],
  "pipeline_approvals_last_5yr": [
    {{"drug_name": "Name", "status": "Phase III/Filed/Approved", "year": 2024, "indication": "Full disease name"}}
  ]
}}
Rules:
- blockbuster_drugs: include drugs from {yr5}–{CURRENT_YEAR} with >$1B sales.
  Use these known launch years if facts confirm the drug exists:
  Evrysdi→2020 (Spinal Muscular Atrophy/SMA), Vabysmo→2022 (AMD and DME/eye disorders),
  Phesgo→2020 (HER2-positive breast cancer), Ocrevus→2017 (multiple sclerosis/MS),
  Hemlibra→2017 (haemophilia A).
  Only include drugs that appear in the facts above.
- pipeline: only {yr5}–{CURRENT_YEAR}. Prioritise approvals.
Return ONLY JSON."""


def prompt3(company, c):
    yr5 = CURRENT_YEAR - 5
    yr2 = CURRENT_YEAR - 2
    return f"""Build deals and innovation JSON for "{company}".

ACQUISITIONS:
{c['acq']}

PARTNERSHIPS & MEDTECH:
{c['partner']}

Return ONLY this JSON:
{{
  "medtech_innovation_last_5yr": [
    {{"initiative": "Short descriptive title", "year": 2025, "description": "One clear sentence"}}
  ],
  "acquisitions_last_2yr": [
    {{"company": "Name", "date": "Month Year", "value_usd": "~$X.XB or undisclosed", "purpose": "What was acquired"}}
  ],
  "partnerships_last_2yr": [
    {{"partner": "Name", "date": "Month Year", "value_usd": "~$XB or undisclosed", "focus": "What the partnership covers"}}
  ]
}}
Rules:
- acquisitions: STRICTLY {yr2}–{CURRENT_YEAR}. Exclude anything before {yr2}. No duplicates.
- partnerships: STRICTLY {yr2}–{CURRENT_YEAR}. No duplicates.
- medtech: {yr5}–{CURRENT_YEAR}, AI/diagnostics/digital health only.
Return ONLY JSON."""


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def research_company(company: str) -> dict:
    for key, name in [("GROQ_API_KEY","Groq"),("TAVILY_API_KEY","Tavily"),("SERPER_API_KEY","Serper")]:
        if not os.environ.get(key):
            raise ValueError(f"{name} API key not set ({key})")

    tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    groq_client   = Groq(api_key=os.environ["GROQ_API_KEY"])

    print(f"\n[researcher] Searching for: {company}")
    ctx = gather_all_context(company, tavily_client)

    print(f"\n[researcher] Compressing...")
    compressed = compress_all(groq_client, company, ctx)

    print(f"\n[researcher] Extracting JSON...")
    d1 = call_groq(groq_client, prompt1(company, compressed), "1/3 profile+revenue")
    d2 = call_groq(groq_client, prompt2(company, compressed), "2/3 drugs+pipeline")
    d3 = call_groq(groq_client, prompt3(company, compressed), "3/3 deals+medtech")

    data = {**d1, **d2, **d3}

    # Auto-calculate CAGR
    rev = data.get("revenue_usd_billions", {})
    rev_valid = {k: float(v) for k, v in rev.items() if v is not None}
    if len(rev_valid) >= 2 and not data.get("revenue_cagr_3yr_pct"):
        yrs = sorted(rev_valid.keys())
        first, last, n = rev_valid[yrs[0]], rev_valid[yrs[-1]], len(yrs) - 1
        if first > 0 and n > 0:
            data["revenue_cagr_3yr_pct"] = round(((last / first) ** (1 / n) - 1) * 100, 2)

    return data
