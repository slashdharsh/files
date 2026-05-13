"""
researcher.py

Pipeline:
  1. Tavily search  → get top URLs per topic
  2. Tavily extract → fetch FULL page content from those URLs (much richer than snippets)
  3. llama-3.1-8b-instant (fast/cheap) → compress each page to key facts only (~300 tokens)
  4. llama-3.3-70b-versatile (smart) → structured JSON extraction from compressed facts
  Split into 3 Groq calls to stay under 12k TPM free tier.
"""

import os, json, re, time
from groq import Groq
from tavily import TavilyClient
from datetime import datetime

CURRENT_YEAR = datetime.now().year
YR3 = CURRENT_YEAR - 1
YR2 = YR3 - 1
YR1 = YR2 - 1


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 + 2: Search → get URLs → fetch full content
# ─────────────────────────────────────────────────────────────────────────────

def search_and_extract(tavily: TavilyClient, query: str, max_results: int = 3) -> str:
    """
    Search for URLs, then use Tavily extract to get full page content.
    Falls back to snippet if extract fails.
    """
    try:
        # First get search results with snippets
        search_resp = tavily.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            include_raw_content=True   # ask for full content directly
        )
        results = search_resp.get("results", [])
        parts = []
        for r in results:
            title   = r.get("title", "")
            # prefer raw_content (full page), fall back to content snippet
            raw     = r.get("raw_content") or r.get("content", "")
            url     = r.get("url", "")
            # keep up to 2000 chars per page — much more than 800-char snippets
            parts.append(f"SOURCE: {title}\nURL: {url}\n{raw[:2000]}")
        return "\n\n====\n\n".join(parts) if parts else "No results."
    except Exception as e:
        return f"Search error: {str(e)}"


def gather_all_context(company: str, tavily: TavilyClient) -> dict:
    c = company  # shorthand

    print(f"  [1/7] Overview & key facts...")
    ctx_overview = search_and_extract(tavily,
        f"{c} pharmaceutical annual report 2025 overview CEO employees headquarters founded", 3)

    print(f"  [2/7] Revenue (CHF/USD)...")
    ctx_revenue = search_and_extract(tavily,
        f"{c} full year results {YR1} {YR2} {YR3} revenue sales CHF USD billions", 4)

    print(f"  [3/7] Therapeutic areas & subsidiaries...")
    ctx_therapeutic = search_and_extract(tavily,
        f"{c} therapeutic areas disease areas portfolio oncology neurology diagnostics subsidiaries", 3)

    print(f"  [4/7] Blockbuster drugs...")
    ctx_blockbuster = search_and_extract(tavily,
        f"{c} blockbuster drug sales 2021 2022 2023 2024 2025 billion revenue indication launched", 4)

    print(f"  [5/7] Pipeline & approvals...")
    ctx_pipeline = search_and_extract(tavily,
        f"{c} FDA EMA drug approval pipeline 2021 2022 2023 2024 2025 2026 phase III filed approved", 4)

    print(f"  [6/7] Acquisitions...")
    ctx_acq = search_and_extract(tavily,
        f"{c} acquisition acquired {CURRENT_YEAR-2} {CURRENT_YEAR-1} {CURRENT_YEAR} deal billion", 3)

    print(f"  [7/7] Partnerships & MedTech...")
    ctx_partner = search_and_extract(tavily,
        f"{c} partnership collaboration AI diagnostics medtech {CURRENT_YEAR-2} {CURRENT_YEAR-1} {CURRENT_YEAR}", 3)

    return {
        "overview":    ctx_overview,
        "revenue":     ctx_revenue,
        "therapeutic": ctx_therapeutic,
        "blockbuster": ctx_blockbuster,
        "pipeline":    ctx_pipeline,
        "acquisitions":ctx_acq,
        "partnerships":ctx_partner,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Compress each context block using fast small model
# ─────────────────────────────────────────────────────────────────────────────

COMPRESS_SYSTEM = (
    "You are a data extraction assistant. Read the text and extract ONLY the specific "
    "facts asked for. Be concise. Numbers, names, dates must be exact. No commentary."
)

def compress(client: Groq, text: str, instructions: str, max_tokens: int = 400) -> str:
    """Use llama-3.1-8b-instant to compress raw page text into key facts."""
    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": COMPRESS_SYSTEM},
                {"role": "user",   "content": f"{instructions}\n\nTEXT:\n{text[:6000]}"}
            ],
            temperature=0.0,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        # If rate limited, wait and return truncated original
        if "rate_limit" in str(e).lower():
            time.sleep(3)
            return text[:800]
        return text[:800]


