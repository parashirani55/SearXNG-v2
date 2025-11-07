import os
import json
import pandas as pd
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

import google.generativeai as genai
# ============================================================
# 🔹 Lazy import helper — breaks circular import safely
# ============================================================
def get_search_company_news():
    """
    Safely imports search_company_news from searxng_analyzer only when needed.
    If not available yet (circular import case), uses fallback.
    """
    try:
        from searxng_analyzer import search_company_news
        return search_company_news
    except Exception:
        from analysis.search_fallback import search_company_news as fallback_search
        return fallback_search


from analysis.corporate_event.event_ai import refine_events_with_ai
from analysis.corporate_event.event_utils import (
    deduplicate_events, merge_and_clean_events, sort_events, validate_event_confidence
)

# ============================================================
# 🔹 Setup
# ============================================================
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")
genai.configure(
    api_key=os.getenv("GEMINI_API_KEY"),
    transport="rest"  # ensures flash-exp works correctly
)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ============================================================
# 🔹 Helper: Ask Gemini for one year (with live context)
# ============================================================
def _ask_gemini_for_year(company: str, year: int, context: str) -> List[Dict[str, Any]]:
    """
    Query Gemini specifically for one year's corporate events.
    Uses:
      - gemini-2.5-flash-exp for current year (fast + live context)
      - gemini-2.5-pro for past years (deep reasoning + historical recall)
    """
    try:
        today = datetime.now().strftime("%B %d, %Y")
        current_year = datetime.now().year

        # ✅ Model selection logic
        if year == current_year:
            model_name = "gemini-2.5-flash-exp"
        else:
            model_name = "gemini-2.5-pro"

        model = genai.GenerativeModel(model_name)
        logging.info(f"🤖 Using model: {model_name} for {company} ({year})")

        # =====================================================
        # 📰 Fetch live news context only for current year
        # =====================================================
        if year == current_year:
            try:
                logging.info(f"🌐 Fetching live news context for {company} ({year})")
                search_company_news = get_search_company_news()
                live_news = search_company_news(company, months=12)
                if live_news:
                    context += f"\n\nRecent verified headlines and filings (past year):\n{live_news[:6000]}"
                    logging.info("✅ Injected live news context into Gemini prompt")
            except Exception as e:
                logging.warning(f"⚠️ Failed to fetch live context → {e}")

        # =====================================================
        # 🧠 Construct Gemini prompt
        # =====================================================
        prompt = rf"""
Today's date is {today}.
You are a senior corporate-finance analyst.

List **all verifiable, publicly announced corporate events** for **{company}**
that occurred or were announced during the year **{year}**.

**Include only:**
- Acquisitions, mergers, divestitures, spin-offs  
- Strategic investments, partnerships, joint ventures  
- Debt/Equity offerings, bond issues, share-repurchase programs  

**Exclude:**
- Earnings releases, dividends, PR announcements, management hires  

Each event should include:
- "date": event or announcement date (YYYY-MM-DD)
- "event_name": short descriptive title
- "description": 2–3 sentences summarizing details, rationale, and impact
- "counterparty": name of involved organization
- "value": transaction value or "Undisclosed"
- "event_type": one of [Acquisition, Merger, Investment, Partnership, Divestiture, Spin-off, Buyback, Bond Issue]

Return strictly valid JSON only:
{{"events": [
  {{
    "date": "YYYY-MM-DD",
    "event_name": "...",
    "description": "...",
    "counterparty": "...",
    "value": "...",
    "event_type": "..."
  }}
]}}
Context:
{context}
"""

        # =====================================================
        # 🔍 Generate and parse Gemini output
        # =====================================================
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.15,
                max_output_tokens=32768
            )
        )

        raw = (response.text or "").strip()
        if raw.startswith("```json"):
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()

        # Parse JSON safely
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*"events".*\[.*\].*\}', raw, re.DOTALL)
            data = json.loads(match.group(0)) if match else {"events": []}

        events = data.get("events", [])
        logging.info(f"✅ Gemini ({model_name}) found {len(events)} events for {year}")
        return events

    except Exception as e:
        logging.warning(f"⚠️ Gemini ({model_name}) failed for {year} → {e}")
        return []

