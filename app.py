import os
import streamlit as st
from dotenv import load_dotenv
from serpapi import GoogleSearch

from searxng_crawler import scrape_website
from searxng_analyzer import (
    generate_summary,
    generate_description,
    get_wikipedia_summary,
    generate_corporate_events
)
from searxng_db import (
    store_report,
    get_reports,
    store_search,
    get_search_history
)
from searxng_pdf import create_pdf_from_text

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
    placeholder="Google, ChatGPT, or https://example.com"
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
                st.markdown(f"{idx + 1}. [{title}]({link})")
                page1_links.append(link)
        else:
            st.info("No search results found for this query.")

    except Exception as e:
        st.error(f"Error fetching search results: {e}")

# --- Analyze Company ---
if st.button("🚀 Analyze Company"):
    if not search_query.strip():
        st.warning("⚠️ Please enter a company name or URL")
    else:
        progress = st.progress(0)
        status = st.empty()

        summary = ""
        description = ""
        corporate_events = ""
        content_to_use = ""

        try:
            # --- Step 1: Wikipedia ---
            status.text("📘 Reading company background...")
            wiki_text = get_wikipedia_summary(search_query)
            content_to_use = wiki_text
            progress.progress(20)

            # --- Step 2: GPT Company Details Extraction ---
            status.text("🧠 Extracting company structure...")
            summary = generate_summary(search_query, text=wiki_text)
            progress.progress(40)

            # --- Step 3: Check for missing fields and fix ---
            required_fields = [
                "CEO", "Founder", "Headquarters",
                "Website", "Year Founded", "LinkedIn"
            ]
            missing = [
                field for field in required_fields
                if f"{field}:" in summary and summary.split(f"{field}:")[1].strip() == ""
            ]

            if missing:
                status.text("🔍 Searching for missing info...")
                from searxng_analyzer import openrouter_chat

                fix_prompt = f"""
                You are an expert data researcher. We are missing the following fields for **{search_query}**:
                {', '.join(missing)}.
                Find accurate, up-to-date info for these fields ONLY.
                Format your answer exactly as:
                - Field: Value
                - Field: Value
                (no extra text)
                """

                missing_filled = openrouter_chat(
                    "openai/gpt-4o-mini", fix_prompt, "Missing Field Finder"
                )

                if missing_filled:
                    for line in missing_filled.split("\n"):
                        if ":" in line:
                            key, val = line.split(":", 1)
                            summary = summary.replace(
                                f"{key.strip()}:", f"{key.strip()}: {val.strip()}"
                            )

                progress.progress(60)

            # --- Step 4: Website fallback if fields still missing ---
            still_missing = [
                field for field in required_fields
                if f"{field}:" in summary and summary.split(f"{field}:")[1].strip() == ""
            ]

            if still_missing:
                status.text("🌐 Exploring company website...")
                base_urls = [
                    f"https://{search_query.lower().replace(' ', '')}.com/about",
                    f"https://{search_query.lower().replace(' ', '')}.com/about-us",
                    f"https://{search_query.lower().replace(' ', '')}.com/company",
                    f"https://{search_query.lower().replace(' ', '')}.com/who-we-are",
                    f"https://{search_query.lower().replace(' ', '')}.com/leadership",
                    f"https://{search_query.lower().replace(' ', '')}.com/team"
                ]

                website_text = ""
                for url in base_urls:
                    try:
                        site_text = scrape_website(base_url=url, company_name=search_query)
                        if site_text and len(site_text) > len(website_text):
                            website_text = site_text
                    except:
                        continue

                if website_text.strip():
                    summary = generate_summary(search_query, text=website_text)
                    description = generate_description(
                        search_query, text=website_text, company_details=summary
                    )
                    content_to_use = website_text

                progress.progress(80)

            # --- Step 5: Final description ---
            if not description.strip():
                status.text("📝 Writing company profile...")
                description = generate_description(
                    search_query, text=wiki_text, company_details=summary
                )
                progress.progress(90)

            # --- Step 6: Corporate Events ---
            status.text("📅 Fetching corporate events...")
            corporate_events = generate_corporate_events(search_query, text=content_to_use) or "No corporate events found."
            progress.progress(100)

            # --- Step 7: Store & Display ---
            store_report(search_query, summary, description, corporate_events)

            store_search(
                search_query,
                content_to_use,
                summary,
                description,
                corporate_events=corporate_events
            )

            st.success("✅ Company data successfully fetched!")

            st.subheader("📈 Valuation Summary Report")
            st.markdown(summary)

            st.subheader("🏢 Company Description (5–6 lines)")
            st.text(description)

            st.subheader("📅 Corporate Events")
            st.text(corporate_events)

            events_text = f"\n\nCorporate Events:\n{corporate_events}" if corporate_events else ""

            pdf_file = create_pdf_from_text(
                title=search_query,
                summary=f"{description}\n\n{summary}{events_text}"
            )

            st.download_button(
                label="📄 Download PDF",
                data=pdf_file,
                file_name=f"{search_query.replace(' ', '_')}.pdf",
                mime="application/pdf"
            )

        except Exception as e:
            st.error(f"⚠️ Error during analysis: {e}")

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

            st.subheader("📅 Corporate Events")
            st.write(r.get('corporate_events', 'No events available.'))

            events_text = f"\n\nCorporate Events:\n{r.get('corporate_events', '')}" if r.get('corporate_events') else ""
            pdf_file = create_pdf_from_text(
                title=r.get('company', 'Report'),
                summary=f"{r.get('description', '')}\n\n{r.get('summary', '')}{events_text}"
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
            st.markdown(f"**Corporate Events:**\n{h.get('corporate_events', 'No events available.')}")

            events_text = f"\n\nCorporate Events:\n{h.get('corporate_events', '')}" if h.get('corporate_events') else ""
            pdf_file = create_pdf_from_text(
                title=query,
                summary=f"{h.get('description', '')}\n\n{h.get('summary', '')}{events_text}"
            )

            st.download_button(
                label="📄 Download PDF",
                data=pdf_file,
                file_name=f"{query.replace(' ', '_')}.pdf",
                mime="application/pdf",
                key=f"download_history_{idx}"
            )
