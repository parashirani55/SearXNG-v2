# analysis/wiki_utils.py
import requests
from bs4 import BeautifulSoup
from serpapi import GoogleSearch
import os
from dotenv import load_dotenv

load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

def get_wikipedia_summary(company_name: str) -> str:
    query = f"{company_name} site:wikipedia.org"
    try:
        search = GoogleSearch({"q": query, "hl": "en", "num": 1, "api_key": SERPAPI_KEY})
        result = search.get_dict().get("organic_results", [{}])[0]
        url = result.get("link")
        if not url:
            return ""
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        paras = [p.get_text() for p in soup.find_all("p") if len(p.get_text()) > 50]
        return " ".join(paras)[:15000]
    except Exception as e:
        print(f"Wiki fetch failed: {e}")
        return ""

def get_wikipedia_subsidiaries(company_name: str):
    try:
        url = f"https://en.wikipedia.org/wiki/{company_name.replace(' ', '_')}"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        subs = set()

        # Infobox
        for row in soup.select("table.infobox tr"):
            th = row.find("th")
            if th and "Subsidiaries" in th.text:
                for a in row.find_all("a"):
                    txt = a.get_text(strip=True)
                    if txt and not txt.startswith(("http", "#")):
                        subs.add(txt)

        # Headings
        for h2 in soup.find_all("h2"):
            if "Subsidiaries" in h2.get_text():
                ul = h2.find_next("ul")
                if ul:
                    for li in ul.find_all("li"):
                        subs.add(li.get_text(strip=True))
        return list(subs)
    except Exception as e:
        print(f"Wiki subs error: {e}")
        return []