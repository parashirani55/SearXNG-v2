import streamlit as st
from dotenv import load_dotenv
import os

# Local imports
from searxng_crawler import scrape_website  # Updated with Wikipedia fallback
from searxng_analyzer import generate_summary
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

# --- Initialize selected URLs ---
selected_urls = []

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

# --- Display Search Results ---
if st.session_state.get('search_results'):
    st.subheader("Select URLs to Analyze")

    for res in st.session_state['search_results']:
        checkbox_label = f"{res['title']} ({res['link']})"
        key_id = res.get('id', len(selected_urls))  # fallback

        if st.checkbox(checkbox_label, key=f"chk_{key_id}"):
            selected_urls.append(res['link'])

        if res.get('snippet'):
            st.markdown(f"*{res['snippet']}*")

        st.markdown("---")

# --- Analyze Selected URLs or GPT fallback ---
if (selected_urls or search_query) and st.button("🚀 Analyze Selected URLs / Generate Report"):
    if not selected_urls:
        # If no URL selected, just use GPT with search_query as fallback
        scraped_text = scrape_website(base_url=None, company_name=search_query, use_js_fallback=False)
        urls_to_process = [search_query]
    else:
        urls_to_process = selected_urls

    for idx, url in enumerate(urls_to_process):
        with st.spinner(f"Analyzing {url} ..."):
            try:
                if selected_urls:
                    scraped_text = scrape_website(base_url=url, company_name=search_query)

                summary = generate_summary(scraped_text)

                # Save to database
                store_report(url, summary)
                store_search(search_query, scraped_text, summary)

                # Display summary
                st.markdown(f"### 📌 {url}")
                st.markdown(summary)

                pdf_file = create_pdf_from_text(title=url, summary=summary)
                st.download_button(
                    label="📄 Download PDF",
                    data=pdf_file,
                    file_name=f"{url.replace('https://','').replace('/','_')}.pdf",
                    mime="application/pdf",
                    key=f"download_new_{idx}_{url}"
                )

            except Exception as e:
                st.error(f"Error analyzing {url}: {e}")

st.divider()

# --- Previous Valuation Reports ---
st.subheader("🗂️ Previous Valuation Reports")
reports = get_reports()

if not reports:
    st.info("No saved reports yet.")
else:
    for idx, r in enumerate(reports):
        with st.expander(f"📊 {r.get('company', 'Unknown Company')}"):
            st.markdown(r.get('summary', 'No summary available.'))

            pdf_file = create_pdf_from_text(
                title=r.get('company', 'Report'),
                summary=r.get('summary', '')
            )

            st.download_button(
                label="📄 Download PDF",
                data=pdf_file,
                file_name=f"{r.get('company', 'report').replace(' ', '_')}.pdf",
                mime="application/pdf",
                key=f"download_report_{idx}"
            )

st.divider()

# --- Previous Search History ---
st.subheader("🕘 Previous Search History")
history = get_search_history()

if not history:
    st.info("No previous searches yet.")
else:
    for idx, h in enumerate(history):
        with st.expander(f"🔎 {h.get('query', 'Unknown Query')}"):
            raw_text = h.get('results', '')[:500] + "..."
            st.markdown(f"**Raw Results:**\n{raw_text}")
            st.markdown(f"**AI Summary:**\n{h.get('summary', '')}")

            pdf_file = create_pdf_from_text(
                title=h.get('query', 'Search'),
                summary=h.get('summary', '')
            )

            st.download_button(
                label="📄 Download PDF",
                data=pdf_file,
                file_name=f"{h.get('query', 'search').replace(' ', '_')}.pdf",
                mime="application/pdf",
                key=f"download_history_{idx}"
            )