# ============================================================
# 🔹 Helper: Ask Gemini for one month (optional granularity)
# ============================================================
def _ask_gemini_for_month(company: str, year: int, month: int, context: str) -> List[Dict[str, Any]]:
    """Query Gemini for one month's corporate events."""
    try:
        model = genai.GenerativeModel("gemini-2.5-pro")
        month_name = datetime(year, month, 1).strftime("%B")

        prompt = f"""
Today's date is {datetime.now().strftime("%B %d, %Y")}.
You are a senior M&A and corporate-finance analyst.

List **all verifiable, publicly announced** financial or strategic corporate events for **{company}**
that occurred or were announced during **{month_name} {year}**.

If {year} is the current year, include all events **announced or completed so far** this month,
even if they are pending.

Each event must have:
- `"date"`: exact or estimated date (YYYY-MM-DD)
- `"event_name"`: concise title
- `"description"`: 2–3 sentence detailed summary including companies involved, reason, and value
- `"counterparty"`: name(s) of other involved party
- `"value"`: deal amount or 'Undisclosed'
- `"event_type"`: one of [Acquisition, Merger, Investment, Divestiture, Partnership, Spin-off, Buyback, Bond Issue]

Return strictly valid JSON only:
{{"events": [
  {{
    "date": "YYYY-MM-DD",
    "event_name": "...",
    "description": "...",
    "counterparty": "...",
    "value": "...",
    "event_type": "..."
  }}
]}}
Context:
{context}
"""
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=32768
            )
        )

        raw = (response.text or "").strip()
        if raw.startswith("```json"):
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()

        # Parse JSON safely
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*"events".*\[.*\].*\}', raw, re.DOTALL)
            data = json.loads(match.group(0)) if match else {"events": []}

        events = data.get("events", [])
        logging.info(f"✅ Gemini found {len(events)} events for {month_name} {year}")
        return events

    except Exception as e:
        logging.warning(f"⚠️ Gemini failed for {month_name} {year} → {e}")
        return []

# ============================================================
# 🔹 Helper: Ask Gemini for one year (with live context)
# ============================================================
def _ask_gemini_for_year(company: str, year: int, context: str) -> List[Dict[str, Any]]:
    """
    Query Gemini specifically for one year's corporate events.
    Uses gemini-2.5-flash-exp (live-aware) to capture current-year events.
    """
    try:
        model = genai.GenerativeModel("gemini-2.5-pro")
        today = datetime.now().strftime("%B %d, %Y")
        current_year = datetime.now().year

        # =====================================================
        # 📰 Fetch live news context to help Gemini detect recent events
        # =====================================================
        try:
            logging.info(f"🌐 Fetching live news context for {company} (current year)")
            search_company_news = get_search_company_news()
            live_news = search_company_news(company, months=12)

            if live_news:
                context += f"\n\nRecent verified headlines and filings (past year):\n{live_news[:6000]}"
                logging.info("✅ Injected live news context into Gemini prompt")
        except Exception as e:
            logging.warning(f"⚠️ Failed to fetch live context → {e}")

        # =====================================================
        # 🧠 Construct final Gemini prompt
        # =====================================================
        prompt = f"""
Today's date is {today}.
You are a senior corporate-finance analyst.

List **all verifiable, publicly announced corporate events** for **{company}**
from **January 1, {year}** up to **{today}**.

If {year} == {current_year}, include all events announced, completed, or pending so far
(even partial or ongoing transactions).

**Include only:**
- Acquisitions, mergers, divestitures, spin-offs  
- Strategic investments, partnerships, joint ventures  
- Debt/Equity offerings, bond issues, share-repurchase programs  

**Exclude:**
- Earnings releases, dividends, PR announcements, management hires  

Each event should include:
- `"date"`: event or announcement date (YYYY-MM-DD)
- `"event_name"`: short title (e.g., "S&P Global Acquires Visible Alpha")
- `"description"`: 2–3 sentences summarizing the event details, including rationale, scale, and strategic purpose
- `"counterparty"`: involved company or organization
- `"value"`: transaction value (if known)
- `"event_type"`: type of event (Acquisition, Partnership, Investment, etc.)

Return strictly valid JSON only:
{{"events": [
  {{
    "date": "YYYY-MM-DD",
    "event_name": "...",
    "description": "...",
    "counterparty": "...",
    "value": "...",
    "event_type": "..."
  }}
]}}
Context:
{context}
"""


        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=32768
            )
        )

        raw = (response.text or "").strip()
        if raw.startswith("```json"):
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()

        # 🧩 Safe JSON parsing
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*"events".*\[.*\].*\}', raw, re.DOTALL)
            data = json.loads(match.group(0)) if match else {"events": []}

        events = data.get("events", [])
        logging.info(f"✅ Gemini found {len(events)} events for {year}")
        return events

    except Exception as e:
        logging.warning(f"⚠️ Gemini failed for {year} → {e}")
        return []


