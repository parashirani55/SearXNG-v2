import os
import requests
from urllib.parse import quote
from dotenv import load_dotenv
import re
from datetime import datetime
import time
import json
from serpapi import GoogleSearch

# ✅ Load environment variables
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPEN_ROUTER_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# ============================================================
# 🧩 OpenRouter Chat Completion Helper
# ============================================================
def openrouter_chat(model, prompt, title):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": title
    }
    data = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=20)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"⚠️ OpenRouter API error ({title}): {e}")
        return ""

# ============================================================
# 🔹 SerpAPI Fallback
# ============================================================
def serpapi_search(query, num_results=5):
    if not SERPAPI_KEY:
        return ""
    try:
        params = {"q": query, "hl": "en", "gl": "us", "num": num_results, "api_key": SERPAPI_KEY}
        search = GoogleSearch(params)
        results = search.get_dict().get("organic_results", [])
        return "\n".join([f"{r.get('title', '')}: {r.get('snippet', '')}" for r in results[:num_results]])
    except Exception as e:
        print(f"⚠️ SerpAPI error: {e}")
        return ""

# ============================================================
# 🔹 Date Parsing & Validation
# ============================================================
def parse_date(date_str):
    if not date_str:
        return datetime(1900, 1, 1)
    for fmt in ("%Y-%m-%d", "%B %d, %Y", "%Y"):
        try:
            return datetime.strptime(date_str.split("T")[0], fmt)
        except:
            continue
    return datetime(1900, 1, 1)

def has_recent_events(text, years=[2021, 2022, 2023, 2024, 2025]):
    found_years = re.findall(r"\b(20\d{2})\b", text)
    return any(int(y) in years for y in found_years)

# ============================================================
# 🔹 Wikipedia Summary Fetcher
# ============================================================
def get_wikipedia_summary(company_name):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        encoded_name = quote(company_name.replace('&', '%26'))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_name}"
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if "extract" in data and data.get("type") != "disambiguation":
                return data["extract"]
    except Exception as e:
        print(f"⚠️ Wikipedia fetch error: {e}")
    return ""

# ============================================================
# 🔹 Corporate Events Generator
# ============================================================
def generate_corporate_events(company_name, text=""):
    print(f"🚀 Extracting corporate events for {company_name}")
    all_events = []

    # 1️⃣ Wikipedia / text-based events
    if text.strip():
        wiki_prompt = f"""
        Extract ONLY corporate events (M&A, IPOs, investments, spin-offs) for {company_name} from 2021–2025.
        For each event, provide JSON object with: description (include company), date (YYYY-MM-DD), type, value (or empty if unknown).
        Text: {text[:4000]}
        """
        wiki_events = openrouter_chat("perplexity/sonar-pro", wiki_prompt, "Corporate Events Wikipedia")
        try:
            events = json.loads(wiki_events)
            if isinstance(events, list):
                all_events.extend(events)
                print("✅ Added events from Wikipedia/text")
        except Exception:
            print("⚠️ Failed to parse Wikipedia events")

    # 2️⃣ GPT fallback events
    chatgpt_prompt = f"""
    Extract corporate events (M&A, IPOs, investments, spin-offs) for {company_name} 2021–2025.
    Return STRICTLY JSON array: description, date (YYYY-MM-DD), type, value (or empty if unknown).
    """
    chatgpt_events = openrouter_chat("anthropic/claude-3.5-sonnet", chatgpt_prompt, "Corporate Events GPT")
    try:
        events = json.loads(chatgpt_events)
        if isinstance(events, list):
            all_events.extend(events)
            print("✅ Added GPT events")
    except Exception:
        print("⚠️ Failed to parse GPT events")

    # 3️⃣ Website / press events
    site_events_prompt = f"""
    List corporate events (M&A, IPOs, investments, spin-offs) for {company_name} 2021–2025 using reliable sources.
    Return STRICTLY JSON array: description, date (YYYY-MM-DD), type, value (or empty if unknown).
    """
    site_events = openrouter_chat("perplexity/sonar-pro", site_events_prompt, "Corporate Events Website")
    try:
        events = json.loads(site_events)
        if isinstance(events, list):
            all_events.extend(events)
            print("✅ Added website/press events")
    except Exception:
        print("⚠️ Failed to parse website/press events")

    if not all_events:
        return f"⚠️ No corporate events found for {company_name}"

    # Deduplicate by description + date
    unique_events = {}
    for e in all_events:
        desc = e.get("description", f"{company_name} Unknown Event")
        date = e.get("date", "N/A")
        typ = e.get("type", "Corporate Event")
        val = e.get("value", "")
        key = (desc.lower(), date)
        unique_events[key] = {"description": desc, "date": date, "type": typ, "value": val}

    # Sort by date descending
    sorted_events = sorted(unique_events.values(), key=lambda x: parse_date(x["date"]), reverse=True)

    # Format output
    output_lines = [
        f"- Event Description: {e['description']}\n  Date: {e['date']}\n  Type: {e['type']}\n  Value: {e['value']}"
        for e in sorted_events
    ]
    return "\n\n".join(output_lines)

# ============================================================
# 🔹 Company Summary Generator
# ============================================================
def generate_summary(company_name, text=""):
    if not text.strip():
        text = get_wikipedia_summary(company_name)

    prompt = f"""
You are a professional researcher. Extract complete company details for "{company_name}".
Return ONLY in this markdown format:

**Company Details**
- Year Founded: <value>
- Website: <value>
- LinkedIn: <value>
- Headquarters: <value>
- CEO: <value>

Source text:
{text[:8000]}
"""
    result = openrouter_chat("openai/gpt-4o-mini", prompt, "Company Info Extractor")
    return result or "❌ No details found."

# ============================================================
# 🔹 Company Description Generator
# ============================================================
def generate_description(company_name, text="", company_details=""):
    if not text.strip():
        text = get_wikipedia_summary(company_name)
    combined_context = f"""
Verified Company Information:
{company_details if company_details else ''}

Additional Context:
{text[:6000]}
"""
    prompt = f"""
Write a factual 5–6 line company description for "{company_name}" using ONLY the verified information provided.
Do NOT invent data. Focus on what the company does, its products/services, market, and value.
{combined_context}
"""
    result = openrouter_chat("openai/gpt-4o-mini", prompt, "Factual Company Description")
    if not result or len(result.strip()) < 40:
        return "❌ No factual description could be generated."
    lines = [l.strip() for l in result.split("\n") if l.strip()]
    if len(lines) < 5:
        lines += [""] * (5 - len(lines))
    elif len(lines) > 6:
        lines = lines[:6]
    return "\n".join(lines)
