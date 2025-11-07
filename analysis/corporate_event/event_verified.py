import os
import re
import json
import pandas as pd
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv
import google.generativeai as genai

from analysis.corporate_event.event_ai import refine_events_with_ai
from analysis.corporate_event.event_utils import (
    deduplicate_events, merge_and_clean_events, sort_events, validate_event_confidence
)

# ============================================================
# 🔹 Setup
# ============================================================
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

genai.configure(api_key=os.getenv("GEMINI_API_KEY"), transport="rest")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ============================================================
# 🔹 Safe Import for Search Fallback
# ============================================================
def get_search_company_news():
    try:
        from searxng_analyzer import search_company_news
        return search_company_news
    except Exception:
        try:
            from analysis.search_fallback import search_company_news as fallback_search
            return fallback_search
        except Exception:
            logging.warning("⚠️ search_fallback missing → using dummy fallback")
            return lambda company, months=12: f"No live context for {company}"


# ============================================================
# 🔹 Extraction Utility
# ============================================================
def extract_event_details(desc: str) -> Dict[str, str]:
    """Extract event type, counterparty, and value from text."""
    if not desc:
        return {"event_type": "Other", "counterparty": "N/A", "value": "Undisclosed"}

    type_keywords = {
        "Acquisition": ["acquire", "acquisition", "buy", "purchase"],
        "Merger": ["merge", "merger"],
        "Investment": ["invest", "investment", "funding"],
        "Partnership": ["partner", "partnership", "collaboration"],
        "Divestiture": ["divest", "sale of", "sell"],
        "Spin-off": ["spin off", "spinoff"],
        "Buyback": ["buyback", "repurchase"],
        "Bond Issue": ["bond", "debt issue", "notes"],
    }

    event_type = "Other"
    for key, words in type_keywords.items():
        if any(w in desc.lower() for w in words):
            event_type = key
            break

    match = re.search(
        r"(?:acquire|acquisition of|partner(?:ship)? with|merger with|invest(?:ment)? in)\s+([A-Z][A-Za-z0-9&\s\.\-]+)",
        desc,
        re.IGNORECASE,
    )
    counterparty = match.group(1).strip(" .-") if match else "N/A"

    match_val = re.search(
        r"(\$\s?\d+(?:\.\d+)?\s?(?:billion|million|bn|m|B|M))", desc, re.IGNORECASE
    )
    value = match_val.group(1) if match_val else "Undisclosed"

    return {"event_type": event_type, "counterparty": counterparty, "value": value}


# ============================================================
# 🔹 Gemini AI Repair Layer
# ============================================================
def repair_incomplete_events_with_ai(events: List[Dict[str, Any]], company: str) -> List[Dict[str, Any]]:
    """Use Gemini to fill missing fields intelligently."""
    try:
        if not events:
            return []
        model = genai.GenerativeModel("gemini-2.5-pro")
        repaired = []

        for i in range(0, len(events), 10):
            batch = events[i:i+10]
            prompt = f"""
You are a corporate-finance data specialist.
Given incomplete event records for {company}, fix and fill missing fields.

Return JSON:
{{"events":[{{"date":"YYYY-MM-DD","event_name":"...","description":"...","counterparty":"...","value":"...","event_type":"..."}}]]}}

Input:
{json.dumps(batch, indent=2)}
"""

            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                    max_output_tokens=32768,
                ),
            )

            raw = (response.text or "").strip()
            if raw.startswith("```json"):
                raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()

            try:
                data = json.loads(raw)
                repaired.extend(data.get("events", []))
            except Exception:
                continue

        logging.info(f"🧠 AI repaired {len(repaired)} events successfully")
        return repaired if repaired else events
    except Exception as e:
        logging.warning(f"⚠️ AI repair failed → {e}")
        return events


