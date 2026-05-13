"""
researcher.py

Dual-search pipeline:
  - Serper (Google results)  for precise factual queries (revenue, employees, drug dates)
  - Tavily (full page fetch)  for rich content (pipeline, deals, MedTech)
  - 8B model compresses raw content → dense facts
  - 70B model extracts structured JSON (3 focused calls, under 12k TPM each)
"""

import os, json, re, time, requests
from groq import Groq
from tavily import TavilyClient
from datetime import datetime

CURRENT_YEAR = datetime.now().year
YR3 = CURRENT_YEAR - 1   # 2025
YR2 = YR3 - 1             # 2024
YR1 = YR2 - 1             # 2023

CHF_TO_USD = 1.12  # approximate conversion


# ─────────────────────────────────────────────────────────────────────────────
# SEARCH HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def serper_search(query: str, num: int = 5) -> str:
    """
    Google search via Serper API.
    Returns title + snippet + link for top results.
    Best for: precise facts, numbers, dates — Google indexes annual reports well.
    """
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        return "Serper API key not set."
    try:
        resp = requests.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num},
            timeout=15
        )
        data = resp.json()
        parts = []
        # Answer box (often has exact number)
        if data.get("answerBox"):
            ab = data["answerBox"]
            parts.append(f"[ANSWER BOX]\n{ab.get('title','')}: {ab.get('answer') or ab.get('snippet','')}")
        # Knowledge graph
        if data.get("knowledgeGraph"):
            kg = data["knowledgeGraph"]
            desc = kg.get("description","")
            attrs = kg.get("attributes",{})
            parts.append(f"[KNOWLEDGE GRAPH]\n{kg.get('title','')}: {desc}\n" +
                         "\n".join(f"  {k}: {v}" for k,v in attrs.items()))
        # Organic results
        for r in data.get("organic", [])[:num]:
            parts.append(f"[{r.get('title','')}]\n{r.get('snippet','')}\n{r.get('link','')}")
        return "\n\n---\n\n".join(parts) if parts else "No results."
    except Exception as e:
        return f"Serper error: {str(e)}"


def tavily_fetch(tavily: TavilyClient, query: str, max_results: int = 3) -> str:
    """
    Tavily with raw_content=True — fetches full page text.
    Best for: detailed pipeline info, acquisition details, MedTech descriptions.
    """
    try:
        resp = tavily.search(query=query, max_results=max_results,
                             search_depth="advanced", include_raw_content=True)
        parts = []
        for r in resp.get("results", []):
            title   = r.get("title", "")
            content = r.get("raw_content") or r.get("content", "")
            url     = r.get("url", "")
            parts.append(f"[{title}]\n{content[:1800]}\n({url})")
        return "\n\n====\n\n".join(parts) if parts else "No results."
    except Exception as e:
        return f"Tavily error: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# GATHER CONTEXT  — 10 targeted searches across both APIs
# ─────────────────────────────────────────────────────────────────────────────

