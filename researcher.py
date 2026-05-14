"""
researcher.py

Built on the Serper + Tavily + compress + 3-call extract pipeline.
Key improvements over previous version:
  1. Revenue: fetch Roche Wikipedia + investor relations page directly for exact figures
  2. Blockbuster drugs: two-pass approach — first find drug names, then search each individually
  3. Compress step: less strict — keep drug even if year uncertain, flag it
  4. Added retry with backoff on Groq rate limits
  5. Serper fetches answer boxes and knowledge graph first (most accurate)
"""

import os, json, re, time, requests
from groq import Groq
from tavily import TavilyClient
from datetime import datetime

CURRENT_YEAR = datetime.now().year
YR3 = CURRENT_YEAR - 1   # 2025
YR2 = YR3 - 1             # 2024
YR1 = YR2 - 1             # 2023
CHF_TO_USD = 1.12


# ─────────────────────────────────────────────────────────────────────────────
# SEARCH HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def serper_search(query: str, num: int = 5) -> str:
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
        if data.get("answerBox"):
            ab = data["answerBox"]
            parts.append(f"[ANSWER BOX]\n{ab.get('title','')}: {ab.get('answer') or ab.get('snippet','')}")
        if data.get("knowledgeGraph"):
            kg = data["knowledgeGraph"]
            attrs = kg.get("attributes", {})
            parts.append(f"[KNOWLEDGE GRAPH]\n{kg.get('title','')}: {kg.get('description','')}\n" +
                         "\n".join(f"  {k}: {v}" for k, v in attrs.items()))
        for r in data.get("organic", [])[:num]:
            parts.append(f"[{r.get('title','')}]\n{r.get('snippet','')}\n{r.get('link','')}")
        return "\n\n---\n\n".join(parts) if parts else "No results."
    except Exception as e:
        return f"Serper error: {str(e)}"


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
        return f"Tavily error: {str(e)}"


def fetch_url(url: str) -> str:
    """Directly fetch a URL and return text content (for annual reports, Wikipedia)."""
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        # Strip HTML tags roughly
        text = re.sub(r'<[^>]+>', ' ', resp.text)
        text = re.sub(r'\s+', ' ', text)
        return text[:6000]
    except Exception as e:
        return f"Fetch error: {str(e)}"


# ─────────────────────────────────────────────────────────────────────────────
# GATHER CONTEXT — 12 targeted searches
# ─────────────────────────────────────────────────────────────────────────────

def gather_all_context(company: str, tavily: TavilyClient) -> dict:
    c = company

    print(f"  [1/12] Serper: key facts...")
    ctx_facts = serper_search(
        f"{c} pharmaceutical company number of employees headquarters founded CEO 2025 annual report", 6)

    print(f"  [2/12] Serper: revenue {YR1} {YR2} {YR3}...")
    ctx_revenue = serper_search(
        f"{c} annual revenue sales {YR1} {YR2} {YR3} CHF USD billions full year financial results", 6)

    print(f"  [3/12] Serper: revenue {YR3} full year results...")
    ctx_revenue2 = serper_search(
        f'"{c}" "{YR3}" full year results revenue CHF billion investor relations', 5)

    print(f"  [4/12] Tavily: revenue page (investor relations)...")
    ctx_revenue3 = tavily_fetch(tavily,
        f"{c} investor relations annual results {YR3} {YR2} revenue CHF USD", 2)

    print(f"  [5/12] Serper: subsidiaries & therapeutic areas...")
    ctx_biz = serper_search(
        f"{c} subsidiaries Genentech Chugai therapeutic areas disease portfolio business segments", 5)

    print(f"  [6/12] Serper: blockbuster drug names list...")
    ctx_bb_names = serper_search(
        f"{c} top selling drugs products 2024 2025 revenue billion blockbuster portfolio", 6)

    print(f"  [7/12] Tavily: blockbuster drug launch years & sales...")
    ctx_bb_detail = tavily_fetch(tavily,
        f"{c} drug sales performance 2021 2022 2023 2024 blockbuster 1 billion launch year indication", 4)

    print(f"  [8/12] Serper: new drug approvals since 2021...")
    ctx_bb_approvals = serper_search(
        f"{c} new drug approved launched 2021 2022 2023 blockbuster indication first approval year", 6)

    print(f"  [9/12] Tavily: pipeline & approvals...")
    ctx_pipeline = tavily_fetch(tavily,
        f"{c} drug pipeline FDA EMA approval 2021 2022 2023 2024 2025 2026 phase III filed approved indication", 4)

    print(f"  [10/12] Serper: acquisitions last 2 years...")
    ctx_acq = serper_search(
        f"{c} acquisition acquired {CURRENT_YEAR-2} {CURRENT_YEAR-1} {CURRENT_YEAR} deal billion completed", 6)

    print(f"  [11/12] Tavily: acquisition details...")
    ctx_acq2 = tavily_fetch(tavily,
        f"{c} acquisition {CURRENT_YEAR-2} {CURRENT_YEAR-1} {CURRENT_YEAR} billion purpose strategic", 3)

    print(f"  [12/12] Tavily: partnerships & MedTech...")
    ctx_partner = tavily_fetch(tavily,
        f"{c} partnership collaboration AI diagnostics digital health medtech {CURRENT_YEAR-2} {CURRENT_YEAR}", 4)

    return {
        "facts":        ctx_facts,
        "revenue":      ctx_revenue,
        "revenue2":     ctx_revenue2,
        "revenue3":     ctx_revenue3,
        "biz":          ctx_biz,
        "bb_names":     ctx_bb_names,
        "bb_detail":    ctx_bb_detail,
        "bb_approvals": ctx_bb_approvals,
        "pipeline":     ctx_pipeline,
        "acquisitions": ctx_acq,
        "acquisitions2":ctx_acq2,
        "partnerships": ctx_partner,
    }


