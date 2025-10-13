import os
import requests
from urllib.parse import urljoin, quote
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# ✅ Load environment variables
load_dotenv()

# ✅ OpenRouter API key and endpoint
OPENROUTER_API_KEY = os.getenv("OPEN_ROUTER_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


# ============================================================
# 🧩 Helper: Wikipedia Summary
# ============================================================
def get_wikipedia_summary(company_name):
    try:
        encoded_name = quote(company_name)
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded_name}"
        r = requests.get(url, timeout=6)
        if r.status_code == 200:
            data = r.json()
            if "extract" in data and data["extract"].strip() and data.get("type") != "disambiguation":
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
                if "extract" in data2 and data2["extract"].strip() and data2.get("type") != "disambiguation":
                    return data2["extract"]
    except Exception as e:
        print(f"⚠️ Wikipedia fetch error for {company_name}: {e}")
    return ""


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
# 🔹 Website Scraper for About Pages
# ============================================================
def scrape_about_page(base_url):
    try:
        urls_to_try = ["about", "about-us", "team", "leadership", "company"]
        text = ""
        for path in urls_to_try:
            full_url = urljoin(base_url, path)
            r = requests.get(full_url, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                paragraphs = soup.find_all("p")
                page_text = " ".join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
                if page_text:
                    text += page_text + "\n"
        return text.strip()
    except Exception as e:
        print(f"⚠️ Website scraping error: {e}")
        return ""


# ============================================================
# 🔹 Generate Company Summary
# ============================================================
def generate_summary(company_name, text="", base_url=""):
    if not text.strip():
        text = get_wikipedia_summary(company_name)

    # Step 1: AI extraction
    prompt = f"""
You are a professional company data researcher.
Extract all details **accurately**. If missing, use your knowledge.
Return ONLY in this markdown:

**Company Details**
- Year Founded: <value>
- Website: <value>
- LinkedIn: <value>
- Headquarters: <value>
- CEO: <value>
- Founder: <value>

Company name: {company_name}
Source text:
{text[:8000]}
"""
    result = openrouter_chat("openai/gpt-4o-mini", prompt, "Company Info Extractor")

    # Step 2: Check if any required field missing
    required_fields = ["Year Founded:", "Website:", "LinkedIn:", "Headquarters:", "CEO:", "Founder:"]
    def missing_fields(output):
        for f in required_fields:
            if f not in output or f"{f}  " in output or f"{f} \n" in output or f"{f}: <value>" in output:
                return True
        return False

    if not result or missing_fields(result):
        # Step 3: Try website scraping if base_url provided
        if base_url:
            website_text = scrape_about_page(base_url)
            if website_text:
                prompt2 = f"""
You are a professional company researcher.
Use the website content below to fill any missing fields.

**Company Details**
- Year Founded:
- Website:
- LinkedIn:
- Headquarters:
- CEO:
- Founder:

Company name: {company_name}
Website content:
{website_text[:8000]}
"""
                result2 = openrouter_chat("openai/gpt-4o-mini", prompt2, "Website Info Extractor")
                if result2 and not missing_fields(result2):
                    result = result2

    # Step 4: Final fallback
    if not result or missing_fields(result):
        return "❌ No reliable details found."

    return result


# ============================================================
# 🔹 Generate Company Description
# ============================================================
def generate_description(company_name, text="", company_details=""):
    if not text.strip():
        text = get_wikipedia_summary(company_name)

    combined_context = f"""
Verified Company Information:
{company_details if company_details else ''}

Additional Context (Wikipedia or web):
{text[:6000]}
"""
    prompt = f"""
You are a business analyst writing verified company descriptions.
Rules:
- Use ONLY the verified data provided.
- DO NOT invent or guess facts.
- Exactly 5–6 lines.
- Focus on company, products/services, market, and value.

Write the 5–6 line description now.

{combined_context}
"""
    result = openrouter_chat("openai/gpt-4o-mini", prompt, "Factual Company Description")

    if not result or len(result.strip()) < 40:
        # fallback to Wikipedia only
        fallback_text = get_wikipedia_summary(company_name)
        result = openrouter_chat("openai/gpt-4o-mini", prompt.replace(text, fallback_text), "Fallback Description")

    if not result or len(result.strip()) < 40:
        return "❌ No factual description could be generated."

    lines = [line.strip() for line in result.strip().split("\n") if line.strip()]
    if len(lines) < 5:
        lines += [""] * (5 - len(lines))
    elif len(lines) > 6:
        lines = lines[:6]

    return "\n".join(lines)
