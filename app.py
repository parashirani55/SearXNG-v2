import streamlit as st
from dotenv import load_dotenv
import os

# Local imports
from searxng_crawler import scrape_website  # Updated with Wikipedia fallback
from searxng_analyzer import generate_summary, generate_description
from searxng_db import store_report, get_reports, store_search, get_search_history
from searxng_pdf import create_pdf_from_text  # Unicode-safe PDF
from serpapi import GoogleSearch

# --- Load Environment Variables ---
load_dotenv()

# --- Streamlit Page Config ---
st.set_page_config(
    page_title="SearXNG – AI Research Assistant",
    page_icon="🧭",
    layout="wide"
)

# --- Page Header ---
st.title("🧭 SearXNG – AI Research & Valuation Assistant")
st.markdown(
    "#### Discover insights, analyze companies, and generate instant valuation reports powered by AI."
)

# --- User Input ---
search_query = st.text_input(
    "🔎 Enter company/topic (or paste URL directly)",
    placeholder="Google, ChatGPT, or https://example.com",
)

# --- Search Logic ---
if st.button("Search"):
    if not search_query.strip():
        st.warning("⚠️ Please enter a search query or URL")
    else:
        st.session_state['search_results'] = []

        # Detect if input is a direct URL or a search query
        if search_query.startswith("http"):
            st.session_state['search_results'] = [{
                "title": search_query,
                "link": search_query,
                "snippet": "",
                "id": 0
            }]
        else:
            try:
                params = {
                    "q": search_query,
                    "hl": "en",
                    "gl": "us",
                    "num": 10,
                    "api_key": os.getenv("SERPAPI_KEY")
                }
                search = GoogleSearch(params)
                results = search.get_dict().get("organic_results", [])

                for idx, res in enumerate(results):
                    st.session_state['search_results'].append({
                        "title": res.get("title") or res.get("link", ""),
                        "link": res.get("link", ""),
                        "snippet": res.get("snippet", ""),
                        "id": idx
                    })
            except Exception as e:
                st.error(f"Error fetching search results: {e}")

# --- Display URLs to be analyzed ---
if st.session_state.get('search_results'):
    st.subheader("🔗 URLs to be Analyzed (Page 1 Results)")
    for res in st.session_state['search_results']:
        st.markdown(f"- [{res['title']}]({res['link']})")

# --- Analyze All URLs ---
if st.session_state.get('search_results') and st.button("🚀 Analyze All Page 1 Links"):
    urls_to_process = [res['link'] for res in st.session_state['search_results']]
    total_urls = len(urls_to_process)
    progress_bar = st.progress(0)

    for idx, url in enumerate(urls_to_process):
        with st.spinner(f"Analyzing {url} ..."):
            try:
                scraped_text = scrape_website(base_url=url, company_name=search_query)

                if not scraped_text:
                    st.warning(f"No content scraped from {url}. Skipping analysis.")
                    continue

                # AI Analysis
                summary = generate_summary(scraped_text)
                description = generate_description(scraped_text)

                # Save to DB
                store_report(url, summary, description)
                store_search(search_query, scraped_text, summary, description)

                # Display Results in Collapsible Expander
                with st.expander(f"📌 {url}"):
                    st.subheader("📈 Valuation Summary Report")
                    st.write(summary)

                    st.subheader("🏢 Company Description")
                    st.write(description)

                    # PDF Download
                    combined_text = f"Company Description:\n{description}\n\nValuation Summary:\n{summary}"
                    pdf_file = create_pdf_from_text(title=url, summary=combined_text)
                    st.download_button(
                        label="📄 Download PDF",
                        data=pdf_file,
                        file_name=f"{url.replace('https://','').replace('/','_')}.pdf",
                        mime="application/pdf",
                        key=f"download_{idx}_{url}"
                    )

                # Update progress bar
                progress = (idx + 1) / total_urls
                progress_bar.progress(progress)

            except Exception as e:
                st.error(f"Error analyzing {url}: {e}")

    progress_bar.empty()

st.divider()

# --- Previous Valuation Reports ---
st.subheader("🗂️ Previous Valuation Reports")
reports = get_reports()
if not reports:
    st.info("No saved reports yet.")
else:
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

st.divider()

# --- Previous Search History (one entry per query) ---
st.subheader("🕘 Previous Search History")
history = get_search_history()
if not history:
    st.info("No previous searches yet.")
else:
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