# ============================================================
# 🔹 Main Function — Year + Month Hybrid
# ============================================================
def generate_verified_corporate_events(company: str, years: int = 5, text: str = None) -> Dict[str, Any]:
    """
    Fetches verifiable corporate events for the last `years` (including current year).
    - Current year → month-by-month (more granular)
    - Past years → yearly summaries
    """
    logging.info(f"🔍 Deep Verified Pipeline → {company} (Last {years} years, including current year)")

    end_year = datetime.now().year
    start_year = end_year - years + 1

    context = (
        f"Company: {company}\n"
        f"Period: {start_year}–{end_year}\n"
        "Focus: Corporate finance, M&A, divestitures, and capital market actions."
    )
    if text:
        context += f"\n\nAdditional Context:\n{text}"

    all_events = []

    # =====================================================
    # 1️⃣ CURRENT YEAR — Month-by-month (granular)
    # =====================================================
    logging.info(f"🗓️ Fetching monthly data for {end_year}")
    for month in range(1, datetime.now().month + 1):
        monthly_events = _ask_gemini_for_month(company, end_year, month, context)
        if not monthly_events:
            monthly_events = refine_events_with_ai(company, [], text=f"{context}\nMonth: {month}/{end_year}")
        all_events.extend(monthly_events)

    # =====================================================
    # 2️⃣ PAST YEARS — Year-by-year (summarized)
    # =====================================================
    for year in range(end_year - 1, start_year - 1, -1):
        logging.info(f"📅 Fetching yearly data for {year}")
        yearly_events = _ask_gemini_for_year(company, year, context)
        if not yearly_events:
            yearly_events = refine_events_with_ai(company, [], text=f"{context}\nYear: {year}")
        all_events.extend(yearly_events)

    logging.info(f"🧩 Total raw events before cleaning: {len(all_events)}")

    # =====================================================
    # 3️⃣ Transform & Clean
    # =====================================================
    # =====================================================
    # 3️⃣ Transform, Clean, and Sort by Year Descending
    # =====================================================
    events = [{
        "year": str(ev.get("date", "Unknown"))[:4],
        "date": ev.get("date", "Unknown"),
        "title": ev.get("event_name", ev.get("title", "Unnamed Event")),
        "description": ev.get("description", ev.get("event_name", "")),
        "event_type": ev.get("event_type", "Other"),
        "counterparty": ev.get("counterparty", "N/A"),
        "amount": ev.get("value", "Undisclosed"),
        "source": "Gemini",
        "url": ev.get("url", ""),
        "confidence": "A"
    } for ev in all_events]

    # Clean and deduplicate events
    events = sort_events(
        merge_and_clean_events(
            validate_event_confidence(
                deduplicate_events(events)
            )
        )
    )

    # Ensure year ordering: latest year first (2025 → older)
    events = sorted(events, key=lambda x: (x["year"], x["date"]), reverse=True)

    logging.info(f"✅ Final verified, cleaned, and ordered events: {len(events)}")

    # =====================================================
    # 4️⃣ Generate Year-Grouped DataFrame
    # =====================================================
    df = pd.DataFrame([{
        "Year": e["year"],
        "Date": e["date"],
        "Event Name/Desc": e["title"],
        "Counter Party": e["counterparty"],
        "Value/Amount": e["amount"],
        "Type": e["event_type"]
    } for e in events])

    # Sort by Year (descending), then Date
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df = df.sort_values(by=["Year", "Date"], ascending=[False, False])

    # Group visually in Markdown
    markdown = ""
    for year in sorted(df["Year"].dropna().unique(), reverse=True):
        markdown += f"\n\n### 📅 {int(year)}\n"
        markdown += df[df["Year"] == year][
            ["Date", "Event Name/Desc", "Counter Party", "Value/Amount", "Type"]
        ].to_markdown(index=False)

    # =====================================================
    # 5️⃣ Save Outputs
    # =====================================================
    outdir = Path(__file__).resolve().parents[2] / "output"
    outdir.mkdir(exist_ok=True)

    csv_path = outdir / f"{company.replace(' ', '_')}_events.csv"
    json_path = outdir / f"{company.replace(' ', '_')}_events.json"

    df.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump({
            "company": company,
            "events": events,
            "verified_count": len(events),
            "last_updated": datetime.utcnow().isoformat()
        }, f, indent=2)

    logging.info(f"✅ Saved to {csv_path} and {json_path}")

    # =====================================================
    # 6️⃣ Return Data
    # =====================================================
    return {
        "company": {"name": company, "symbol": company[:4].upper()},
        "events": events,
        "verified_count": len(events),
        "last_updated": datetime.utcnow().isoformat(),
        "structured_summary": {
            "markdown_table": markdown,
            "key_insights": [
                f"Fetched via Gemini hybrid model ({start_year}–{end_year})",
                "Data grouped year-wise (latest to oldest)"
            ],
            "total_value_estimate": "Aggregated"
        },
        "source_model": "Gemini 2.5 Hybrid Multi-Year Fetch"
    }


    # =====================================================
    # 4️⃣ Save Output
    # =====================================================
    df = pd.DataFrame([{
        "Date": e["date"],
        "Event Name/Desc": e["title"],
        "Counter Party": e["counterparty"],
        "Value/Amount": e["amount"],
        "Type": e["event_type"]
    } for e in events])
    markdown = df.to_markdown(index=False)

    outdir = Path(__file__).resolve().parents[2] / "output"
    outdir.mkdir(exist_ok=True)
    df.to_csv(outdir / f"{company.replace(' ', '_')}_events.csv", index=False)
    with open(outdir / f"{company.replace(' ', '_')}_events.json", "w") as f:
        json.dump({
            "company": company,
            "events": events,
            "verified_count": len(events),
            "last_updated": datetime.utcnow().isoformat()
        }, f, indent=2)

    # =====================================================
    # 5️⃣ Return Data
    # =====================================================
    return {
        "company": {"name": company, "symbol": company[:4].upper()},
        "events": events,
        "verified_count": len(events),
        "last_updated": datetime.utcnow().isoformat(),
        "structured_summary": {
            "markdown_table": markdown,
            "key_insights": [
                f"Fetched via Gemini hybrid model ({start_year}–{end_year})",
                f"Includes monthly breakdown for {end_year} and yearly summaries for {start_year}–{end_year - 1}"
            ],
            "total_value_estimate": "Aggregated"
        },
        "source_model": "Gemini 2.5 Hybrid Multi-Year Fetch"
    }
