import streamlit as st
from dotenv import load_dotenv
load_dotenv()
import os
import io

from searxng_crawler import scrape_website
from searxng_analyzer import generate_summary
from searxng_db import store_report, get_reports, store_search, get_search_history
from searxng_pdf import create_pdf_from_text  # Unicode-safe PDF

# SerpAPI
from serpapi import GoogleSearch

# --- Streamlit Page Config ---
st.set_page_config(page_title="SearXNG – AI Research Assistant", page_icon="🧭", layout="wide")
st.title("🧭 SearXNG – AI Research & Valuation Assistant")
st.markdown("#### Discover insights, analyze companies, and generate instant valuation reports powered by AI.")

# --- User Input ---
search_query = st.text_input(
    "🔎 Enter company/topic (or paste URL directly)",
    placeholder="Elite Infotec or https://verityplatform.com"
)

# --- Search Button ---
if st.button("Search"):
    if search_query.strip() == "":
        st.warning("⚠️ Please enter a search query or URL")
    else:
        st.session_state['search_results'] = []

        # Detect if input is URL or keyword
        if search_query.startswith("http"):
            st.session_state['search_results'] = [{"title": search_query, "link": search_query, "snippet": ""}]
        else:
            # Use SerpAPI for keyword search
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
                        "title": res.get("title", res.get("link", "")),
                        "link": res.get("link", ""),
                        "snippet": res.get("snippet", ""),
                        "id": idx  # unique ID for checkbox/key
                    })
            except Exception as e:
                st.error(f"Error fetching search results: {e}")

# --- Display Search Results ---
if 'search_results' in st.session_state and st.session_state['search_results']:
    st.subheader("Select URLs to Analyze")
    selected_urls = []

    for res in st.session_state['search_results']:
        checkbox_label = f"{res['title']} ({res['link']})"
        if st.checkbox(checkbox_label, key=f"chk_{res['id']}"):
            selected_urls.append(res['link'])

        # Display snippet
        if res['snippet']:
            st.markdown(f"*{res['snippet']}*")
        st.markdown("---")

    # --- Analyze Selected URLs ---
    if st.button("🚀 Analyze Selected URLs") and selected_urls:
        for idx, url in enumerate(selected_urls):
            with st.spinner(f"Analyzing {url} ..."):
                try:
                    scraped = scrape_website(url)
                    combined_text = ' '.join([item['content'] for item in scraped])
                    summary = generate_summary(combined_text)

                    # Store in Supabase
                    store_report(url, summary)
                    store_search(search_query, combined_text, summary)

                    # Display summary
                    st.markdown(f"### 📌 {url}")
                    st.markdown(summary)

                    # --- Download PDF ---
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
        with st.expander(f"📊 {r['company']}"):
            st.markdown(r['summary'])
            # PDF download for past reports
            pdf_file = create_pdf_from_text(title=r['company'], summary=r['summary'])
            st.download_button(
                label="📄 Download PDF",
                data=pdf_file,
                file_name=f"{r['company'].replace(' ','_')}.pdf",
                mime="application/pdf",
                key=f"download_report_{idx}_{r['company']}"
            )

st.divider()

# --- Previous Search History ---
st.subheader("🕘 Previous Search History")
history = get_search_history()
if not history:
    st.info("No previous searches yet.")
else:
    for idx, h in enumerate(history):
        with st.expander(f"🔎 {h['query']}"):
            st.markdown(f"**Raw Results:**\n{h['results'][:500]}...")  # first 500 chars
            st.markdown(f"**AI Summary:**\n{h['summary']}")

            # PDF download for past searches
            pdf_file = create_pdf_from_text(title=h['query'], summary=h['summary'])
            st.download_button(
                label="📄 Download PDF",
                data=pdf_file,
                file_name=f"{h['query'].replace(' ','_')}.pdf",
                mime="application/pdf",
                key=f"download_history_{idx}_{h['query']}"
            )