def gather_all_context(company: str, tavily: TavilyClient) -> dict:
    c = company
    print(f"  [1/10] Serper: key facts (employees, founded, HQ)...")
    ctx_facts = serper_search(
        f"{c} pharmaceutical company employees headquarters founded parent CEO 2025", 6)

    print(f"  [2/10] Serper: revenue {YR1} {YR2} {YR3}...")
    ctx_revenue = serper_search(
        f"{c} annual revenue {YR1} {YR2} {YR3} CHF USD billions full year results", 6)

    print(f"  [3/10] Serper: revenue cross-check...")
    ctx_revenue2 = serper_search(
        f"{c} {YR3} full year sales results financial highlights CHF billion", 5)

    print(f"  [4/10] Serper: subsidiaries & therapeutic areas...")
    ctx_biz = serper_search(
        f"{c} subsidiaries therapeutic areas disease areas business segments 2024 2025", 5)

    print(f"  [5/10] Serper: blockbuster drugs launch year sales...")
    ctx_blockbuster = serper_search(
        f"{c} blockbuster drugs billion sales 2021 2022 2023 2024 2025 launch year approval indication", 6)

    print(f"  [6/10] Tavily: blockbuster drugs detail...")
    ctx_blockbuster2 = tavily_fetch(tavily,
        f"{c} new drugs launched 2021 2022 2023 2024 sales exceed 1 billion indication approval year", 3)

    print(f"  [7/10] Tavily: pipeline & approvals...")
    ctx_pipeline = tavily_fetch(tavily,
        f"{c} drug pipeline FDA EMA approval 2021 2022 2023 2024 2025 2026 phase III filed approved", 4)

    print(f"  [8/10] Serper: acquisitions last 2 years...")
    ctx_acq = serper_search(
        f"{c} acquisition acquired {CURRENT_YEAR-2} {CURRENT_YEAR-1} {CURRENT_YEAR} deal billion", 6)

    print(f"  [9/10] Tavily: acquisitions detail...")
    ctx_acq2 = tavily_fetch(tavily,
        f"{c} acquisition deal {CURRENT_YEAR-2} {CURRENT_YEAR-1} {CURRENT_YEAR} billion purpose", 3)

    print(f"  [10/10] Tavily: partnerships & MedTech...")
    ctx_partner = tavily_fetch(tavily,
        f"{c} partnership collaboration AI diagnostics medtech {CURRENT_YEAR-2} {CURRENT_YEAR-1} {CURRENT_YEAR}", 4)

    return {
        "facts":        ctx_facts,
        "revenue":      ctx_revenue,
        "revenue2":     ctx_revenue2,
        "biz":          ctx_biz,
        "blockbuster":  ctx_blockbuster,
        "blockbuster2": ctx_blockbuster2,
        "pipeline":     ctx_pipeline,
        "acquisitions": ctx_acq,
        "acquisitions2":ctx_acq2,
        "partnerships": ctx_partner,
    }


# ─────────────────────────────────────────────────────────────────────────────
# COMPRESS — 8B model strips noise, keeps only needed facts
# ─────────────────────────────────────────────────────────────────────────────

COMPRESS_SYS = (
    "You are a precise data extraction assistant. "
    "Read the text and extract ONLY the specific facts requested. "
    "Be concise. Preserve exact numbers, names, dates, currency labels. No commentary."
)

def compress(client: Groq, text: str, instructions: str, max_tokens: int = 450) -> str:
    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": COMPRESS_SYS},
                {"role": "user",   "content": f"{instructions}\n\nSOURCE TEXT:\n{text[:5000]}"}
            ],
            temperature=0.0,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        if "rate_limit" in str(e).lower():
            time.sleep(4)
            return text[:600]
        return text[:600]


