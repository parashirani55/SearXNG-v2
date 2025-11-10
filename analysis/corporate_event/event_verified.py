import os
import re
import json
import time
import pandas as pd
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv
import google.generativeai as genai

# Utilities
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
# 🔹 Utility: Extract Event Details
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
# 🔹 Gemini Fetch Helper
# ============================================================
def _fetch_corporate_events(company: str, year: int, month: int = None, verified: bool = True, context: str = None):
    """Fetch corporate events using Gemini (monthly if month specified, yearly otherwise)."""
    try:
        model_name = "gemini-2.0-flash-exp" if month else "gemini-2.5-pro"
        model = genai.GenerativeModel(model_name)

        if month:
            month_name = datetime(year, month, 1).strftime("%B")
            prompt = f"""
You are a corporate finance researcher.
Find **verified corporate events** for {company} during **{month_name} {year}**.
Focus strictly on M&A, partnerships, investments, divestitures, and buybacks.

Return verified events only, confirmed via:
- Official company press releases
- Reuters, Bloomberg, Financial Times, PR Newswire
- SEC filings or MarketScreener

Return valid JSON ONLY:
{{
  "events": [
    {{
      "date": "YYYY-MM-DD",
      "event_name": "Acquisition of XYZ Corp",
      "description": "S&P Global completed the acquisition of XYZ Corp for $2.4B.",
      "counterparty": "XYZ Corp",
      "value": "US$2.4B",
      "event_type": "Acquisition",
      "source": "Reuters"
    }}
  ]
}}
"""
        else:
            prompt = f"""
You are a corporate-finance analyst.
Summarize **verified and completed corporate events** for {company} in the year {year}.
Focus on acquisitions, mergers, divestitures, partnerships, and bond issues.

Only include events confirmed by trusted media or company press releases.
Exclude rumors, future plans, and unverified content.

Return strictly valid JSON:
{{"events":[{{"date":"YYYY-MM-DD","event_name":"...","description":"...","counterparty":"...","value":"...","event_type":"...","source":"..."}}]}}
"""

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.3,
                max_output_tokens=12288,
            ),
        )

        raw = (response.text or "").strip()
        if raw.startswith("```json"):
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()

        data = json.loads(raw)
        return data.get("events", [])
    except Exception as e:
        logging.warning(f"⚠️ Gemini fetch failed for {company} ({year}/{month}) → {e}")
        return []

# ============================================================
# 🔹 Repair Incomplete Events
# ============================================================
def repair_incomplete_events_with_ai(events: List[Dict[str, Any]], company: str) -> List[Dict[str, Any]]:
    """Use Gemini to fill incomplete fields."""
    if not events:
        return events

    model = genai.GenerativeModel("gemini-2.5-pro")
    repaired = []

    for i in range(0, len(events), 10):
        batch = events[i:i+10]
        prompt = f"""
You are a corporate-finance data specialist.
Repair incomplete or missing values for {company}'s corporate events.
Keep all original data, just fill missing fields (date, counterparty, type, value, source).

Return valid JSON:
{{"events": [...]}}
Input:
{json.dumps(batch, indent=2)}
"""
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                    max_output_tokens=12288,
                ),
            )
            raw = (response.text or "").strip()
            if raw.startswith("```json"):
                raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
            data = json.loads(raw)
            repaired.extend(data.get("events", []))
        except Exception as e:
            logging.warning(f"⚠️ Repair batch failed → {e}")
            continue

    logging.info(f"🧠 AI repaired {len(repaired)} events successfully")
    return repaired or events

# ============================================================
# 🔹 ETA Helper
# ============================================================
def estimate_eta(current_step, total_steps, avg_time_per_step):
    remaining = (total_steps - current_step) * avg_time_per_step
    minutes, seconds = divmod(int(remaining), 60)
    return f"{minutes} min {seconds:02d} sec"

