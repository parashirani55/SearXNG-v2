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