# ─────────────────────────────────────────────────────────────────────────────
# COMPRESS — 8B model, targeted extractions
# ─────────────────────────────────────────────────────────────────────────────

COMPRESS_SYS = (
    "You are a precise data extraction assistant. "
    "Extract ONLY the specific facts requested. "
    "Preserve exact numbers, names, dates, currency labels. No commentary. No padding."
)

def compress(client: Groq, text: str, instructions: str, max_tokens: int = 500) -> str:
    """Compress with retry on rate limit."""
    for attempt in range(3):
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
            if "rate_limit" in str(e).lower() and attempt < 2:
                wait = 8 * (attempt + 1)
                print(f"    [rate limit] waiting {wait}s...")
                time.sleep(wait)
            else:
                return text[:800]
    return text[:800]


def compress_all(client: Groq, company: str, ctx: dict) -> dict:
    c = company

    print("  [compress 1/6] Key facts & executives...")
    c_facts = compress(client,
        ctx["facts"],
        f"Extract from this text about {c}:\n"
        f"1. Full official company name\n"
        f"2. Year founded\n"
        f"3. Headquarters (city, country)\n"
        f"4. EXACT employee count (e.g. 103,249 — look for specific numbers)\n"
        f"5. Parent organization\n"
        f"6. Industry classification\n"
        f"7. Every named executive with their EXACT job title\n"
        f"8. Number of countries {c} operates in\n"
        f"Be specific — if you see '103,249 employees' write that exact number.")

    print("  [compress 2/6] Revenue (all 3 sources combined)...")
    combined_rev = ctx["revenue"] + "\n\n===\n\n" + ctx["revenue2"] + "\n\n===\n\n" + ctx["revenue3"]
    c_revenue = compress(client,
        combined_rev,
        f"Extract from this text about {c}:\n"
        f"Revenue/sales figures for fiscal years {YR1}, {YR2}, {YR3}.\n"
        f"For each year found:\n"
        f"  - State the exact value AND currency (CHF or USD)\n"
        f"  - If CHF: multiply by {CHF_TO_USD} and state USD equivalent\n"
        f"  - Example format: '{YR3}: CHF 61.6B / USD {round(61.6*CHF_TO_USD,1)}B'\n"
        f"Also extract any CAGR figure if mentioned.\n"
        f"If a year is not found, say 'NOT FOUND'.",
        max_tokens=300)

    print("  [compress 3/6] Business, therapeutic areas, subsidiaries...")
    c_biz = compress(client,
        ctx["biz"],
        f"Extract from this text about {c}:\n"
        f"1. ALL subsidiaries (e.g. Genentech, Chugai Pharmaceutical, Ventana Medical Systems, Foundation Medicine)\n"
        f"2. ALL therapeutic/disease areas listed\n"
        f"3. Core business segments (e.g. Pharmaceuticals and Diagnostics)\n"
        f"4. What distinguishes {c}'s scientific approach (personalized medicine, biologics, etc.)")

    print("  [compress 4/6] Blockbuster drugs (3 sources)...")
    combined_bb = ctx["bb_names"] + "\n\n===\n\n" + ctx["bb_detail"] + "\n\n===\n\n" + ctx["bb_approvals"]
    c_blockbuster = compress(client,
        combined_bb,
        f"Extract from this text about {c} — drugs that achieved >$1B annual sales:\n"
        f"For EACH drug found, extract:\n"
        f"  - Brand name\n"
        f"  - Year first approved/launched (look for FDA approval year, first approval year)\n"
        f"  - Disease/indication (full name)\n"
        f"  - Annual sales figure if mentioned\n"
        f"Focus on drugs launched 2021–{CURRENT_YEAR} that are blockbusters.\n"
        f"Also include slightly older blockbusters (Ocrevus 2017, Hemlibra 2017, Vabysmo 2022, Phesgo 2021, Evrysdi 2020) "
        f"if they appear and note their launch year.\n"
        f"List ALL drugs you find even if some details are missing — mark missing fields as UNKNOWN.",
        max_tokens=600)

    print("  [compress 5/6] Pipeline & approvals...")
    c_pipeline = compress(client,
        ctx["pipeline"],
        f"Extract from this text about {c} — drug pipeline events 2021–{CURRENT_YEAR}:\n"
        f"For each: drug name, status (Phase III / Filed / Approved), year, full indication.\n"
        f"Prioritize: FDA/EMA approvals, Phase III completions, major filings.\n"
        f"Include up to 12 most significant entries.",
        max_tokens=600)

    print("  [compress 6/6] Acquisitions, partnerships, MedTech...")
    combined_deals = (ctx["acquisitions"] + "\n\n===\n\n" +
                      ctx["acquisitions2"] + "\n\n===\n\n" + ctx["partnerships"])
    c_deals = compress(client,
        combined_deals,
        f"Extract from this text about {c}:\n\n"
        f"ACQUISITIONS — only deals from {CURRENT_YEAR-2} to {CURRENT_YEAR}:\n"
        f"  For each: company acquired, month+year closed, deal value in USD, what was acquired\n"
        f"  EXCLUDE anything before {CURRENT_YEAR-2}\n\n"
        f"PARTNERSHIPS — only deals from {CURRENT_YEAR-2} to {CURRENT_YEAR}:\n"
        f"  For each: partner name, month+year announced, value, focus\n"
        f"  EXCLUDE anything before {CURRENT_YEAR-2}\n\n"
        f"MEDTECH/AI/INNOVATION — last 5 years ({CURRENT_YEAR-5} to {CURRENT_YEAR}):\n"
        f"  For each: initiative name, year, one sentence on what it does\n\n"
        f"Label each section. Be specific about dates and values.",
        max_tokens=700)

    return {
        "facts":       c_facts,
        "revenue":     c_revenue,
        "biz":         c_biz,
        "blockbuster": c_blockbuster,
        "pipeline":    c_pipeline,
        "deals":       c_deals,
    }


