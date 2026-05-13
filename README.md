# 💊 Pharma Company Research Tool

A Streamlit app that takes a pharmaceutical company name and generates:
- A structured `.txt` research brief (slide-ready, 10 sections)
- A revenue bar chart `.png` (last 3 years)

**Architecture: Tavily (live web search) → Groq LLaMA (extraction)**  
No hallucination — every fact is grounded in real web search results.

---

## 📁 Project Structure

```
pharma_research_tool/
├── app.py            # Streamlit UI
├── researcher.py     # Tavily search + Groq LLM data extraction
├── chart.py          # Revenue bar chart generator (matplotlib)
├── formatter.py      # TXT brief formatter
├── requirements.txt
└── README.md
```

---

## 🚀 Setup & Run Locally

### 1. Copy all 6 files into a folder on your machine

### 2. Create a virtual environment (recommended)
```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Get your FREE API keys

**Groq API** (LLM — free):
- Go to: https://console.groq.com
- Sign up → API Keys → Create key

**Tavily API** (web search — free, 1000 searches/month):
- Go to: https://app.tavily.com
- Sign up → copy your API key

### 5. Run the app
```bash
streamlit run app.py
```

### 6. Use the app
- Paste both API keys in the **sidebar**
- Enter a company name (e.g. `Roche`, `Pfizer`, `Novartis`)
- Click **Research Company** (~60 seconds — runs 7 searches)
- Download the `.txt` brief and `.png` chart

---

## 🔍 Why Tavily + Groq?

| Old approach | New approach |
|---|---|
| Ask LLM to recall facts | Search web first, then extract |
| High hallucination risk | Grounded in real search results |
| Stale training data | Live web data |
| ~70% wrong revenue figures | Accurate from financial news |

The tool runs **7 targeted web searches** (one per section), feeds all snippets as context to Groq, and instructs it to extract only what's explicitly stated — not guess.

---

## 📊 Output Sections

| Section | Time Window |
|---------|-------------|
| Key Facts | Current |
| Business Description | Current |
| Therapeutic Areas | Current |
| Key Subsidiaries | Current |
| Revenue (USD Billions) | Last 3 fiscal years |
| Blockbuster Drugs | Last 5 years |
| Pipeline & Approvals | Last 5 years |
| MedTech & Innovation | Last 5 years |
| Acquisitions | Last 2 years |
| Partnerships | Last 2 years |

---

## 🔜 Next Steps (Phase 2)
- Auto-generate PowerPoint (.pptx) from the same structured data
- Add source URLs as footnotes in the brief
- Streamlit Cloud deployment (add keys as secrets)