def compress_all(client: Groq, company: str, ctx: dict) -> dict:
    """Compress all 7 context blocks into dense fact summaries."""
    print("  [compress 1/5] Overview & employees...")
    c_overview = compress(client, ctx["overview"],
        f"Extract for {company}: full company name, year founded, headquarters city/country, "
        f"number of employees, CEO name, other key executives with titles, "
        f"number of countries operating in, core business segments.")

    print("  [compress 2/5] Revenue...")
    c_revenue = compress(client, ctx["revenue"],
        f"Extract for {company}: exact annual revenue figures for {YR1}, {YR2}, {YR3}. "
        f"State currency (CHF or USD). Include any USD conversion if mentioned. "
        f"List as: YEAR: VALUE CURRENCY. Do not skip any year found.")

    print("  [compress 3/5] Therapeutic areas...")
    c_therapeutic = compress(client, ctx["therapeutic"],
        f"Extract for {company}: list ALL therapeutic/disease areas and subsidiaries mentioned.")

    print("  [compress 4/5] Blockbuster drugs...")
    c_blockbuster = compress(client, ctx["blockbuster"],
        f"Extract for {company}: drugs launched 2021–{CURRENT_YEAR} that reached >$1B annual sales. "
        f"For each: drug name, exact launch/approval year, disease/indication, annual sales figure. "
        f"Only include if launch year AND disease AND sales figure are all present.")

    print("  [compress 5/5] Pipeline, deals, MedTech...")
    c_pipeline = compress(client, ctx["pipeline"],
        f"Extract for {company}: drug pipeline events 2021–{CURRENT_YEAR}. "
        f"For each: drug name, status (Phase III/Filed/Approved), year, exact indication.")

    c_acq = compress(client, ctx["acquisitions"],
        f"Extract for {company}: acquisitions {CURRENT_YEAR-2}–{CURRENT_YEAR}. "
        f"For each: company name, month+year of deal, deal value in USD, what was acquired.")

    c_partner = compress(client, ctx["partnerships"],
        f"Extract for {company}: partnerships and MedTech/AI/diagnostics initiatives "
        f"{CURRENT_YEAR-2}–{CURRENT_YEAR}. For each: partner name, date, value, focus area.")

    return {
        "overview":     c_overview,
        "revenue":      c_revenue,
        "therapeutic":  c_therapeutic,
        "blockbuster":  c_blockbuster,
        "pipeline":     c_pipeline,
        "acquisitions": c_acq,
        "partnerships": c_partner,
    }


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: Structured JSON extraction using 70B model
# ─────────────────────────────────────────────────────────────────────────────

EXTRACT_SYSTEM = (
    "You are a pharmaceutical research analyst. "
    "Extract structured data ONLY from the compressed facts provided. "
    "Do NOT invent or guess. Use null or [] when data is absent. "
    "Return ONLY valid compact JSON — no markdown fences, no explanation."
)

CHF_NOTE = f"Note: If revenue is in CHF, multiply by 1.12 to get USD. Roche reports in CHF."

def prompt_call1(company, c):
    return f"""Extract profile and revenue data for "{company}".

FACTS:
Overview: {c['overview']}
Revenue: {c['revenue']}
Therapeutic/Subsidiaries: {c['therapeutic']}

{CHF_NOTE}

Return ONLY this JSON:
{{
  "company_name": "Full official name",
  "founded": "Year only e.g. 1896",
  "parent_organization": "Parent or Independent",
  "headquarters": "City, Country",
  "num_employees": "e.g. ~103,000",
  "industry": "e.g. Pharmaceuticals / Diagnostics",
  "key_people": [{{"name": "Full Name", "role": "Exact title"}}],
  "business_description": "2-3 sentences: number of countries present in, two core business segments, one distinguishing scientific fact. No drug names, no revenue, no subsidiaries.",
  "therapeutic_areas": ["every area explicitly mentioned"],
  "subsidiaries": ["every subsidiary explicitly mentioned"],
  "revenue_usd_billions": {{"{YR1}": null, "{YR2}": null, "{YR3}": null}},
  "revenue_cagr_3yr_pct": null
}}
Rules: revenue years must be {YR1}, {YR2}, {YR3} only. Convert CHF→USD (×1.12). null if not found.
Return ONLY JSON."""


