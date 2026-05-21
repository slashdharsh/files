"""
researcher.py — Generic pharma research tool.
Works for ANY company. Zero hardcoded company names, drug names, or person names.
Pipeline: Serper + Tavily search → 8B compress → 70B extract JSON
"""

import os, json, re, time, requests
from groq import Groq
from tavily import TavilyClient
from datetime import datetime

CURRENT_YEAR = datetime.now().year
YR3 = CURRENT_YEAR - 1
YR2 = YR3 - 1
YR1 = YR2 - 1


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
# GATHER CONTEXT — all queries use only the company variable, nothing hardcoded
# ─────────────────────────────────────────────────────────────────────────────

def gather_all_context(company: str, tavily: TavilyClient) -> dict:
    c = company

    print(f"  [1] Key facts: employees, HQ, founded...")
    ctx_facts = serper(f"{c} pharmaceutical company number of employees headquarters founded year 2024 2025", 5)

    print(f"  [2] Parent organization...")
    ctx_parent = serper(f"{c} parent organization holding company owner corporate structure", 4)

    print(f"  [3] Executive leadership — full names and titles...")
    ctx_people = serper(f"{c} CEO CFO CMO executive leadership team full name title 2024 2025", 6)

    print(f"  [4] Executive detail page...")
    ctx_people2 = tavily_fetch(tavily,
        f"{c} executive leadership team board of directors full name exact job title 2024 2025", 2)

    print(f"  [5] Revenue {YR3}...")
    ctx_rev1 = serper(f"{c} full year {YR3} annual revenue sales billion results", 6)

    print(f"  [6] Revenue {YR2}...")
    ctx_rev2 = serper(f"{c} full year {YR2} annual revenue sales billion results", 6)

    print(f"  [7] Revenue {YR1}...")
    ctx_rev3 = serper(f"{c} full year {YR1} annual revenue sales billion results", 5)

    print(f"  [8] Revenue investor relations...")
    ctx_rev4 = tavily_fetch(tavily,
        f"{c} investor relations full year results {YR3} {YR2} {YR1} revenue annual sales", 2)

    print(f"  [9] Subsidiaries...")
    ctx_subs = serper(f"{c} subsidiaries divisions owned companies list", 5)

    print(f"  [10] Therapeutic areas...")
    ctx_therapeutic = serper(f"{c} therapeutic areas disease focus portfolio oncology 2024 2025", 5)

    print(f"  [11] Blockbuster drugs — top selling products...")
    ctx_bb1 = serper(f"{c} top selling drugs products 2024 2025 billion dollar sales revenue blockbuster", 6)

    print(f"  [12] Blockbuster drugs — recent launches...")
    ctx_bb2 = tavily_fetch(tavily,
        f"{c} new drug launched approved 2020 2021 2022 2023 blockbuster billion sales indication", 3)

    print(f"  [13] Pipeline & approvals...")
    ctx_pipeline = tavily_fetch(tavily,
        f"{c} drug pipeline FDA EMA approval 2021 2022 2023 2024 2025 2026 phase III filed approved indication", 4)

    print(f"  [14] Acquisitions last 2 years...")
    ctx_acq1 = serper(f"{c} acquisition acquired deal {CURRENT_YEAR-2} {CURRENT_YEAR-1} {CURRENT_YEAR} billion completed", 6)
    ctx_acq2 = tavily_fetch(tavily,
        f"{c} acquisition {CURRENT_YEAR-2} {CURRENT_YEAR-1} {CURRENT_YEAR} billion deal completed strategic purpose", 3)

    print(f"  [15] Partnerships & MedTech...")
    ctx_part1 = serper(f"{c} partnership collaboration deal signed {CURRENT_YEAR-2} {CURRENT_YEAR-1} {CURRENT_YEAR}", 6)
    ctx_part2 = tavily_fetch(tavily,
        f"{c} partnership collaboration AI diagnostics digital health innovation {CURRENT_YEAR-2} {CURRENT_YEAR}", 3)
    ctx_medtech = serper(f"{c} AI artificial intelligence digital health diagnostics innovation technology {CURRENT_YEAR-4} {CURRENT_YEAR}", 5)

    return {
        "facts":       ctx_facts,
        "parent":      ctx_parent,
        "people":      ctx_people,
        "people2":     ctx_people2,
        "rev1":        ctx_rev1,
        "rev2":        ctx_rev2,
        "rev3":        ctx_rev3,
        "rev4":        ctx_rev4,
        "subs":        ctx_subs,
        "therapeutic": ctx_therapeutic,
        "bb1":         ctx_bb1,
        "bb2":         ctx_bb2,
        "pipeline":    ctx_pipeline,
        "acq1":        ctx_acq1,
        "acq2":        ctx_acq2,
        "part1":       ctx_part1,
        "part2":       ctx_part2,
        "medtech":     ctx_medtech,
    }