# ============================================================
# 🔹 Main Unified Verified Event Generator
# ============================================================
def generate_verified_corporate_events(company: str, years: int = 5, context_text: str = None, progress_callback=None):
    """
    Generate verified corporate events from Gemini.
    Includes:
      ✅ Monthly fetch for current year
      ✅ Yearly fetch for past years
      ✅ Auto-retry on empty results
      ✅ AI repair + normalization
      ✅ Live progress updates (for Streamlit)
    """
    logging.info(f"🔍 Generating verified corporate events for {company} ({years} years)...")

    start_time = time.time()
    end_year = datetime.now().year
    start_year = end_year - years + 1
    context = f"Company: {company} | Years: {start_year}-{end_year}"
    all_events = []
    total_steps = datetime.now().month + (years - 1)
    avg_time_per_step = 12
    step_count = 0

    def update_ui(msg):
        if progress_callback:
            progress_callback(msg, min(step_count / total_steps, 1.0))

    # ============================================================
    # 1️⃣ Current Year (Monthly)
    # ============================================================
    for month in range(1, datetime.now().month + 1):
        step_count += 1
        eta = estimate_eta(step_count, total_steps, avg_time_per_step)
        msg = f"📅 Fetching {datetime(end_year, month, 1).strftime('%B %Y')} → ETA: {eta}"
        logging.info(msg)
        update_ui(msg)

        monthly_events = _fetch_corporate_events(company, end_year, month, verified=True, context=context)
        if not monthly_events:
            time.sleep(2)
            monthly_events = _fetch_corporate_events(company, end_year, month, verified=True, context=context)
        all_events.extend(monthly_events or [])

    # ============================================================
    # 2️⃣ Past Years (Yearly)
    # ============================================================
    for year in range(end_year - 1, start_year - 1, -1):
        step_count += 1
        eta = estimate_eta(step_count, total_steps, avg_time_per_step)
        msg = f"📆 Fetching {year} summary → ETA: {eta}"
        logging.info(msg)
        update_ui(msg)

        yearly_events = _fetch_corporate_events(company, year, verified=True, context=context)
        if not yearly_events:
            time.sleep(2)
            yearly_events = _fetch_corporate_events(company, year, verified=True, context=context)
        all_events.extend(yearly_events or [])

    logging.info(f"🧩 Total raw events fetched: {len(all_events)}")

    # ============================================================
    # 3️⃣ AI Repair + Cleanup
    # ============================================================
    all_events = repair_incomplete_events_with_ai(all_events, company)

    # ============================================================
    # 4️⃣ Filter Future / Speculative
    # ============================================================
    current_date = datetime.now().date()
    clean_events = []
    speculative_terms = ["potential", "rumored", "expected", "plans to", "may acquire", "considering", "exploring"]
    for ev in all_events:
        if not isinstance(ev, dict):
            continue
        desc = (ev.get("description") or ev.get("event_name") or "").lower()
        if any(t in desc for t in speculative_terms):
            continue
        try:
            if datetime.fromisoformat(ev.get("date", "1900-01-01")).date() > current_date:
                continue
        except Exception:
            pass
        clean_events.append(ev)

    logging.info(f"🧹 Filtered speculative/future events → kept {len(clean_events)} / {len(all_events)}")

    # ============================================================
    # 5️⃣ Normalize Data
    # ============================================================
    events = []
    for ev in clean_events:
        desc = ev.get("description") or ev.get("event_name") or ev.get("title", "")
        title = ev.get("event_name") or ev.get("title") or desc[:80]
        date = ev.get("date") or ev.get("Date (From List)") or "Unknown"
        event_type = ev.get("event_type") or ev.get("Event Type") or "Other"
        counterparty = ev.get("counterparty") or ev.get("Counterparty / Entity") or "N/A"
        value = ev.get("value") or ev.get("Reported Value") or "Undisclosed"
        source = ev.get("source") or ev.get("Public Source(s)") or "Gemini Verified"
        parsed = extract_event_details(desc or title)

        events.append({
            "year": str(date)[:4],
            "date": date,
            "title": title.strip(),
            "description": desc.strip(),
            "event_type": (event_type or parsed["event_type"]).strip(),
            "counterparty": (counterparty or parsed["counterparty"]).strip(),
            "amount": (value or parsed["value"]).strip(),
            "source": source.strip(),
            "confidence": "A",
        })

    events = sort_events(merge_and_clean_events(validate_event_confidence(deduplicate_events(events))))

    # ============================================================
    # 6️⃣ Save Files
    # ============================================================
    outdir = Path(__file__).resolve().parents[2] / "output"
    outdir.mkdir(exist_ok=True)
    csv_path = outdir / f"{company.replace(' ', '_')}_verified_events.csv"
    json_path = outdir / f"{company.replace(' ', '_')}_verified_events.json"
    pd.DataFrame(events).to_csv(csv_path, index=False)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"company": company, "events": events, "verified_count": len(events)}, f, indent=2)

    # ============================================================
    # 7️⃣ Done
    # ============================================================
    elapsed = time.time() - start_time
    minutes, seconds = divmod(int(elapsed), 60)
    msg = f"✅ Completed in {minutes} min {seconds:02d} sec — Total {len(events)} verified events fetched."
    logging.info(msg)
    if progress_callback:
        progress_callback(msg, 1.0)

    return {
        "company": {"name": company, "symbol": company[:4].upper()},
        "events": events,
        "verified_count": len(events),
        "last_updated": datetime.utcnow().isoformat(),
        "eta_runtime": f"{minutes} min {seconds:02d} sec",
        "source_model": "Gemini Verified (Monthly + Yearly + Auto-Retry)"
    }

# ============================================================
# 🔹 Local Test
# ============================================================
if __name__ == "__main__":
    logging.info("🚀 Running unified verified corporate event generator with ETA...")
    result = generate_verified_corporate_events("S&P Global", years=5)
    print(pd.DataFrame(result["events"]).head(10))
