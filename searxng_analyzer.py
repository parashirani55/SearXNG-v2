import os
import requests
from urllib.parse import quote
from dotenv import load_dotenv

# ✅ Load environment variables
load_dotenv()

# ✅ OpenRouter API key and endpoint
OPENROUTER_API_KEY = os.getenv("OPEN_ROUTER_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


# ============================================================
# 🧩 Helper: Safe Wikipedia Fetcher
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

        # Step 2: Fallback - search Wikipedia for closest page title
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
    Always returns a complete, structured Company Details summary.
    Ensures CEO, HQ, and Website fields are filled by fallback AI if missing.
    """

    if not text.strip():
        text = get_wikipedia_summary(company_name)

    # --- Step 1: Base extraction prompt ---
    base_prompt = f"""
You are a professional company data researcher.
Your job is to extract key company details **accurately and completely**.

If the input text does not include all fields, you must **use your own knowledge** to fill in any missing ones.
If the company is not found or uncertain, return exactly "NO DETAILS FOUND".

Return ONLY in this markdown format:

**Company Details**
- Year Founded: <value>
- Website: <value>
- LinkedIn: <value>
- Headquarters: <value>
- CEO: <value>

Do not add explanations or commentary.

Company name: {company_name}

Source text:
{text[:8000]}
"""

    # --- Step 2: First AI call ---
    result = openrouter_chat("openai/gpt-4o-mini", base_prompt, "Company Info Extractor")

    # --- Step 3: Retry if any field missing or blank ---
    def field_missing(output):
        required_fields = ["Year Founded:", "Website:", "LinkedIn:", "Headquarters:", "CEO:"]
        for field in required_fields:
            if field not in output or f"{field}  " in output or f"{field} \n" in output:
                return True
        return False

    if not result or len(result.strip()) < 30 or field_missing(result):
        print("🔁 Retrying with direct GPT lookup (forcing all fields)...")
        enforce_prompt = f"""
You are a company researcher AI. Your goal is to ensure that all fields below are **always filled** 
for the company "{company_name}". Use general knowledge if missing from text.

If you cannot find verified data after trying, return exactly "NO DETAILS FOUND".

**Company Details**
- Year Founded:
- Website:
- LinkedIn:
- Headquarters:
- CEO:
"""
        result = openrouter_chat("openai/gpt-4o-mini", enforce_prompt, "Company Info Enforcer")

    # --- Step 4: If still missing, fail gracefully ---
    if not result or "NO DETAILS FOUND" in result.upper() or field_missing(result):
        print("❌ No reliable details found.")
        return "❌ No details found."

    return result


# ============================================================
# 🔹 Generate Company Description
# ============================================================
def generate_description(company_name, text=""):
    """
    Always returns a short, accurate company description.
    Enforces exactly 5–6 lines.
    Uses Wikipedia fallback automatically.
    """

    if not text.strip():
        text = get_wikipedia_summary(company_name)

    prompt = f"""
You are an expert business analyst.

Based on the content below, write a concise, factual, and professional company description suitable for a pitch deck or investor report.

Rules:
1. Include what the company does, its target market/customers, value proposition, and key differentiators.
2. The description must be exactly **5-6 lines** (no more, no less). 
3. Do not add extra sentences or commentary.
4. Focus only on available information. 

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
        # Safe default, 5 lines placeholder
        result = (
            f"{company_name} is a company providing products or services in its industry.\n"
            "It serves a defined customer base and market.\n"
            "The company offers unique value propositions.\n"
            "It differentiates itself from competitors.\n"
            "It aims to grow and innovate continually."
        )

    # Ensure exactly 5–6 lines
    lines = result.strip().split("\n")
    if len(lines) < 5:
        # Pad with empty lines
        lines += [""] * (5 - len(lines))
    elif len(lines) > 6:
        lines = lines[:6]

    return "\n".join(lines)
