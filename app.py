# ============================================================
# app.py — SearXNG AI Research & Valuation Assistant
# ============================================================

import os
import json
import re
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from serpapi import GoogleSearch
import hashlib
import ast
import uuid
import streamlit as st
import pandas as pd
from analysis.person_analyzer import generate_people_intelligence
from analysis.corporate_event import event_verified
from analysis.summary_generator import generate_summary
from searxng_analyzer import (
    generate_description,
    get_wikipedia_summary,
    generate_corporate_events,
    get_top_management,
    generate_subsidiary_data
)

from searxng_db import (
    store_report,
    get_reports,
    store_search,
    get_search_history,
    get_subsidiaries 
)
from searxng_pdf import create_pdf_from_text

# ============================================================
# 🔹 Normalization Helpers
# ============================================================

def normalize_top_management(data):
    """Ensure keys match the expected format (role → position, add status if missing)."""
    if not data:
        return []
    try:
        mgmt = json.loads(data) if isinstance(data, str) else data
        if isinstance(mgmt, list):
            for m in mgmt:
                if "role" in m and "position" not in m:
                    m["position"] = m.pop("role")
                if "status" not in m:
                    m["status"] = "Current"  # Default for legacy data
            return mgmt
    except:
        return []
    return []

def normalize_corporate_events(raw_text):
    """Convert plain text or JSON events into a structured list."""
    events = []
    if not raw_text:
        return events

    # If already JSON, return it directly
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, list):
            return parsed
    except:
        pass

    # Parse plain text format using regex for robust multi-line extraction
    pattern = r'- Event Description: (.*?)(?=\s*(?:Date:|Type:|Value:| - Event Description:)|$)'
    matches = re.findall(pattern, raw_text, re.DOTALL | re.IGNORECASE)
    
    for match in matches:
        if not match.strip():
            continue
        event_block = re.search(r'- Event Description: .*?(?=\s*- Event Description:|$)', raw_text, re.DOTALL | re.IGNORECASE)
        if not event_block:
            continue
        event_block = event_block.group(0)
        
        event = {"description": match.strip()}
        lines = event_block.split('\n')
        for line in lines:
            line = line.strip()
            if ':' in line and line.lower().startswith(('date:', 'type:', 'value:')):
                key, val = line.split(':', 1)
                key = key.strip().lower()
                val = val.strip()
                if key == 'date':
                    event["date"] = val
                elif key == 'type':
                    event["type"] = val
                elif key == 'value':
                    event["value"] = val
        if event.get("description"):
            events.append(event)
    
    return events

# ============================================================
# 🔹 Environment Setup
# ============================================================
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# ============================================================
# 🔹 Streamlit Configuration
# ============================================================
st.set_page_config(
    page_title="SearXNG – AI Research Assistant",
    page_icon="🧭",
    layout="wide"
)
st.title("🧭 SearXNG – AI Research & Valuation Assistant")
st.markdown("#### Discover insights, analyze companies, and generate instant valuation reports powered by AI.")

# ============================================================
# 🔹 Helper Functions
# ============================================================

