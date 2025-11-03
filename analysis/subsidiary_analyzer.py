# analysis/subsidiary_analyzer.py
import json
import re
from serpapi import GoogleSearch
from searxng_db import store_subsidiaries
from .api_client import openrouter_chat
from .wiki_utils import get_wikipedia_subsidiaries
from .logo_fetchers import fetch_logo_free

def generate_subsidiary_data(company_name: str, company_description: str = "") -> list:
    print(f"Generating subsidiaries for {company_name}")
    wiki_subs = get_wikipedia_subsidiaries(company_name)
    serp_links = []
    try:
        params = {
            "q": f"{company_name} subsidiaries OR brands site:linkedin.com OR site:crunchbase.com",
            "num": 20, "api_key": os.getenv("SERPAPI_KEY")
        }
        results = GoogleSearch(params).get_dict().get("organic_results", [])
        serp_links = [r.get("link") for r in results if r.get("link")]
    except: pass

    prompt = f"""
Return ONLY a JSON array of current subsidiaries of "{company_name}".
Each object: {{"name": "", "url": "", "description": "", "sector": "", "linkedin_members": 0, "country": ""}}

Wikipedia names: {wiki_subs}
Links: {" | ".join(serp_links[:15])}
"""
    raw = openrouter_chat("anthropic/claude-3.5-sonnet", prompt, "Subsidiary JSON")
    try:
        subs = json.loads(re.search(r'\[.*\]', raw, re.S).group(0))
    except:
        return []

    for sub in subs:
        name = sub.get("name", "")
        sub["logo"] = fetch_logo_free(name)
        if not sub.get("url"):
            sub["url"] = f"https://www.google.com/search?q={name.replace(' ', '+')}"
        if not isinstance(sub.get("linkedin_members"), int):
            sub["linkedin_members"] = int(re.sub(r"\D", "", str(sub.get("linkedin_members", "0")))) or 0
        store_subsidiaries(company_name, [sub])
    return subs