# ─────────────────────────────────────────────────────────────────────────────
# COMPRESS — 8B model. Generic instructions, no company-specific hints.
# ─────────────────────────────────────────────────────────────────────────────

COMPRESS_SYS = (
    "You are a precise data extraction assistant. "
    "Extract ONLY the specific facts requested from the source text. "
    "Preserve exact numbers, names, dates, currency labels. No padding or commentary."
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

    print("  [compress 1/7] Key facts + executives...")
    people_text = (ctx["facts"] + "\n\n===\n\n" + ctx["parent"] +
                   "\n\n===\n\n" + ctx["people"] + "\n\n===\n\n" + ctx["people2"])
    c_facts = compress(client, people_text,
        f"From this text about {c}, extract:\n"
        f"1. Full official company name\n"
        f"2. Year founded\n"
        f"3. Headquarters city and country\n"
        f"4. EXACT employee headcount — find a specific number like '89,900' or '103,249'. "
        f"Write only the exact number. If you see a range or approximation, write the number as stated.\n"
        f"5. Parent or holding company name\n"
        f"6. Industry classification\n"
        f"7. Number of countries the company operates in\n"
        f"8. EXECUTIVES: For every executive mentioned, write their FULL first and last name "
        f"and their EXACT job title as stated in the text. "
        f"Format: FULL NAME | EXACT TITLE\n"
        f"If employee count not found anywhere, write: EMPLOYEES: NOT FOUND",
        max_tokens=700)

    print("  [compress 2/7] Revenue...")
    combined_rev = (ctx["rev1"] + "\n\n===\n\n" + ctx["rev2"] +
                    "\n\n===\n\n" + ctx["rev3"] + "\n\n===\n\n" + ctx["rev4"])
    c_revenue = compress(client, combined_rev,
        f"From this text about {c}, extract annual revenue/sales figures.\n"
        f"Find figures for these specific years: {YR1}, {YR2}, {YR3}.\n"
        f"Rules:\n"
        f"- State the EXACT value and currency as written (USD, GBP, EUR, CHF, etc.)\n"
        f"- If in a foreign currency, also note the USD equivalent if mentioned\n"
        f"- Format: YEAR: VALUE CURRENCY (e.g. 2024: $45.8B USD  or  2024: CHF 38.2B)\n"
        f"- If a year is not found, write: YEAR: NOT FOUND\n"
        f"Also note the reporting currency if consistently mentioned.",
        max_tokens=300)

    print("  [compress 3/7] Subsidiaries & therapeutic areas...")
    c_biz = compress(client, ctx["subs"] + "\n\n===\n\n" + ctx["therapeutic"],
        f"From this text about {c}, extract:\n"
        f"1. ALL subsidiary companies and divisions mentioned\n"
        f"2. ALL therapeutic areas and disease categories listed\n"
        f"3. Core business segments\n"
        f"4. Key scientific or strategic differentiator",
        max_tokens=400)

    print("  [compress 4/7] Blockbuster drugs...")
    c_bb = compress(client, ctx["bb1"] + "\n\n===\n\n" + ctx["bb2"],
        f"From this text about {c}, list every drug that has achieved blockbuster status "
        f"(annual sales exceeding $1 billion USD).\n"
        f"For each drug found, extract:\n"
        f"- Brand name\n"
        f"- Year first approved or launched (FDA or EMA first approval year)\n"
        f"- Disease or indication treated\n"
        f"- Annual sales figure if mentioned\n"
        f"Format each as: DRUG NAME | LAUNCH YEAR | DISEASE | SALES\n"
        f"If launch year is not in text, write YEAR: UNKNOWN\n"
        f"Include ALL drugs mentioned, even if some details are missing.",
        max_tokens=500)

    print("  [compress 5/7] Pipeline...")
    c_pipeline = compress(client, ctx["pipeline"],
        f"From this text about {c}, list drug pipeline events from 2021 to {CURRENT_YEAR}.\n"
        f"For each entry: drug name (brand or code name), status (Phase III / Filed / Approved), "
        f"year of the event, full disease indication.\n"
        f"Prioritise: FDA/EMA approvals and late-stage (Phase III) candidates.\n"
        f"List up to 12 most significant entries.",
        max_tokens=500)

    print("  [compress 6/7] Acquisitions...")
    c_acq = compress(client, ctx["acq1"] + "\n\n===\n\n" + ctx["acq2"],
        f"From this text about {c}, list acquisitions completed between "
        f"{CURRENT_YEAR-2} and {CURRENT_YEAR}.\n"
        f"For each: acquired company name | month and year of deal | deal value in USD | "
        f"what capability or asset was acquired\n"
        f"IMPORTANT: Exclude any deals from before {CURRENT_YEAR-2}.",
        max_tokens=400)

    print("  [compress 7/7] Partnerships & MedTech...")
    c_partner = compress(client,
        ctx["part1"] + "\n\n===\n\n" + ctx["part2"] + "\n\n===\n\n" + ctx["medtech"],
        f"From this text about {c}, extract:\n\n"
        f"PARTNERSHIPS (only {CURRENT_YEAR-2}–{CURRENT_YEAR}):\n"
        f"For each: partner name | month+year announced | deal value | what the partnership covers\n"
        f"Exclude any partnerships before {CURRENT_YEAR-2}.\n\n"
        f"MEDTECH/AI/INNOVATION (last 5 years, {CURRENT_YEAR-5}–{CURRENT_YEAR}):\n"
        f"For each: initiative name | year | one sentence describing what it does\n"
        f"Focus on: AI, machine learning, digital health, diagnostics technology, data platforms.",
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
# EXTRACT — 70B model, 3 focused JSON calls. No hardcoded company references.
# ─────────────────────────────────────────────────────────────────────────────

EXTRACT_SYS = (
    "You are a pharmaceutical research analyst. "
    "Convert the compressed facts into the exact JSON structure requested. "
    "Use ONLY what is stated in the facts provided. Use null or [] if absent. "
    "Return ONLY valid compact JSON — no markdown fences, no explanation."
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
    return f"""Build company profile JSON for "{company}" using ONLY the facts below.
Do NOT use any prior knowledge about this company.

KEY FACTS & EXECUTIVES:
{c['facts']}

REVENUE:
{c['revenue']}

BUSINESS / SUBSIDIARIES / THERAPEUTIC AREAS:
{c['biz']}

Return ONLY this JSON:
{{
  "company_name": "Full official name as stated in facts",
  "founded": "Year as stated in facts",
  "parent_organization": "Parent/holding company as stated in facts, or Independent if none",
  "headquarters": "City, Country as stated",
  "num_employees": "Exact number from facts — null if NOT FOUND",
  "industry": "As stated in facts",
  "key_people": [{{"name": "Full first and last name", "role": "Exact title as stated"}}],
  "business_description": "2-3 sentences using only what is in the facts: number of countries operated in, core business segments, one scientific or strategic differentiator. No drug names, no revenue figures, no subsidiary names.",
  "therapeutic_areas": ["every therapeutic area listed in facts"],
  "subsidiaries": ["every subsidiary listed in facts"],
  "revenue_usd_billions": {{"{YR1}": null, "{YR2}": null, "{YR3}": null}},
  "revenue_cagr_3yr_pct": null
}}
Revenue notes:
- Use ONLY years {YR1}, {YR2}, {YR3}
- If revenue is in USD already, use as-is
- If revenue is in GBP: multiply by 1.27 to get USD
- If revenue is in EUR: multiply by 1.09 to get USD
- If revenue is in CHF: multiply by 1.27 to get USD
- Use null for any year genuinely not found
Return ONLY JSON."""


def prompt2(company, c):
    yr5 = CURRENT_YEAR - 5
    return f"""Build drugs JSON for "{company}" using ONLY the facts below.
Do NOT use any prior knowledge about this company's drugs.

BLOCKBUSTER DRUGS:
{c['bb']}

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
- blockbuster_drugs_last_5yr: ONLY include drugs that BOTH (a) appear in the facts above AND
  (b) have >$1B annual sales. Launch years must be from the facts — do not guess.
  Only include entries where you have drug name + launch year + disease from the facts.
- pipeline_approvals_last_5yr: only events from {yr5} to {CURRENT_YEAR}.
  Prioritise approved drugs and Phase III candidates.
Return ONLY JSON."""


def prompt3(company, c):
    yr5 = CURRENT_YEAR - 5
    yr2 = CURRENT_YEAR - 2
    return f"""Build deals and innovation JSON for "{company}" using ONLY the facts below.
Do NOT use any prior knowledge about this company's deals.

ACQUISITIONS:
{c['acq']}

PARTNERSHIPS & MEDTECH:
{c['partner']}

Return ONLY this JSON:
{{
  "medtech_innovation_last_5yr": [
    {{"initiative": "Short descriptive title", "year": 2024, "description": "One clear sentence"}}
  ],
  "acquisitions_last_2yr": [
    {{"company": "Name", "date": "Month Year", "value_usd": "~$X.XB or undisclosed", "purpose": "What was acquired"}}
  ],
  "partnerships_last_2yr": [
    {{"partner": "Name", "date": "Month Year", "value_usd": "~$XB or undisclosed", "focus": "What the partnership covers"}}
  ]
}}
Rules:
- acquisitions_last_2yr: ONLY deals from {yr2} to {CURRENT_YEAR}. Hard exclude anything earlier. No duplicates.
- partnerships_last_2yr: ONLY from {yr2} to {CURRENT_YEAR}. No duplicates.
- medtech_innovation_last_5yr: {yr5} to {CURRENT_YEAR} only. AI / diagnostics / digital health only.
- Include ONLY what appears in the facts above. Do not add deals from memory.
Return ONLY JSON."""


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def research_company(company: str) -> dict:
    for key, name in [("GROQ_API_KEY", "Groq"), ("TAVILY_API_KEY", "Tavily"), ("SERPER_API_KEY", "Serper")]:
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

    # Auto-calculate CAGR if missing
    rev = data.get("revenue_usd_billions", {})
    rev_valid = {k: float(v) for k, v in rev.items() if v is not None}
    if len(rev_valid) >= 2 and not data.get("revenue_cagr_3yr_pct"):
        yrs = sorted(rev_valid.keys())
        first, last, n = rev_valid[yrs[0]], rev_valid[yrs[-1]], len(yrs) - 1
        if first > 0 and n > 0:
            data["revenue_cagr_3yr_pct"] = round(((last / first) ** (1 / n) - 1) * 100, 2)

    return data