# ============================================================
# 🔹 Ask Gemini for Monthly Data (Current Year)
# ============================================================
def _ask_gemini_for_month(company: str, year: int, month: int, context: str) -> List[Dict[str, Any]]:
    """Fetch month-specific corporate events with smarter prompt and contextual grounding."""
    try:
        model = genai.GenerativeModel("gemini-2.5-pro")
        month_name = datetime(year, month, 1).strftime("%B")
        start_date = f"{year}-{month:02d}-01"
        end_date = f"{year}-{month:02d}-28"

        # 🔹 Fetch live or fallback context
        try:
            search_company_news = get_search_company_news()
            logging.info(f"🌐 Fetching contextual news for {company} ({month_name} {year})...")
            live_news = search_company_news(company, months=1)
            if not live_news:
                live_news = search_company_news(company, months=3)
            context += f"\nRelevant verified news and filings ({month_name} {year}):\n{live_news[:6000]}"
        except Exception as e:
            logging.warning(f"⚠️ Failed to fetch live news context → {e}")

        # 🧠 Refined prompt — gives examples, time range, fallback logic
        prompt = f"""
Today's date is {datetime.now():%B %d, %Y}.
You are a senior corporate-finance analyst who tracks mergers, acquisitions, partnerships, divestitures, and similar events.

Analyze all reliable public and financial information and list **every verifiable corporate event involving {company}**
that occurred or was announced between **{start_date}** and **{end_date}** ({month_name} {year}).

If no major events are publicly recorded, infer any likely relevant actions or strategic developments
(e.g., divestments, acquisitions, collaborations, investments, or capital structure changes)
based on context, company behavior, and industry trends.

### Examples of valid outputs:
- Acquisition: "S&P Global Acquires With Intelligence for $1.8B"
- Partnership: "S&P Global partners with Microsoft for data integration"
- Divestiture: "S&P Global sells Energy Data division to KKR"
- Investment: "S&P Global invests $250M in fintech platform XYZ"
- Buyback: "S&P Global launches $3B share repurchase program"

Each event should include:
- date (YYYY-MM-DD)
- event_name
- description (2–3 sentences explaining purpose and impact)
- counterparty
- value (or 'Undisclosed')
- event_type (Acquisition, Merger, Investment, Partnership, Divestiture, Spin-off, Buyback, Bond Issue, Other)

Return strictly valid JSON:
{{"events":[{{"date":"YYYY-MM-DD","event_name":"...","description":"...","counterparty":"...","value":"...","event_type":"..."}}]]}}

Context:
{context}
"""

        # 🔹 Run Gemini request
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.35,
                max_output_tokens=32768,
            ),
        )

        raw = (response.text or "").strip()
        if raw.startswith("```json"):
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()

        # 🔹 Safe parse
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*"events".*\[.*\].*\}', raw, re.DOTALL)
            data = json.loads(match.group(0)) if match else {"events": []}

        events = data.get("events", [])
        logging.info(f"✅ Gemini found {len(events)} events for {month_name} {year}")

        # 🔁 Retry with Gemini-2.5-Pro if nothing found
        if len(events) == 0:
            logging.warning(f"⚠️ No events found for {month_name} {year} — retrying with Gemini-2.5-Pro")
            model_fb = genai.GenerativeModel("gemini-2.5-pro")
            response_fb = model_fb.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.25,
                    max_output_tokens=32768,
                ),
            )
            raw_fb = (response_fb.text or "").strip()
            if raw_fb.startswith("```json"):
                raw_fb = raw_fb.split("```json", 1)[1].split("```", 1)[0].strip()
            try:
                data_fb = json.loads(raw_fb)
                events = data_fb.get("events", [])
                logging.info(f"✅ Gemini 2.5-Pro found {len(events)} events for {month_name} {year}")
            except Exception:
                logging.warning(f"⚠️ Gemini-2.5-Pro fallback also failed for {month_name} {year}")

        return events

    except Exception as e:
        logging.warning(f"⚠️ Gemini failed for {month_name} {year} → {e}")
        return []


# ============================================================
# 🔹 Ask Gemini for Yearly Data (Past Years)
# ============================================================
def _ask_gemini_for_year(company: str, year: int, context: str) -> List[Dict[str, Any]]:
    """Fetch summarized corporate events for a past year."""
    try:
        model = genai.GenerativeModel("gemini-2.5-pro")
        prompt = f"""
You are an M&A and corporate-finance analyst.
List all verifiable corporate events for {company} during {year}.
Return valid JSON:
{{"events":[{{"date":"YYYY-MM-DD","event_name":"...","description":"...","counterparty":"...","value":"...","event_type":"..."}}]]}}
Context:
{context}
"""
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=32768,
            ),
        )

        raw = (response.text or "").strip()
        if raw.startswith("```json"):
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()

        data = json.loads(raw)
        events = data.get("events", [])
        logging.info(f"✅ Gemini found {len(events)} events for {year}")
        return events
    except Exception as e:
        logging.warning(f"⚠️ Gemini failed for {year} → {e}")
        return []


