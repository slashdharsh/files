import streamlit as st
import os
from researcher import research_company
from chart import generate_revenue_chart
from formatter import format_output

# ── Load API keys ──────────────────────────────────────────────────────────
# Priority: Streamlit secrets (cloud) → .env file (local) → error
try:
    # Works on Streamlit Cloud
    from dotenv import load_dotenv
    load_dotenv()  # loads .env if present locally, no-op if not found
except ImportError:
    pass

def get_key(name: str) -> str:
    # 1. Streamlit secrets (for cloud deployment)
    try:
        return st.secrets[name]
    except Exception:
        pass
    # 2. Environment variable (loaded from .env locally)
    val = os.environ.get(name)
    if val:
        return val
    return ""

GROQ_KEY   = get_key("GROQ_API_KEY")
TAVILY_KEY = get_key("TAVILY_API_KEY")
SERPER_KEY = get_key("SERPER_API_KEY")

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Pharma Company Research Tool",
    page_icon="💊",
    layout="centered"
)

st.title("💊 Pharma Company Research Tool")
st.markdown("Enter a pharmaceutical company name to generate a structured research brief and revenue chart.")

# ── Sidebar — info only, no key inputs ────────────────────────────────────
with st.sidebar:
    st.markdown("**Pipeline:**")
    st.markdown(
        "1. Serper (Google) — facts, revenue, employees\n"
        "2. Tavily (full pages) — pipeline, deals, MedTech\n"
        "3. LLaMA 8B — compress to key facts\n"
        "4. LLaMA 70B — extract structured JSON"
    )
    st.markdown("---")
    st.markdown("**Output sections:**")
    st.markdown(
        "- Key facts · Business description\n"
        "- Therapeutic areas · Subsidiaries\n"
        "- Revenue chart (last 3 yrs)\n"
        "- Blockbuster drugs (last 5 yrs)\n"
        "- Pipeline & approvals (last 5 yrs)\n"
        "- MedTech & innovation (last 5 yrs)\n"
        "- Acquisitions (last 2 yrs)\n"
        "- Partnerships (last 2 yrs)"
    )

    # Show key status
    st.markdown("---")
    st.markdown("**API Key Status:**")
    for label, val in [("Groq", GROQ_KEY), ("Tavily", TAVILY_KEY), ("Serper", SERPER_KEY)]:
        st.markdown(f"{'✅' if val else '❌'} {label}")

# ── Main ───────────────────────────────────────────────────────────────────
company_name = st.text_input("🏢 Company Name", placeholder="e.g. Roche, Pfizer, Novartis, AstraZeneca...")

if st.button("🔍 Research Company", use_container_width=True):
    missing = [n for n, k in [("Groq", GROQ_KEY), ("Tavily", TAVILY_KEY), ("Serper", SERPER_KEY)] if not k]
    if missing:
        st.error(f"Missing API keys: {', '.join(missing)}. Add them to your .env file or Streamlit secrets.")
    elif not company_name.strip():
        st.error("Please enter a company name.")
    else:
        with st.spinner(f"Researching {company_name}... (~90 seconds)"):
            try:
                os.environ["GROQ_API_KEY"]   = GROQ_KEY
                os.environ["TAVILY_API_KEY"] = TAVILY_KEY
                os.environ["SERPER_API_KEY"] = SERPER_KEY

                progress = st.progress(0, text="Starting web searches...")
                progress.progress(5, text="Searching: key facts, revenue, pipeline, deals...")
                data = research_company(company_name.strip())

                progress.progress(85, text="Generating revenue chart...")
                chart_path = generate_revenue_chart(data, company_name.strip())

                progress.progress(95, text="Formatting output brief...")
                txt_content = format_output(data, company_name.strip())

                progress.progress(100, text="Done!")
                st.success(f"✅ Research complete for **{company_name}**")

                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        label="📄 Download TXT Brief",
                        data=txt_content,
                        file_name=f"{company_name.replace(' ', '_')}_brief.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                with col2:
                    if chart_path and os.path.exists(chart_path):
                        with open(chart_path, "rb") as f:
                            st.download_button(
                                label="📊 Download Revenue Chart",
                                data=f,
                                file_name=f"{company_name.replace(' ', '_')}_revenue_chart.png",
                                mime="image/png",
                                use_container_width=True
                            )

                with st.expander("📋 Preview Text Brief", expanded=True):
                    st.text(txt_content)

                if chart_path and os.path.exists(chart_path):
                    with st.expander("📊 Preview Revenue Chart", expanded=True):
                        st.image(chart_path, caption=f"{company_name} — Revenue (USD Billions)",
                                 use_container_width=True)

            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.exception(e)

st.markdown("---")
st.caption("Powered by Serper · Tavily · Groq LLaMA · TCS Research Tool Prototype")