def compress_all(client: Groq, company: str, ctx: dict) -> dict:
    c = company

    print("  [compress 1/6] Key facts...")
    c_facts = compress(client,
        ctx["facts"],
        f"From this text about {c}, extract:\n"
        f"- Full official company name\n- Year founded\n- Headquarters (city, country)\n"
        f"- Exact number of employees (look for headcount figures like 103,000 etc)\n"
        f"- Parent organization\n- Industry classification\n"
        f"- All named executives with their EXACT titles\n"
        f"- How many countries {c} operates in")

    print("  [compress 2/6] Revenue...")
    c_revenue = compress(client,
        ctx["revenue"] + "\n\n" + ctx["revenue2"],
        f"From this text about {c}, extract:\n"
        f"- Revenue/sales for fiscal years {YR1}, {YR2}, {YR3}\n"
        f"- State the EXACT figure AND the currency (CHF or USD)\n"
        f"- If in CHF: also compute USD equivalent (CHF × {CHF_TO_USD})\n"
        f"- Any mentioned CAGR figures\n"
        f"Format: YEAR: [value] [currency] / USD equiv: [computed]",
        max_tokens=300)

    print("  [compress 3/6] Business segments, therapeutic areas, subsidiaries...")
    c_biz = compress(client,
        ctx["biz"],
        f"From this text about {c}, extract:\n"
        f"- All subsidiaries mentioned (e.g. Genentech, Chugai, etc.)\n"
        f"- All therapeutic/disease areas listed\n"
        f"- Core business segments\n"
        f"- Brief description of scientific approach or differentiator")

    print("  [compress 4/6] Blockbuster drugs...")
    c_blockbuster = compress(client,
        ctx["blockbuster"] + "\n\n" + ctx["blockbuster2"],
        f"From this text about {c}, list drugs that:\n"
        f"1. Were launched/approved between 2021 and {CURRENT_YEAR}\n"
        f"2. Have confirmed annual sales exceeding $1 billion\n"
        f"For each drug include: brand name, EXACT launch/approval year, "
        f"disease/indication, annual sales figure, any abbreviation.\n"
        f"ONLY include if you find all three: name + year + disease. Skip if year is missing.",
        max_tokens=500)

    print("  [compress 5/6] Pipeline...")
    c_pipeline = compress(client,
        ctx["pipeline"],
        f"From this text about {c}, list drug pipeline events from 2021–{CURRENT_YEAR}:\n"
        f"For each: drug name, status (Phase III/Filed/Approved), year, full indication.\n"
        f"Focus on most important/recent approvals and late-stage drugs.",
        max_tokens=500)

    print("  [compress 6/6] Acquisitions & partnerships...")
    c_deals = compress(client,
        ctx["acquisitions"] + "\n\n" + ctx["acquisitions2"] + "\n\n" + ctx["partnerships"],
        f"From this text about {c}, extract:\n"
        f"ACQUISITIONS (only {CURRENT_YEAR-2}–{CURRENT_YEAR}):\n"
        f"  - Company acquired, month+year, deal value in USD, what was acquired/why\n"
        f"PARTNERSHIPS (only {CURRENT_YEAR-2}–{CURRENT_YEAR}):\n"
        f"  - Partner name, month+year, value, focus area\n"
        f"MEDTECH/AI/INNOVATION ({CURRENT_YEAR-5}–{CURRENT_YEAR}):\n"
        f"  - Initiative name, year, one-sentence description\n"
        f"Label each section clearly. Exclude anything before {CURRENT_YEAR-2} for acq/partnerships.",
        max_tokens=600)

    return {
        "facts":      c_facts,
        "revenue":    c_revenue,
        "biz":        c_biz,
        "blockbuster":c_blockbuster,
        "pipeline":   c_pipeline,
        "deals":      c_deals,
    }


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACT — 70B model turns compressed facts into structured JSON
# ─────────────────────────────────────────────────────────────────────────────

EXTRACT_SYS = (
    "You are a pharmaceutical research analyst. "
    "Convert the provided compressed facts into the exact JSON structure requested. "
    "Use ONLY what is stated in the facts. Use null or [] when absent. "
    "Return ONLY valid compact JSON — no markdown, no explanation."
)

def prompt1(company, c):
    return f"""Build the company profile JSON for "{company}" from these facts.

FACTS — KEY INFO:
{c['facts']}

FACTS — REVENUE:
{c['revenue']}

FACTS — BUSINESS / SUBSIDIARIES / THERAPEUTIC AREAS:
{c['biz']}

CHF→USD conversion: multiply CHF value by {CHF_TO_USD}

Return ONLY:
{{
  "company_name": "Full official name",
  "founded": "Year e.g. 1896",
  "parent_organization": "Parent company or Independent",
  "headquarters": "City, Country",
  "num_employees": "Exact or approximate e.g. 103,249 or ~103,000",
  "industry": "e.g. Pharmaceuticals / Diagnostics",
  "key_people": [{{"name": "Full Name", "role": "Exact title"}}],
  "business_description": "2-3 sentences covering: (1) number of countries {company} operates in, (2) its two core business segments, (3) one distinguishing fact about its scientific/research approach. Do NOT mention drug names, revenue figures, or subsidiary names.",
  "therapeutic_areas": ["every area explicitly mentioned in facts"],
  "subsidiaries": ["every subsidiary explicitly mentioned — e.g. Genentech, Chugai Pharmaceutical, Ventana Medical Systems, Foundation Medicine"],
  "revenue_usd_billions": {{"{YR1}": null, "{YR2}": null, "{YR3}": null}},
  "revenue_cagr_3yr_pct": null
}}
Revenue rules: use years {YR1}, {YR2}, {YR3} only. Values must be in USD billions (convert CHF×{CHF_TO_USD} if needed). null if not found.
Return ONLY JSON."""


