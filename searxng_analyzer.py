import os
import requests
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import re
from datetime import datetime
import time
import json
from serpapi import GoogleSearch  # Add this import for SerpAPI

# ✅ Load environment variables
load_dotenv()

# ✅ OpenRouter API key and endpoint
OPENROUTER_API_KEY = os.getenv("OPEN_ROUTER_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

# ============================================================
# 🔹 Helper: SerpAPI Search Fallback
# ============================================================
def serpapi_search(query, num_results=5):
    """Fallback search using SerpAPI for company data/events."""
    if not SERPAPI_KEY:
        print("⚠️ SERPAPI_KEY not set; skipping fallback search.")
        return ""
    try:
        params = {"q": query, "hl": "en", "gl": "us", "num": num_results, "api_key": SERPAPI_KEY}
        search = GoogleSearch(params)
        results = search.get_dict().get("organic_results", [])
        combined = "\n".join([f"{res.get('title', '')}: {res.get('snippet', '')}" for res in results[:3]])
        return combined.strip() if combined else ""
    except Exception as e:
        print(f"⚠️ SerpAPI error: {e}")
        return ""

# ============================================================
# 🔹 Helper: Wikidata Events Fetcher
# ============================================================
def get_wikidata_events(company_name):
    """
    Fetch corporate events (M&A, IPOs, investments) from Wikidata using SPARQL.
    Filters for events specific to the company and corporate event types.
    """
    try:
        # Broader SPARQL query to include more corporate events (acquisitions, mergers, spin-offs, etc.)
        query = f"""
        SELECT ?event ?eventLabel ?date ?eventTypeLabel ?value WHERE {{
            ?company wdt:P31/wdt:P279* wd:Q783794 .  # Instance of/subclass of company
            ?company rdfs:label "{company_name}"@en .
            ?event wdt:P710 ?company .  # Event involves the company
            ?event wdt:P585 ?date .     # Event has a date
            OPTIONAL {{ ?event wdt:P2139 ?value . }}  # Optional: financial value
            FILTER(YEAR(?date) >= 2021 && YEAR(?date) <= 2025)
            # Broader event types: mergers, acquisitions, IPOs, investments, spin-offs
            ?event wdt:P31/wdt:P279* ?eventType .
            VALUES ?eventType {{
                wd:Q1491844,  # Merger
                wd:Q563000,  # Acquisition
                wd:Q1127217, # Initial public offering
                wd:Q185142,  # Investment
                wd:Q134556,  # Spin-off
                wd:Q157206   # Business process (broader for partnerships)
            }}
            SERVICE wikibase:label {{ 
                bd:serviceParam wikibase:language "en". 
                ?event rdfs:label ?eventLabel .
                ?eventType rdfs:label ?eventTypeLabel .
            }}
        }}
        ORDER BY DESC(?date)
        LIMIT 10
        """
        url = "https://query.wikidata.org/sparql"
        headers = {"Accept": "application/sparql-results+json"}
        params = {"query": query}
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            events = []
            for item in data.get("results", {}).get("bindings", []):
                event_label = item.get("eventLabel", {}).get("value", "Unknown Event")
                date_str = item.get("date", {}).get("value", "")
                event_type = item.get("eventTypeLabel", {}).get("value", "Corporate Event")
                value = item.get("value", {}).get("value", "N/A")
                if event_label and date_str:
                    # Parse date for consistency
                    date_parsed = parse_date(date_str).strftime("%Y-%m-%d")
                    events.append({
                        "description": f"{company_name} {event_label}",
                        "date": date_parsed,
                        "type": event_type,
                        "value": value
                    })
            return events
        return []
    except Exception as e:
        print(f"⚠️ Wikidata fetch error for {company_name}: {e}")
        return []

# ============================================================
# 🔹 Generate Corporate Events
# ============================================================
def has_recent_events(text, years=[2025, 2024, 2023, 2022, 2021]):
    """Check if any year in `years` appears in the text using regex."""
    found_years = re.findall(r"\b(20\d{2})\b", text)
    for y in found_years:
        if int(y) in years:
            return True
    return False

def parse_date(date_str):
    """Robust date parser for various formats."""
    if not date_str:
        return datetime(1900, 1, 1)
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except:
        try:
            return datetime.strptime(date_str, "%B %d, %Y")
        except:
            try:
                return datetime.strptime(date_str.split("T")[0], "%Y-%m-%d")
            except:
                try:
                    return datetime.strptime(date_str, "%Y")
                except:
                    return datetime(1900, 1, 1)

def generate_corporate_events(company_name, text=""):
    """
    Fetch and merge verified corporate events from multiple sources.
    Ensures all fields (description, date, type, value) are present.
    """
    print(f"🚀 Starting corporate event extraction for: {company_name}")

    all_events = []

    # ============================================================
    # 1️⃣ Try provided text (if any)
    # ============================================================
    if text.strip() and has_recent_events(text):
        try:
            prompt = f"""
            Extract ONLY corporate events (M&A, IPOs, investments, spin-offs) for {company_name} from 2021–2025 from the text below.
            For each event, provide: description (include company name), date (YYYY-MM-DD or closest), type (e.g., Acquisition, Investment, IPO, Spin-off), value (amount if known, else "N/A").
            Return STRICTLY valid JSON array of objects, e.g., [{{"description": "...", "date": "2025-10-15", "type": "Acquisition", "value": "$1.8B"}}]. No other text.
            Text: {text[:4000]}
            """
            response = openrouter_chat("openai/gpt-4o-mini", prompt, "Text Corporate Events")
            if response:
                try:
                    events = json.loads(response)
                    if isinstance(events, list):
                        all_events.extend(events)
                        print("✅ Added events from provided text")
                except json.JSONDecodeError:
                    print("⚠️ Failed to parse provided text events as JSON")
        except Exception as e:
            print(f"⚠️ Error parsing provided text for {company_name}: {e}")

    # ============================================================
    # 2️⃣ Try verified Wikidata events
    # ============================================================
    wikidata_events = get_wikidata_events(company_name)
    if wikidata_events:
        all_events.extend(wikidata_events)
        print("✅ Added verified Wikidata events")

    # ============================================================
    # 3️⃣ Try Website / Press events (Perplexity)
    # ============================================================
    try:
        site_prompt = f"""
        List major corporate events (M&A, IPOs, investments, spin-offs) for {company_name} from 2021–2025 using reliable sources.
        For each: description (include company), date (YYYY-MM-DD), type (Acquisition/Investment/IPOs/Spin-off), value (amount or N/A).
        Return STRICTLY valid JSON array: [{{"description": "...", "date": "2025-10-15", "type": "Acquisition", "value": "$1.8B"}}]. No intro/conclusion.
        """
        site_events_str = openrouter_chat("perplexity/sonar-pro", site_prompt, "Corporate Events Website")
        if site_events_str:
            try:
                events = json.loads(site_events_str)
                if isinstance(events, list) and has_recent_events(str(events)):
                    all_events.extend(events)
                    print("✅ Added press/website events")
            except json.JSONDecodeError:
                print("⚠️ Failed to parse Perplexity response as JSON")
    except Exception as e:
        print(f"⚠️ Site fetch error for {company_name}: {e}")

    # ============================================================
    # 4️⃣ GPT / Claude Fallback
    # ============================================================
    try:
        wiki_prompt = f"""
        Extract key corporate events for {company_name} (M&A, IPOs, investments, spin-offs) 2021–2025.
        For each: description (include company), date (YYYY-MM-DD), type (Acquisition/Investment/IPOs/Spin-off), value (amount or N/A).
        Return STRICTLY valid JSON array: [{{"description": "...", "date": "2021-02-01", "type": "Acquisition", "value": "$12.5B"}}]. No other text.
        """
        chatgpt_events_str = openrouter_chat("anthropic/claude-3.5-sonnet", wiki_prompt, "Corporate Events GPT")
        if chatgpt_events_str:
            try:
                events = json.loads(chatgpt_events_str)
                if isinstance(events, list) and has_recent_events(str(events)):
                    all_events.extend(events)
                    print("✅ Added GPT/Wikipedia-based events")
            except json.JSONDecodeError:
                print("⚠️ Failed to parse GPT response as JSON")
    except Exception as e:
        print(f"⚠️ GPT fetch error for {company_name}: {e}")

    # ============================================================
    # 5️⃣ SerpAPI Fallback for Events (if still empty)
    # ============================================================
    if not all_events:
        print("🔍 Using SerpAPI fallback for corporate events...")
        search_query = f"{company_name} acquisitions mergers investments IPOs spin-offs 2021-2025"
        search_results = serpapi_search(search_query, num_results=10)
        if search_results:
            fallback_prompt = f"""
            From the following search results, extract major corporate events for {company_name} from 2021–2025.
            For each: description (include company), date (YYYY-MM-DD or closest), type (Acquisition/Investment/IPOs/Spin-off), value (amount or N/A).
            Return STRICTLY valid JSON array: [{{"description": "...", "date": "2025-09-01", "type": "Acquisition", "value": "Undisclosed"}}]. No other text.
            Results: {search_results[:4000]}
            """
            fallback_response = openrouter_chat("openai/gpt-4o-mini", fallback_prompt, "SerpAPI Events Fallback")
            if fallback_response:
                try:
                    events = json.loads(fallback_response)
                    if isinstance(events, list):
                        all_events.extend(events)
                        print("✅ Added SerpAPI fallback events")
                except json.JSONDecodeError:
                    print("⚠️ Failed to parse SerpAPI fallback as JSON")

    # ============================================================
    # 6️⃣ Merge, Deduplicate, and Validate Fields
    # ============================================================
    if not all_events:
        return f"⚠️ No verified corporate events found for {company_name}."

    # Deduplicate by description + date
    unique_events = {}
    for event in all_events:
        # Ensure all fields exist with defaults
        desc = event.get("description", f"{company_name} Unknown Event")
        date = event.get("date", "N/A")
        typ = event.get("type", "Corporate Event")
        val = event.get("value", "N/A")
        key = (desc.lower(), date)
        unique_events[key] = {
            "description": desc,
            "date": date,
            "type": typ,
            "value": val
        }

    # Sort by date (newest first)
    sorted_events = sorted(unique_events.values(), key=lambda x: parse_date(x["date"]), reverse=True)

    # Generate formatted output
    output_lines = []
    for event in sorted_events:
        output_lines.append(
            f"- Event Description: {event['description']}\n"
            f"  Date: {event['date']}\n"
            f"  Type: {event['type']}\n"
            f"  Enterprise Value: {event['value']}"
        )

    final_output = "\n\n".join(output_lines)
    print(f"✅ Final merged event timeline for {company_name} ({len(sorted_events)} events)")

    return final_output if final_output else f"⚠️ No verified corporate events found for {company_name}."

# ============================================================
# 🧩 Helper: Wikipedia Summary
# ============================================================
def get_wikipedia_summary(company_name):
    """
    Fetches a company summary from Wikipedia with smart fallback.
    Ensures no wrong or empty results.
    """
    try:
        # Step 1: Direct API attempt
        encoded_name = quote(company_name)
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_name}"
        r = requests.get(url, timeout=6)
        if r.status_code == 200:
            data = r.json()
            if (
                "extract" in data
                and data["extract"].strip()
                and data.get("type") != "disambiguation"
            ):
                return data["extract"]

        # fallback search
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": company_name,
            "format": "json",
            "srlimit": 1,
        }
        search_resp = requests.get(search_url, params=params, timeout=6).json()
        results = search_resp.get("query", {}).get("search", [])

        if results:
            best_title = results[0]["title"]
            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(best_title)}"
            r2 = requests.get(summary_url, timeout=6)
            if r2.status_code == 200:
                data2 = r2.json()
                if (
                    "extract" in data2
                    and data2["extract"].strip()
                    and data2.get("type") != "disambiguation"
                ):
                    return data2["extract"]

    except Exception as e:
        print(f"⚠️ Wikipedia fetch error for {company_name}: {e}")

    # Step 3: Fallback message if absolutely nothing found
    return f"{company_name} is a company that operates in the business domain."