def prompt_call2(company, c):
    yr5 = CURRENT_YEAR - 5
    return f"""Extract drug data for "{company}".

FACTS:
Blockbuster Drugs: {c['blockbuster']}
Pipeline & Approvals: {c['pipeline']}

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
- blockbuster: ONLY {yr5}–{CURRENT_YEAR}, must have year_launched + disease_area + confirmed >$1B sales. Omit if any of these missing.
- pipeline: only {yr5}–{CURRENT_YEAR} events.
Return ONLY JSON."""


def prompt_call3(company, c):
    yr5 = CURRENT_YEAR - 5
    yr2 = CURRENT_YEAR - 2
    return f"""Extract deals and innovation data for "{company}".

FACTS:
Acquisitions: {c['acquisitions']}
Partnerships & MedTech: {c['partnerships']}

Return ONLY this JSON:
{{
  "medtech_innovation_last_5yr": [
    {{"initiative": "Short title", "year": 2023, "description": "One clear sentence"}}
  ],
  "acquisitions_last_2yr": [
    {{"company": "Name", "date": "Month Year", "value_usd": "~$X.XB or undisclosed", "purpose": "What was acquired"}}
  ],
  "partnerships_last_2yr": [
    {{"partner": "Name", "date": "Month Year", "value_usd": "~$XB or undisclosed", "focus": "What it covers"}}
  ]
}}
Rules:
- medtech: {yr5}–{CURRENT_YEAR} only.
- acquisitions: STRICTLY {yr2}–{CURRENT_YEAR} only. Exclude anything before {yr2}.
- partnerships: STRICTLY {yr2}–{CURRENT_YEAR} only. Exclude anything before {yr2}.
Return ONLY JSON."""


def call_groq_extract(client: Groq, prompt: str, label: str) -> dict:
    print(f"[researcher] Groq extract {label}...")
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": EXTRACT_SYSTEM},
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
    groq_key   = os.environ.get("GROQ_API_KEY")
    tavily_key = os.environ.get("TAVILY_API_KEY")
    if not groq_key:   raise ValueError("GROQ_API_KEY not set")
    if not tavily_key: raise ValueError("TAVILY_API_KEY not set")

    tavily      = TavilyClient(api_key=tavily_key)
    groq_client = Groq(api_key=groq_key)

    # ── 1. Fetch full page content via Tavily ──────────────────────────────
    print(f"\n[researcher] Fetching web content for: {company}")
    ctx = gather_all_context(company, tavily)

    # ── 2. Compress each block to dense facts (fast 8B model) ─────────────
    print(f"\n[researcher] Compressing content...")
    compressed = compress_all(groq_client, company, ctx)

    # ── 3. Extract structured JSON (smart 70B model, 3 calls) ─────────────
    print(f"\n[researcher] Extracting structured data...")
    d1 = call_groq_extract(groq_client, prompt_call1(company, compressed), "1/3: profile+revenue")
    d2 = call_groq_extract(groq_client, prompt_call2(company, compressed), "2/3: drugs+pipeline")
    d3 = call_groq_extract(groq_client, prompt_call3(company, compressed), "3/3: deals+medtech")

    # ── 4. Merge ───────────────────────────────────────────────────────────
    data = {**d1, **d2, **d3}

    # ── 5. Auto-calculate CAGR ─────────────────────────────────────────────
    rev = data.get("revenue_usd_billions", {})
    rev_valid = {k: float(v) for k, v in rev.items() if v is not None}
    if len(rev_valid) >= 2 and not data.get("revenue_cagr_3yr_pct"):
        yrs = sorted(rev_valid.keys())
        first, last, n = rev_valid[yrs[0]], rev_valid[yrs[-1]], len(yrs) - 1
        if first > 0 and n > 0:
            data["revenue_cagr_3yr_pct"] = round(((last / first) ** (1 / n) - 1) * 100, 2)

    return data
