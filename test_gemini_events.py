# ============================================================
# test_gemini_events.py — Debug Gemini output only
# ============================================================

import os
import json
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from analysis.corporate_event.event_verified import fetch_verified_finnhub_news, get_ticker_symbol

# Load .env properly
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def test_gemini_output(company: str, years: int = 5):
    print(f"🚀 Testing Gemini 2.5 raw output for: {company}")
    symbol = get_ticker_symbol(company)

    # Fetch real data from Finnhub
    events = fetch_verified_finnhub_news(company, years)
    print(f"✅ {len(events)} verified events fetched from Finnhub")

    if not events:
        print("⚠️ No verified events found. Aborting test.")
        return

    # Prepare Gemini input (use only first 10 to keep output readable)
    event_input = json.dumps(events[:10], indent=2)

    prompt = f"""
You are a professional financial analyst.
Below is verified news data for {company} from Finnhub.
DO NOT invent new events — only fill missing fields if clearly implied.

Return ONLY JSON, in this exact schema:
[
  {{
    "date": "",
    "title": "",
    "description": "",
    "event_type": "",
    "counterparty": "",
    "investment": "",
    "enterprise_value": "",
    "advisors": "",
    "confidence": "",
    "source": "",
    "url": ""
  }}
]

Input data:
{event_input}
"""

    model = genai.GenerativeModel("gemini-2.5-pro")

    response = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.25,
            "response_mime_type": "application/json",
            "max_output_tokens": 32768,
        },
    )

    raw_text = response.text if hasattr(response, "text") else str(response)
    print("\n🧠 GEMINI RAW OUTPUT:\n")
    print(raw_text[:6000])  # show first 6000 chars
    print("\n✅ --- END OF GEMINI OUTPUT ---")

if __name__ == "__main__":
    import sys
    company = sys.argv[1] if len(sys.argv) > 1 else input("Enter company name: ")
    test_gemini_output(company)
