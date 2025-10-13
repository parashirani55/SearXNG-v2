import streamlit as st
from dotenv import load_dotenv
import os
import time
import random
from searxng_crawler import scrape_website
from searxng_analyzer import generate_summary, generate_description, get_wikipedia_summary
from searxng_db import store_report, get_reports, store_search, get_search_history
from searxng_pdf import create_pdf_from_text
from serpapi import GoogleSearch

# --- Load Environment Variables ---
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# --- Streamlit Config ---
st.set_page_config(
    page_title="SearXNG – AI Research Assistant",
    page_icon="🧭",
    layout="wide"
)

# --- Page Header ---
st.title("🧭 SearXNG – AI Research & Valuation Assistant")
st.markdown("#### Discover insights, analyze companies, and generate instant valuation reports powered by AI.")

# --- User Input ---
search_query = st.text_input(
    "🔎 Enter company/topic (or paste URL directly)",
    placeholder="Google, ChatGPT, or https://example.com",
)

# --- Fetch Page 1 Links ---
if search_query.strip():
    st.subheader("🔗 Top Page 1 Search Results")
    try:
        params = {
            "q": search_query,
            "hl": "en",
            "gl": "us",
            "num": 10,
            "api_key": SERPAPI_KEY
        }
        search = GoogleSearch(params)
        results = search.get_dict().get("organic_results", [])
        page1_links = []

        if results:
            for idx, res in enumerate(results):
                title = res.get("title") or res.get("link", "")
                link = res.get("link", "")
                snippet = res.get("snippet", "")
                st.markdown(f"{idx+1}. [{title}]({link})")
                page1_links.append(link)
        else:
            st.info("No search results found for this query.")
    except Exception as e:
        st.error(f"Error fetching search results: {e}")

# --- Humanized Progress Messages ---
PROGRESS_MESSAGES = [
    "📡 Gathering company signals from trusted sources...",
    "🧠 Summarizing verified data into insights...",
    "💼 Extracting executive and HQ details...",
    "📊 Refining structured business overview...",
    "🌐 Collecting web intelligence and final touches..."
]

# --- Analyze Company ---
if st.button("🚀 Analyze Company"):
    if not search_query.strip():
        st.warning("⚠️ Please enter a company name or URL")
    else:
        progress_placeholder = st.empty()
        progress_bar = st.progress(0)

        summary = ""
        description = ""
        content_to_use = ""

        # Progress simulation
        for i, msg in enumerate(PROGRESS_MESSAGES):
            progress_placeholder.markdown(f"**{msg}**")
            progress_bar.progress((i + 1) / len(PROGRESS_MESSAGES))
            time.sleep(random.uniform(0.6, 1.2))

        # Step 1: Wikipedia or fallback
        wiki_text = get_wikipedia_summary(search_query)
        content_to_use = wiki_text

        # Step 2: AI summaries
        summary = generate_summary(search_query, text=wiki_text)
        description = generate_description(search_query, text=wiki_text)

        # Step 3: Website fallback if Wikipedia/AI insufficient
        if not summary.strip() or not description.strip() or len(description.strip().splitlines()) < 5:
            base_url = page1_links[0] if 'page1_links' in locals() and page1_links else ""
            if base_url:
                website_text = scrape_website(base_url=base_url, company_name=search_query)
                if website_text.strip():
                    summary = generate_summary(search_query, text=website_text)
                    description = generate_description(search_query, text=website_text)
                    content_to_use = website_text

        # Step 4: Show result or error
        progress_bar.progress(1.0)
        progress_placeholder.empty()

        if not summary.strip() and not description.strip():
            st.error("❌ Unable to fetch company data from available sources.")
        else:
            store_report(search_query, summary, description)
            store_search(search_query, content_to_use, summary, description)

            st.success("✅ Analysis Complete")

            st.subheader("📈 Valuation Summary Report")
            st.markdown(summary)

            st.subheader("🏢 Company Description (5–6 lines)")
            st.markdown(description)

            pdf_file = create_pdf_from_text(
                title=search_query,
                summary=f"{description}\n\n{summary}"
            )
            st.download_button(
                label="📄 Download PDF",
                data=pdf_file,
                file_name=f"{search_query.replace(' ','_')}.pdf",
                mime="application/pdf"
            )

# --- Previous Reports ---
st.divider()
st.subheader("🗂️ Previous Valuation Reports")
reports = get_reports()
if reports:
    for idx, r in enumerate(reports):
        with st.expander(f"📊 {r.get('company', 'Unknown Company')}"):
            st.subheader("📈 Valuation Summary Report")
            st.write(r.get('summary', 'No summary available.'))
            st.subheader("🏢 Company Description")
            st.write(r.get('description', 'No description available.'))

            pdf_file = create_pdf_from_text(
                title=r.get('company', 'Report'),
                summary=f"{r.get('description','')}\n\n{r.get('summary','')}"
            )
            st.download_button(
                label="📄 Download PDF",
                data=pdf_file,
                file_name=f"{r.get('company', 'report').replace(' ', '_')}.pdf",
                mime="application/pdf",
                key=f"download_report_{idx}"
            )

# --- Previous Search History ---
st.divider()
st.subheader("🕘 Previous Search History")
history = get_search_history()
if history:
    seen_queries = set()
    for idx, h in enumerate(history):
        query = h.get('query', 'Unknown Query')
        if query in seen_queries:
            continue
        seen_queries.add(query)
        with st.expander(f"🔎 {query}"):
            raw_text = h.get('results', '')[:500] + "..."
            st.markdown(f"**Raw Results:**\n{raw_text}")
            st.markdown(f"**AI Description:**\n{h.get('description', '')}")
            st.markdown(f"**AI Summary:**\n{h.get('summary', '')}")

            pdf_file = create_pdf_from_text(
                title=query,
                summary=f"{h.get('description','')}\n\n{h.get('summary','')}"
            )
            st.download_button(
                label="📄 Download PDF",
                data=pdf_file,
                file_name=f"{query.replace(' ', '_')}.pdf",
                mime="application/pdf",
                key=f"download_history_{idx}"
            )
