import streamlit as st
import os
from researcher import research_company
from chart import generate_revenue_chart
from formatter import format_output

st.set_page_config(
    page_title="Pharma Company Research Tool",
    page_icon="💊",
    layout="centered"
)

st.title("💊 Pharma Company Research Tool")
st.markdown("Enter a pharmaceutical company name to generate a structured research brief and revenue chart.")

with st.sidebar:
    st.header("⚙️ API Keys")
    groq_api_key = st.text_input(
        "Groq API Key",
        type="password",
        help="Free at console.groq.com"
    )
    tavily_api_key = st.text_input(
        "Tavily API Key",
        type="password",
        help="Free at app.tavily.com (1000 searches/month)"
    )
    st.markdown("---")
    st.markdown("**How it works:**")
    st.markdown(
        "1. Tavily searches the web for each section separately\n"
        "2. Groq extracts structured data from real results\n"
        "3. No hallucination — answers grounded in live web data"
    )
    st.markdown("---")
    st.markdown("**Output sections:**")
    st.markdown(
        "- Key facts\n"
        "- Business description\n"
        "- Therapeutic areas\n"
        "- Subsidiaries\n"
        "- Revenue chart (last 3 yrs)\n"
        "- Blockbuster drugs (last 5 yrs)\n"
        "- Pipeline & approvals (last 5 yrs)\n"
        "- MedTech & innovation (last 5 yrs)\n"
        "- Acquisitions (last 2 yrs)\n"
        "- Partnerships (last 2 yrs)"
    )

company_name = st.text_input("🏢 Company Name", placeholder="e.g. Roche, Pfizer, Novartis, AstraZeneca...")

if st.button("🔍 Research Company", use_container_width=True):
    if not groq_api_key:
        st.error("Please enter your Groq API key in the sidebar.")
    elif not tavily_api_key:
        st.error("Please enter your Tavily API key in the sidebar.")
    elif not company_name.strip():
        st.error("Please enter a company name.")
    else:
        with st.spinner(f"Researching {company_name}... Running 7 web searches + AI extraction (~60s)"):
            try:
                os.environ["GROQ_API_KEY"] = groq_api_key
                os.environ["TAVILY_API_KEY"] = tavily_api_key

                progress = st.progress(0, text="Starting web searches...")

                progress.progress(10, text="Searching: Company overview & key facts...")
                data = research_company(company_name.strip())

                progress.progress(80, text="Generating revenue chart...")
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
                        st.image(chart_path, caption=f"{company_name} — Revenue (USD Billions)", use_container_width=True)

            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.exception(e)

st.markdown("---")
st.caption("Powered by Tavily Search + Groq LLaMA 3.3 · TCS Research Tool Prototype")
