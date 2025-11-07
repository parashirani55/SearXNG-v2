# ============================================================
# event_verified_ai.py — Smart Multi-Model AI Corporate Events Pipeline
# ============================================================
# ✅ Auto-switches between models (OpenRouter)
# ✅ Validates and refines structured JSON event output
# ✅ Filters non-financial or irrelevant news
# ✅ M&A, Investments, IPOs, and major financial events only
# ============================================================

import os
import re
import json
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from analysis.corporate_event.event_utils import merge_and_clean_events

# ------------------------------------------------------------
# 🔹 Load environment variables
# ------------------------------------------------------------
load_dotenv()
FINNHUB_KEY = os.getenv("FINNHUB_API_KEY")
OPENROUTER_KEY = os.getenv("OPEN_ROUTER_KEY")

# ------------------------------------------------------------
# 🔹 Initialize OpenRouter Client
# ------------------------------------------------------------
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_KEY,
    default_headers={
        "HTTP-Referer": "https://github.com/",
        "X-Title": "CorporateEventVerifier"
    }
)

# ------------------------------------------------------------
# 🔹 Helper — JSON Extraction
# ------------------------------------------------------------
def extract_json(text: str):
    """Extract valid JSON object from AI output."""
    if not text:
        return None
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


# ------------------------------------------------------------
# 🔹 1. Fetch Company News (Finnhub API)
# ------------------------------------------------------------
def fetch_company_news(company: str, from_date="2024-01-01", to_date=None):
    """Fetch recent company-related financial news."""
    if not FINNHUB_KEY:
        print("⚠️ Missing FINNHUB_API_KEY in .env")
        return []
    if not to_date:
        to_date = datetime.now().strftime("%Y-%m-%d")

    url = f"https://finnhub.io/api/v1/company-news?symbol={company}&from={from_date}&to={to_date}&token={FINNHUB_KEY}"

    try:
        resp = requests.get(url, timeout=15)
        if resp.status_code != 200:
            print(f"⚠️ Finnhub API Error: {resp.status_code} — {resp.text[:100]}")
            return []
        return resp.json()
    except Exception as e:
        print(f"⚠️ Failed to fetch Finnhub news: {e}")
        return []


# ------------------------------------------------------------
# 🔹 2. AI Extraction Flow — Multi-Tier Model Strategy
# ------------------------------------------------------------
def extract_event_fields_ai(company: str, news_item: dict):
    """Convert a single news item into a verified structured event."""
    title = news_item.get("headline", "")
    summary = news_item.get("summary", "")
    date = datetime.fromtimestamp(news_item.get("datetime", 0)).strftime("%Y-%m-%d")
    source = news_item.get("source", "Unknown")
    url = news_item.get("url", "")

    # 🔎 Filter only corporate-financial events
    keywords = [
        "acquire", "merger", "divest", "buyout", "stake",
        "investment", "deal", "transaction", "ipo", "funding"
    ]
    if not any(k in title.lower() for k in keywords):
        return None

    text = f"Title: {title}\nSummary: {summary}\nSource: {source}"

    # 🚦 Model fallback flow: Paid → Free
    models = [
        "openai/gpt-4o-mini",  # high-accuracy (paid)
        "deepseek/deepseek-chat-v3-0324:free",  # fast free fallback
        "mistralai/mistral-nemo:free",           # reliable fallback
    ]

    for model in models:
        try:
            print(f"🤖 Processing via model → {model}")

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a corporate finance analyst. "
                            "Extract verified structured corporate event data from company news. "
                            "Output ONLY valid JSON — no explanations."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"""
Analyze this news related to {company}.
If it describes a corporate financial event (M&A, investment, IPO, funding, or divestment),
return only structured verified details.

Return a valid JSON object:
{{
  "description": "Short event summary",
  "date_announced": "YYYY-MM-DD",
  "type": "Acquisition | Divestment | Investment | IPO | Merger | Funding | Partnership",
  "counterparty_status": "Acquirer | Investor | Divestor | Issuer",
  "other_counterparties": "Name(s) if known",
  "investment_value": "Include currency if available",
  "enterprise_value": "Include value if known",
  "advisors": "Mention any banks/law firms involved if available",
  "confidence": "High | Medium | Low",
  "source": "{source}",
  "url": "{url}"
}}

Text:
{text}
""",
                    },
                ],
                temperature=0.1,
                max_tokens=700,
            )

            # 🔍 Try to parse structured JSON output
            content = response.choices[0].message.content.strip()
            event = extract_json(content)
            if not event:
                print(f"⚠️ Invalid JSON output from {model}, retrying next...")
                continue

            # Ensure required fallback fields
            event.setdefault("date_announced", date)
            event.setdefault("source", source)
            event.setdefault("url", url)
            event.setdefault("confidence", "Medium")

            print(f"✅ Extracted event via {model}")
            return event

        except Exception as e:
            err = str(e)
            if "429" in err:
                print(f"⚠️ {model} rate-limited — switching...")
                time.sleep(1)
                continue
            elif "402" in err:
                print(f"⚠️ {model} requires credits — skipping...")
                continue
            elif "404" in err:
                print(f"⚠️ {model} not available.")
                continue
            else:
                print(f"⚠️ AI extraction error for '{title[:60]}': {e}")
                continue

    print(f"❌ All models failed for: {title[:80]}...")
    return None


# ------------------------------------------------------------
# 🔹 3. Aggregation Logic — Fetch → Analyze → Store
# ------------------------------------------------------------
def generate_verified_events_ai(company: str):
    print(f"🔗 Using OpenRouter Multi-Model AI Flow (GPT-4o → DeepSeek → Mistral)")
    print(f"🚀 Generating verified corporate events for: {company}\n")

    news = fetch_company_news(company)
    if not news:
        print("⚠️ No news articles fetched.")
        return {"company": company, "events": [], "count": 0}

    # Filter relevant news before AI processing
    relevant = [
        n for n in news
        if any(k in n.get("headline", "").lower()
               for k in ["acquire", "merger", "investment", "deal", "ipo", "funding", "stake", "buyout", "divest"])
    ]

    structured_events = []
    for item in relevant:
        event = extract_event_fields_ai(company, item)
        if event:
            structured_events.append(event)

    structured_events = merge_and_clean_events(structured_events)
    print(f"✅ Generated {len(structured_events)} verified structured events.\n")

    result = {
        "company": company,
        "events": structured_events,
        "count": len(structured_events),
        "last_updated": datetime.now().isoformat(),
    }

    os.makedirs("output", exist_ok=True)
    path = f"output/{company}_verified_events.json"
    with open(path, "w") as f:
        json.dump(result, f, indent=2)

    print(f"💾 Saved → {path}")
    return result


# ------------------------------------------------------------
# 🔹 4. CLI Execution
# ------------------------------------------------------------
if __name__ == "__main__":
    import sys

    company = sys.argv[1] if len(sys.argv) > 1 else input("Enter company symbol or name: ")
    result = generate_verified_events_ai(company)
    print(json.dumps(result, indent=2))