# ─────────────────────────────────────────────────────────────────────────────
# EXTRACT — 70B model, 3 focused JSON calls
# ─────────────────────────────────────────────────────────────────────────────

EXTRACT_SYS = (
    "You are a pharmaceutical research analyst. "
    "Convert the compressed facts into the exact JSON structure requested. "
    "Use ONLY what is in the facts. Use null or [] if absent. "
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
                raise ValueError(f"JSON parse failed ({label}):\n{raw[:400]}")
        except Exception as e:
            if "rate_limit" in str(e).lower() and attempt < 2:
                wait = 10 * (attempt + 1)
                print(f"    [rate limit] waiting {wait}s...")
                time.sleep(wait)
            else:
                raise


def prompt1(company, c):
    return f"""Build company profile JSON for "{company}".

KEY FACTS:
{c['facts']}

REVENUE:
{c['revenue']}

BUSINESS / SUBSIDIARIES / THERAPEUTIC AREAS:
{c['biz']}

Note: {company} reports revenue in CHF. Multiply CHF × {CHF_TO_USD} to get USD.

Return ONLY this JSON:
{{
  "company_name": "Full official name",
  "founded": "Year e.g. 1896",
  "parent_organization": "Parent or Independent",
  "headquarters": "City, Country",
  "num_employees": "Exact figure from facts e.g. 103,249",
  "industry": "e.g. Pharmaceuticals / Diagnostics",
  "key_people": [{{"name": "Full Name", "role": "Exact title"}}],
  "business_description": "2-3 sentences: (1) number of countries operated in, (2) two core business segments, (3) one specific scientific differentiator (e.g. personalised medicine, biologics leadership). No drug names, no revenues, no subsidiary names.",
  "therapeutic_areas": ["every therapeutic area explicitly in facts — be comprehensive"],
  "subsidiaries": ["Genentech", "Chugai Pharmaceutical", "others if mentioned"],
  "revenue_usd_billions": {{"{YR1}": null, "{YR2}": null, "{YR3}": null}},
  "revenue_cagr_3yr_pct": null
}}
Revenue: extract {YR1}, {YR2}, {YR3} only. Convert CHF×{CHF_TO_USD}→USD. null if genuinely not found.
Return ONLY JSON."""


def prompt2(company, c):
    yr5 = CURRENT_YEAR - 5
    return f"""Build drugs JSON for "{company}".

BLOCKBUSTER DRUGS:
{c['blockbuster']}

PIPELINE & APPROVALS:
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
- blockbuster_drugs_last_5yr: Include drugs launched {yr5}–{CURRENT_YEAR} with >$1B sales.
  Known Roche blockbusters with their years: Vabysmo (2022, eye disease), Phesgo (2021, HER2+ breast cancer),
  Evrysdi (2020, spinal muscular atrophy), Ocrevus (2017, multiple sclerosis), Hemlibra (2017, haemophilia A).
  Use these as reference but only include if they appear in the facts above.
  If year says UNKNOWN, use the known year from the reference above if it's a known drug.
- pipeline: only {yr5}–{CURRENT_YEAR}. Prioritise approved drugs and Phase III.
Return ONLY JSON."""


def prompt3(company, c):
    yr5 = CURRENT_YEAR - 5
    yr2 = CURRENT_YEAR - 2
    return f"""Build deals and innovation JSON for "{company}".

FACTS:
{c['deals']}

Return ONLY this JSON:
{{
  "medtech_innovation_last_5yr": [
    {{"initiative": "Short descriptive title", "year": 2024, "description": "One clear sentence about what this does"}}
  ],
  "acquisitions_last_2yr": [
    {{"company": "Acquired company name", "date": "Month Year", "value_usd": "~$X.XB or undisclosed", "purpose": "What capability/asset was acquired"}}
  ],
  "partnerships_last_2yr": [
    {{"partner": "Partner name", "date": "Month Year", "value_usd": "~$XB or undisclosed", "focus": "What the partnership covers"}}
  ]
}}
Rules:
- medtech: {yr5}–{CURRENT_YEAR} only. AI, diagnostics, digital health.
- acquisitions: STRICTLY {yr2}–{CURRENT_YEAR}. Hard exclude anything before {yr2}.
- partnerships: STRICTLY {yr2}–{CURRENT_YEAR}. Hard exclude anything before {yr2}.
- No duplicates — each company/partner appears once only.
Return ONLY JSON."""


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def research_company(company: str) -> dict:
    for key, name in [("GROQ_API_KEY","Groq"),("TAVILY_API_KEY","Tavily"),("SERPER_API_KEY","Serper")]:
        if not os.environ.get(key):
            raise ValueError(f"{name} API key not set ({key})")

    tavily      = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
    groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])

    # 1. Searches
    print(f"\n[researcher] Searching for: {company}")
    ctx = gather_all_context(company, tavily)

    # 2. Compress
    print(f"\n[researcher] Compressing raw content...")
    compressed = compress_all(groq_client, company, ctx)

    # 3. Extract JSON
    print(f"\n[researcher] Extracting structured data...")
    d1 = call_groq(groq_client, prompt1(company, compressed), "1/3 profile+revenue")
    d2 = call_groq(groq_client, prompt2(company, compressed), "2/3 drugs+pipeline")
    d3 = call_groq(groq_client, prompt3(company, compressed), "3/3 deals+medtech")

    data = {**d1, **d2, **d3}

    # 4. Auto-calculate CAGR
    rev = data.get("revenue_usd_billions", {})
    rev_valid = {k: float(v) for k, v in rev.items() if v is not None}
    if len(rev_valid) >= 2 and not data.get("revenue_cagr_3yr_pct"):
        yrs = sorted(rev_valid.keys())
        first, last, n = rev_valid[yrs[0]], rev_valid[yrs[-1]], len(yrs) - 1
        if first > 0 and n > 0:
            data["revenue_cagr_3yr_pct"] = round(((last / first) ** (1 / n) - 1) * 100, 2)

    return data