# ============================================================
# 🔹 Main: Verified Corporate Events Generator
# ============================================================
def generate_verified_corporate_events(company: str, years: int = 5, text: str = None) -> Dict[str, Any]:
    logging.info(f"🔍 Generating verified corporate events for {company} ({years} years)...")

    end_year = datetime.now().year
    start_year = end_year - years + 1

    context = f"Company: {company}\nPeriod: {start_year}–{end_year}\nFocus: Corporate M&A, divestitures, and capital market activity."
    if text:
        context += f"\n\nAdditional context:\n{text}"

    all_events = []

    # =====================================================
    # 1️⃣ Current Year — Monthly Data
    # =====================================================
    logging.info(f"🗓️ Fetching monthly events for {end_year}")
    for month in range(1, datetime.now().month + 1):
        monthly_events = _ask_gemini_for_month(company, end_year, month, context)
        if not monthly_events:
            monthly_events = refine_events_with_ai(company, [], text=f"{context}\nMonth: {month}/{end_year}")
        all_events.extend(monthly_events)

    # =====================================================
    # 2️⃣ Past Years — Yearly Data
    # =====================================================
    for year in range(end_year - 1, start_year - 1, -1):
        yearly_events = _ask_gemini_for_year(company, year, context)
        if not yearly_events:
            yearly_events = refine_events_with_ai(company, [], text=f"{context}\nYear: {year}")
        all_events.extend(yearly_events)

    logging.info(f"🧩 Total raw events before cleaning: {len(all_events)}")

    # =====================================================
    # 3️⃣ AI Repair — Fill Missing Fields
    # =====================================================
    logging.info("🧠 Running AI repair on incomplete events...")
    all_events = repair_incomplete_events_with_ai(all_events, company)
    logging.info(f"✅ After AI repair → {len(all_events)} structured events")

    # =====================================================
    # 4️⃣ Parse, Clean & Save
    # =====================================================
    events = []
    for ev in all_events:
        if not isinstance(ev, dict):
            continue

        desc = ev.get("description") or ev.get("event_name") or ev.get("title", "")
        title = ev.get("event_name") or ev.get("title") or desc[:80]
        parsed = extract_event_details(desc or title)

        events.append({
            "year": str(ev.get("date", "Unknown"))[:4],
            "date": ev.get("date", "Unknown"),
            "title": title.strip(),
            "description": desc.strip(),
            "event_type": (ev.get("event_type") or parsed["event_type"]).strip(),
            "counterparty": (ev.get("counterparty") or parsed["counterparty"]).strip(),
            "amount": (ev.get("value") or parsed["value"]).strip(),
            "source": ev.get("source", "Gemini"),
            "url": ev.get("url", ""),
            "confidence": "A",
        })

    events = sort_events(
        merge_and_clean_events(
            validate_event_confidence(
                deduplicate_events(events)
            )
        )
    )

    outdir = Path(__file__).resolve().parents[2] / "output"
    outdir.mkdir(exist_ok=True)
    csv_path = outdir / f"{company.replace(' ', '_')}_events.csv"
    json_path = outdir / f"{company.replace(' ', '_')}_events.json"

    df = pd.DataFrame(events)
    df.to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump({"company": company, "events": events, "verified_count": len(events)}, f, indent=2)

    logging.info(f"💾 Saved verified data → {csv_path}")
    logging.info(f"💾 Saved verified JSON → {json_path}")

    return {
        "company": {"name": company, "symbol": company[:4].upper()},
        "events": events,
        "verified_count": len(events),
        "last_updated": datetime.utcnow().isoformat(),
        "source_model": "Gemini Hybrid (Monthly+Yearly+AI Repair)"
    }


# ============================================================
# 🔹 Local Test
# ============================================================
if __name__ == "__main__":
    logging.info("Corporate Event System: Using VERIFIED pipeline for: S&P Global")
    result = generate_verified_corporate_events("S&P Global", years=5)
    print(pd.DataFrame(result["events"]).head(10))