def show_corporate_events(events):
    """
    ✅ Unified Corporate Events Renderer
       - Handles JSON string / list-of-dicts / raw text
       - Fixes inconsistent key names
       - Safe date parsing with mixed formats
       - Splits clean vs incomplete events cleanly
    """

    if not events:
        st.warning("⚠️ No corporate events found.")
        return

    # ✅ Convert JSON → list of dicts
    if isinstance(events, str):
        try:
            events = json.loads(events)
            if isinstance(events, str):  # double-encoded JSON
                events = json.loads(events)
        except:
            events = normalize_corporate_events(events)

    if not isinstance(events, list) or not events:
        st.warning("⚠️ Corporate events format invalid.")
        return

    df = pd.DataFrame(events)

    # ✅ Standardize naming
    rename_map = {
        "description": "Event Description",
        "title": "Event Description",
        "date": "Date",
        "event_type": "Type",
        "type": "Type",
        "counterparty": "Counterparty",
        "amount": "Value",
        "value": "Value",
        "source": "Source"
    }
    df = df.rename(columns=rename_map)

    # ✅ Ensure mandatory columns exist
    required_cols = ["Date", "Event Description", "Type", "Counterparty", "Value", "Source"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = "-"
    
    # ✅ Remove duplicate column labels (fixes "cannot reindex" error)
    df = df.loc[:, ~df.columns.duplicated()].copy()
    
    # ✅ Normalize cell content (safe for Series, arrays, NaN, etc.)
    for col in required_cols:
        df[col] = df[col].apply(
            lambda x: (
                " ".join(map(str, x)) if isinstance(x, (list, tuple)) else
                str(x).strip() if isinstance(x, (str, int, float)) and str(x).strip().lower() not in ["", "nan", "none"] else
                "-"
            )
        )
    
    # ✅ Replace any remaining NaN values
    df = df.fillna("-")
    
    # ✅ Clean + parse dates (mixed formats allowed)
    df["Date"] = df["Date"].astype(str).str.replace(r"[^\w\s:/-]", "", regex=True).str.strip()
    df["SortDate"] = pd.to_datetime(df["Date"], format="mixed", errors="coerce")
    df = df.sort_values("SortDate", ascending=False)

    # ✅ Reorder columns
    df = df[required_cols]

    # ✅ Split complete vs incomplete
    complete_mask = (
        df["Event Description"].ne("-") &
        df["Date"].ne("-") &
        df["Type"].ne("-")
    )
    complete_df = df[complete_mask]
    incomplete_df = df[~complete_mask]

    # ✅ Display
    final_df = pd.concat([complete_df, incomplete_df]).reset_index(drop=True)

    st.markdown("### 📅 Verified Corporate Events")
    st.dataframe(final_df, use_container_width=True, hide_index=True)


def show_top_management(mgmt_data):
    """
    Renders top management information in two clear tables:
    - Current Leadership
    - Past Leadership
    Handles JSON, legacy strings, or semicolon-delimited text gracefully.
    """
    # -------------------------
    # 1️⃣ Parse / Normalize Data
    # -------------------------
    if not mgmt_data:
        st.info("No top management data available.")
        return

    # Convert JSON strings → list
    if isinstance(mgmt_data, str):
        try:
            parsed = json.loads(mgmt_data)
            if isinstance(parsed, dict):
                # From new get_top_management() format
                mgmt_data = []
                for item in parsed.get("current", []):
                    item["status"] = "Current"
                    mgmt_data.append(item)
                for item in parsed.get("past", []):
                    item["status"] = "Past"
                    mgmt_data.append(item)
            elif isinstance(parsed, list):
                mgmt_data = parsed
            else:
                mgmt_data = []
        except Exception:
            # Try to parse plain string: "Name — Role (Status); ..."
            entries = re.split(r";\s*", mgmt_data.strip())
            mgmt_data = []
            for entry in entries:
                if not entry.strip():
                    continue
                match = re.match(r"(.+?)\s*[—-]\s*(.+?)(?:\s*\((Current|Past)\))?$", entry.strip())
                if match:
                    name, position, status = match.groups()
                    mgmt_data.append({
                        "name": name.strip(),
                        "position": position.strip(),
                        "status": status or "Current"
                    })
                else:
                    mgmt_data.append({"name": entry.strip(), "position": "", "status": "Current"})

    # Ensure it’s a valid list
    if not isinstance(mgmt_data, list) or not mgmt_data:
        st.info("No top management data available.")
        return

    df = pd.DataFrame(mgmt_data)
    if not {"name", "position"}.issubset(df.columns):
        st.info("No valid management data found.")
        return

    # Clean & normalize
    df = df.rename(columns={"name": "Name", "position": "Position", "status": "Status"})
    df["Status"] = df["Status"].fillna("Current").apply(lambda x: x.capitalize())

    # -------------------------
    # 2️⃣ Split into Current & Past
    # -------------------------
    current_df = df[df["Status"] == "Current"][["Name", "Position"]].drop_duplicates().fillna("-")
    past_df = df[df["Status"] == "Past"][["Name", "Position"]].drop_duplicates().fillna("-")

    # -------------------------
    # 3️⃣ Display
    # -------------------------
    if not current_df.empty:
        st.markdown("### 👤 Current Leadership")
        st.dataframe(
            current_df.reset_index(drop=True),
            width="stretch",
            hide_index=True
        )
    elif past_df.empty:
        st.info("No leadership data available.")

    if not past_df.empty:
        st.markdown("### 🕰️ Past Leadership")
        st.dataframe(
            past_df.reset_index(drop=True),
            width="stretch",
            hide_index=True
        )

def show_subsidiaries(subsidiaries, context_label="main"):
    """
    Displays subsidiaries in a clean, readable layout.
    ✅ Shows full description (no expand button)
    ✅ Logos fit neatly in divs
    """
    if not subsidiaries:
        st.info("No subsidiaries found.")
        return

    st.markdown("### 🏢 Subsidiaries Overview")

    for i, sub in enumerate(subsidiaries):
        name = sub.get("name", "Unknown")
        logo = sub.get("logo", "")
        desc = sub.get("description", "No description available.")
        sector = sub.get("sector", "N/A")
        country = sub.get("country", "N/A")
        linkedin_members = sub.get("linkedin_members", 0)
        url = sub.get("url", "")

        with st.container():
            st.markdown("---")
            cols = st.columns([1, 6])

            with cols[0]:
                st.markdown(
                    f"""
                    <div style="
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        width: 80px;
                        height: 80px;
                        border-radius: 12px;
                        overflow: hidden;
                        background-color: #f5f5f5;
                        box-shadow: 0 1px 4px rgba(0,0,0,0.1);
                    ">
                        <img src="{logo}" style="max-width: 70px; max-height: 70px; object-fit: contain;" />
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            with cols[1]:
                st.markdown(f"### {name}")
                st.markdown(f"**Sector:** {sector}  |  **Country:** {country}  |  👥 {linkedin_members} members")
                if url:
                    st.markdown(f"[🌐 Visit Website]({url})")

                # ✅ Full description always visible
                st.markdown(f"<p style='text-align: justify;'>{desc}</p>", unsafe_allow_html=True)

# ============================================================
# 🔹 Search Input
# ============================================================
search_query = st.text_input("🔎 Enter company/topic (or paste URL directly)", placeholder="Google, ChatGPT, or https://example.com")

# ============================================================
# 🔹 Fetch Search Results
# ============================================================
if search_query.strip():
    st.subheader("🔗 Top Page 1 Search Results")
    try:
        params = {"q": search_query, "hl": "en", "gl": "us", "num": 10, "api_key": SERPAPI_KEY}
        search = GoogleSearch(params)
        results = search.get_dict().get("organic_results", [])
        if results:
            for idx, res in enumerate(results):
                title = res.get("title") or res.get("link", "")
                link = res.get("link", "")
                st.markdown(f"{idx + 1}. [{title}]({link})")
        else:
            st.info("No search results found for this query.")
    except Exception as e:
        st.error(f"Error fetching search results: {e}")

# ============================================================
# 🔹 Analyze Company
# ============================================================
if st.button("🚀 Analyze Company"):
    if not search_query.strip():
        st.warning("⚠️ Please enter a company name or URL")
    else:
        progress = st.progress(0)
        status = st.empty()

        summary, description, corporate_events, mgmt_list, mgmt_text, subsidiaries = "", "", [], [], "", []

        try:
            # -------------------------
            # 1️⃣ Wikipedia / Company Background
            # -------------------------
            status.text("📘 Reading company background...")
            wiki_text = get_wikipedia_summary(search_query)
            progress.progress(20)

            # -------------------------
            # 2️⃣ AI Summary
            # -------------------------
            status.text("🧠 Extracting company structure...")
            summary = generate_summary(search_query, text=wiki_text)
            progress.progress(40)

            # -------------------------
            # 3️⃣ Company Description
            # -------------------------
            status.text("📝 Writing company profile...")
            description = generate_description(search_query, text=wiki_text, company_details=summary)
            progress.progress(60)


            # -------------------------
            # 4️⃣ Corporate Events (With ETA + Live Status)
            # -------------------------
            status.text("📅 Fetching corporate events...")
            progress.progress(65)

            try:
                import time
                from analysis.corporate_event.event_verified import generate_verified_corporate_events

                # Start timer
                start_time = time.time()

                # Display live ETA info
                st.info("⏳ Gemini Verified Mode: This may take 2–5 minutes depending on company size and year range.")

                # Initialize live UI placeholders
                eta_display = st.empty()
                step_display = st.empty()

                # Simulate or stream ETA updates while running the generator
                step_display.text("🧠 Initializing Gemini verified models...")
                eta_display.text("🕒 Estimated completion: calculating...")

                # Run the full unified verified event generator
                eta_display = st.empty()
                step_display = st.empty()
                progress_bar = st.progress(0)

                def update_eta_ui(message, progress_value):
                    step_display.text(message)
                    eta_display.text(f"⏳ {message}")
                    progress_bar.progress(min(max(progress_value, 0.01), 1.0))

                raw_events_dict = event_verified.generate_verified_corporate_events(
                    search_query, years=5, progress_callback=update_eta_ui
                )
                corporate_events = raw_events_dict.get("events", [])

                # Simulate time for display update
                elapsed = time.time() - start_time
                minutes, seconds = divmod(int(elapsed), 60)
                eta_display.text(f"✅ Completed in {minutes} min {seconds:02d} sec")
                step_display.text(f"🎯 Total Verified Events: {len(corporate_events)}")

            except Exception as e:
                corporate_events = []
                st.warning(f"⚠️ Failed to fetch corporate events: {e}")

            progress.progress(75)

            

            # -------------------------
            # 5️⃣ Top Management
            # -------------------------
            status.text("👥 Fetching top management...")
            mgmt_list, mgmt_text = get_top_management(search_query)
            mgmt_list = normalize_top_management(mgmt_list)
            progress.progress(85)

            # -------------------------
            # 6️⃣ Subsidiaries
            # -------------------------
            status.text("🏢 Fetching subsidiaries...")
            subsidiaries = get_subsidiaries(search_query) or generate_subsidiary_data(search_query)
            progress.progress(95)

            # -------------------------
            # 7️⃣ Store Report & Search Data
            # -------------------------
            store_report(
                search_query,
                summary,
                description,
                json.dumps(corporate_events),
                json.dumps(mgmt_list)
            )

            store_search(
                search_query,
                wiki_text,
                summary,
                description,
                json.dumps(corporate_events),
                json.dumps(mgmt_list)
            )

            # -------------------------
            # 8️⃣ Display Results
            # -------------------------
            st.success("✅ Company data successfully fetched!")
            progress.progress(100)
            status.text("✅ Done")

            st.subheader("📈 Valuation Summary Report")
            st.markdown(summary)

            st.subheader("🏢 Company Description")
            st.text(description)

            st.subheader("📅 Corporate Events")
            show_corporate_events(corporate_events)

            if raw_events_dict and raw_events_dict.get("verified_count", 0) > 0:
                st.info(f"✅ Verified {raw_events_dict['verified_count']} corporate events retrieved via Gemini Deep Fetch.")


            st.subheader("👥 Top Management")
            show_top_management(mgmt_list)

            st.subheader("People Intelligence")
            people = generate_people_intelligence(search_query, mgmt_list)
            if people:
                df = pd.DataFrame(people)
                df = df[['name', 'position', 'status', 'location', 'linkedin', 'bio']]
                df.columns = ['Name', 'Role', 'Status', 'Location', 'LinkedIn', 'Bio']
                df['LinkedIn'] = df['LinkedIn'].apply(lambda x: f"[View]({x})" if x != "N/A" else "N/A")
                st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)
            else:
                st.info("No people intelligence generated.")

            st.subheader("🏢 Subsidiaries")
            if subsidiaries:
                show_subsidiaries(subsidiaries)
            else:
                st.info("No subsidiaries found for this company.")

            # -------------------------
            # 9️⃣ PDF Generation
            # -------------------------
            events_text = f"\n\nCorporate Events:\n{json.dumps(corporate_events)}" if corporate_events else ""
            mgmt_text_pdf = f"\n\nTop Management:\n{mgmt_text}" if mgmt_text else ""
            pdf_file = create_pdf_from_text(
                title=search_query,
                summary=f"{description}\n\n{summary}{events_text}{mgmt_text_pdf}"
            )

            st.download_button(
                "📄 Download PDF",
                data=pdf_file,
                file_name=f"{search_query.replace(' ', '_')}.pdf",
                mime="application/pdf"
            )

        except Exception as e:
            status.text("")
            st.error(f"⚠️ Error during analysis: {e}")

# ============================================================
# 🔹 Previous Valuation Reports
# ============================================================
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
            corp_data_raw = r.get("corporate_events")

            # ✅ Ensure the data is a valid Python list
            if isinstance(corp_data_raw, str):
                try:
                    corp_data = json.loads(corp_data_raw)
                    if isinstance(corp_data, str):  # Handle nested JSON strings
                        corp_data = json.loads(corp_data)
                except:
                    corp_data = normalize_corporate_events(corp_data_raw)
            else:
                corp_data = corp_data_raw or []

            show_corporate_events(corp_data)

            st.subheader("👥 Top Management")
            mgmt_list = normalize_top_management(r.get("top_management"))
            show_top_management(mgmt_list)

            pdf_file = create_pdf_from_text(
                title=r.get('company', 'Report'),
                summary=f"{r.get('description', '')}\n\n{r.get('summary', '')}"
            )

            st.subheader("🏢 Subsidiaries")
            subsidiaries_data = get_subsidiaries(r.get("company", ""))
            if subsidiaries_data:
                show_subsidiaries(subsidiaries_data, context_label=f"report_{idx}")
            else:
                st.info("No subsidiaries found for this company.")


            st.download_button(
                "📄 Download PDF",
                data=pdf_file,
                file_name=f"{r.get('company', 'report').replace(' ', '_')}.pdf",
                mime="application/pdf",
                key=f"download_report_{idx}"
            )

# ============================================================
# 🔹 Previous Search History
# ============================================================
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
            st.markdown(f"**AI Description:**\n{h.get('description', '')}")
            st.markdown(f"**AI Summary:**\n{h.get('summary', '')}")

            st.subheader("📅 Corporate Events")
            corp_data_raw = h.get("corporate_events")


            # ✅ Ensure corporate events are always parsed into a list of dicts
            corp_data = []
            if corp_data_raw:
                # Case: JSON string (including nested)
                try:
                    corp_data = json.loads(corp_data_raw)
                    if isinstance(corp_data, str):
                        corp_data = json.loads(corp_data)
                except:
                    # Case: Python literal (list/dict stored as text)
                    try:
                        corp_data = ast.literal_eval(corp_data_raw)
                    except:
                        # Case: raw plain text → convert to structured data
                        corp_data = normalize_corporate_events(corp_data_raw)
            
            if not isinstance(corp_data, list):
                corp_data = []
            
            show_corporate_events(corp_data)

            st.subheader("👥 Top Management")
            mgmt_list = normalize_top_management(h.get("top_management"))
            show_top_management(mgmt_list)

            st.subheader("🏢 Subsidiaries")
            show_subsidiaries(get_subsidiaries(query))

            pdf_file = create_pdf_from_text(
                title=query,
                summary=f"{h.get('description', '')}\n\n{h.get('summary', '')}"
            )
            st.download_button("📄 Download PDF", data=pdf_file, file_name=f"{query.replace(' ', '_')}.pdf", mime="application/pdf", key=f"download_history_{idx}")