def prompt2(company, c):
    yr5 = CURRENT_YEAR - 5
    return f"""Build the drugs JSON for "{company}" from these facts.

FACTS — BLOCKBUSTER DRUGS:
{c['blockbuster']}

FACTS — PIPELINE & APPROVALS:
{c['pipeline']}

Return ONLY:
{{
  "blockbuster_drugs_last_5yr": [
    {{"drug_name": "Brand name", "year_launched": 2022, "disease_area": "Full indication name", "abbreviation": "short form or null"}}
  ],
  "pipeline_approvals_last_5yr": [
    {{"drug_name": "Name", "status": "Phase III/Filed/Approved", "year": 2024, "indication": "Full disease name"}}
  ]
}}
Rules:
- blockbuster: ONLY drugs with ALL THREE present: launch year {yr5}–{CURRENT_YEAR}, disease area, confirmed >$1B sales. Omit entire entry if any field missing.
- pipeline: only events {yr5}–{CURRENT_YEAR}. Prioritise approved drugs and phase III.
Return ONLY JSON."""


def prompt3(company, c):
    yr5 = CURRENT_YEAR - 5
    yr2 = CURRENT_YEAR - 2
    return f"""Build the deals and innovation JSON for "{company}" from these facts.

FACTS:
{c['deals']}

Return ONLY:
{{
  "medtech_innovation_last_5yr": [
    {{"initiative": "Short descriptive title", "year": 2024, "description": "One clear sentence"}}
  ],
  "acquisitions_last_2yr": [
    {{"company": "Acquired company name", "date": "Month Year", "value_usd": "~$X.XB or undisclosed", "purpose": "What capability/asset was acquired"}}
  ],
  "partnerships_last_2yr": [
    {{"partner": "Partner name", "date": "Month Year", "value_usd": "~$XB or undisclosed", "focus": "What the partnership covers"}}
  ]
}}
Rules:
- medtech: {yr5}–{CURRENT_YEAR}, AI/diagnostics/digital health only.
- acquisitions: STRICTLY {yr2}–{CURRENT_YEAR} only. Hard exclude anything before {yr2}.
- partnerships: STRICTLY {yr2}–{CURRENT_YEAR} only. Hard exclude anything before {yr2}.
- Do NOT duplicate entries. Each company/partner appears only once.
Return ONLY JSON."""


def call_groq(client: Groq, prompt: str, label: str) -> dict:
    print(f"[researcher] Groq extract {label}...")
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": EXTRACT_SYS},
            {"role": "user",   "content": prompt}
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
        raise ValueError(f"JSON parse failed ({label}):\n{raw[:600]}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def research_company(company: str) -> dict:
    for key, name in [("GROQ_API_KEY","Groq"), ("TAVILY_API_KEY","Tavily"), ("SERPER_API_KEY","Serper")]:
        if not os.environ.get(key):
            raise ValueError(f"{name} API key not set ({key})")

    tavily      = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

    # 1. 10 targeted searches (Serper + Tavily)
    print(f"\n[researcher] Searching for: {company}")
    ctx = gather_all_context(company, tavily)

    # 2. Compress raw content → dense facts (8B model)
    print(f"\n[researcher] Compressing...")
    compressed = compress_all(groq_client, company, ctx)

    # 3. Extract structured JSON (70B model, 3 calls)
    print(f"\n[researcher] Extracting structured data...")
    d1 = call_groq(groq_client, prompt1(company, compressed), "1/3: profile+revenue")
    d2 = call_groq(groq_client, prompt2(company, compressed), "2/3: drugs+pipeline")
    d3 = call_groq(groq_client, prompt3(company, compressed), "3/3: deals+medtech")

    data = {**d1, **d2, **d3}

    # 4. Auto-calculate CAGR if missing
    rev = data.get("revenue_usd_billions", {})
    rev_valid = {k: float(v) for k, v in rev.items() if v is not None}
    if len(rev_valid) >= 2 and not data.get("revenue_cagr_3yr_pct"):
        yrs = sorted(rev_valid.keys())
        first, last, n = rev_valid[yrs[0]], rev_valid[yrs[-1]], len(yrs) - 1
        if first > 0 and n > 0:
            data["revenue_cagr_3yr_pct"] = round(((last / first) ** (1 / n) - 1) * 100, 2)

    return data