# ============================================================
# 🧩 Helper: OpenRouter Chat Completion
# ============================================================
def openrouter_chat(model, prompt, title):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:3000/",
        "X-Title": title,
        "Content-Type": "application/json",
    }
    data = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=data, timeout=20)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"⚠️ OpenRouter API error: {e}")
        return ""


# ============================================================
# 🔹 Generate Company Summary
# ============================================================
def generate_summary(company_name, text=""):
    """
    Always returns a well-structured Company Details summary.
    Automatically uses Wikipedia if needed.
    """

    # --- Ensure some base content to analyze ---
    if not text.strip():
        text = get_wikipedia_summary(company_name)

    # --- AI extraction prompt ---
    prompt = f"""
You are an expert company information extractor.

Your job is to **always return a structured Company Details summary** — even if the input text is short, incomplete, or unclear.
Do not explain what you are doing or ask for more information.
If a value cannot be confidently found, leave that field blank (but still include it).

---

### 🧾 Extract the Following Fields:
1. **Year Founded**
2. **Website**
3. **LinkedIn**
4. **Headquarters (HQ)**
5. **CEO / Key Executive**

---

### 🧩 Output Rules:
- Always use the **exact markdown format** shown below.  
- Do **not** add commentary, explanations, or disclaimers.  
- If info is missing, still include the field but leave blank.  

---

### ✅ Output Format Example
**Company Details**
- Year Founded: 1907  
- Website: https://www.shell.com  
- LinkedIn: https://linkedin.com/company/shell  
- Headquarters: The Hague, Netherlands  
- CEO: Wael Sawan  

---

Now extract and return **only** in this exact format using the content below:

{text[:8000]}
"""

    result = openrouter_chat("openai/gpt-4o-mini", prompt, "Company Info Extractor")

    # Fallback: if AI gives empty output → use Wikipedia directly
    if not result or len(result.strip()) < 20:
        print("🔍 Fallback to Wikipedia...")
        wiki_text = get_wikipedia_summary(company_name)
        result = openrouter_chat("openai/gpt-4o-mini", prompt.replace(text, wiki_text), "Company Info Extractor")

    # Last resort: safe default
    if not result or len(result.strip()) < 20:
        result = f"""**Company Details**
- Year Founded:  
- Website:  
- LinkedIn:  
- Headquarters:  
- CEO:  
"""

    return result

# ============================================================
# 🔹 Generate Company Description
# ============================================================
def generate_description(company_name, text=""):
    """
    Always returns a short, accurate company description.
    Uses Wikipedia fallback automatically.
    """

    if not text.strip():
        text = get_wikipedia_summary(company_name)

    prompt = f"""
You are an expert business analyst.
Based on the following web content, write a concise, factual, and professional company description suitable for a pitch deck or investor report.

Include:
- What the company does
- Its target customers or market
- Its value proposition
- Key differentiators (if mentioned)

Keep it under 150 words. Focus only on available information.

Content:
{text[:6000]}
"""

    result = openrouter_chat("openai/gpt-4o-mini", prompt, "Company Description Generator")

    # Fallback if AI fails or blank
    if not result or len(result.strip()) < 20:
        print("🔍 Fallback to Wikipedia...")
        wiki_text = get_wikipedia_summary(company_name)
        result = openrouter_chat("openai/gpt-4o-mini", prompt.replace(text, wiki_text), "Company Description Generator")

    if not result or len(result.strip()) < 20:
        result = f"{company_name} is a company providing products or services in its respective industry."

    return result
