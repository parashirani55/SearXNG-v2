# analysis/logo_fetchers.py
import requests
from bs4 import BeautifulSoup
import re
import base64
from serpapi import GoogleSearch
import os
from dotenv import load_dotenv

load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

def fetch_logo_free(company_name: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    # 1. Wikipedia
    try:
        wiki_url = f"https://en.wikipedia.org/wiki/{company_name.replace(' ', '_')}"
        r = requests.get(wiki_url, headers=headers, timeout=10)
        if r.ok:
            soup = BeautifulSoup(r.text, "html.parser")
            img = soup.select_one("table.infobox img")
            if img and img.get("src"):
                url = img["src"]
                if url.startswith("//"): url = "https:" + url
                data = requests.get(url, timeout=10).content
                b64 = base64.b64encode(data).decode()
                mime = "image/png" if ".png" in url.lower() else "image/jpeg"
                return f"data:{mime};base64,{b64}"
    except: pass

    # 2. DuckDuckGo
    try:
        r = requests.get(f"https://duckduckgo.com/html/?q={company_name}+logo", headers=headers, timeout=10)
        if r.ok:
            soup = BeautifulSoup(r.text, "html.parser")
            for img in soup.find_all("img"):
                src = img.get("src") or ""
                if re.search(r"\.(png|jpg|jpeg|svg)", src, re.I):
                    if src.startswith("//"): src = "https:" + src
                    data = requests.get(src, timeout=10).content
                    b64 = base64.b64encode(data).decode()
                    mime = "image/png" if ".png" in src.lower() else "image/jpeg"
                    return f"data:{mime};base64,{b64}"
    except: pass

    # 3. Favicon
    try:
        domain = company_name.lower().replace(" ", "") + ".com"
        url = f"https://www.google.com/s2/favicons?sz=128&domain_url={domain}"
        r = requests.get(url, timeout=10)
        if r.ok:
            b64 = base64.b64encode(r.content).decode()
            return f"data:image/png;base64,{b64}"
    except: pass

    return "https://www.google.com/s2/favicons?sz=128&domain_url=google.com"


def fetch_logo_from_google(company_name: str) -> str:
    try:
        params = {
            "q": f"{company_name} official company logo filetype:png OR filetype:svg",
            "tbm": "isch", "num": 5, "api_key": SERPAPI_KEY
        }
        results = GoogleSearch(params).get_dict().get("images_results", [])
        for img in results:
            url = img.get("original") or img.get("thumbnail")
            if url and url.startswith("http"):
                r = requests.get(url, timeout=10)
                if r.ok and "image" in r.headers.get("Content-Type", ""):
                    b64 = base64.b64encode(r.content).decode()
                    mime = r.headers.get("Content-Type", "image/png")
                    return f"data:{mime};base64,{b64}"
    except: pass
    return fetch_logo_free(company_name)


def fetch_and_encode_logo(url: str) -> str:
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        mime = r.headers.get("Content-Type", "image/png")
        b64 = base64.b64encode(r.content).decode()
        return f"data:{mime};base64,{b64}"
    except:
        return "https://www.google.com/s2/favicons?sz=64&domain_url=google.com"


def get_google_logo(company_name: str) -> str:
    try:
        search = GoogleSearch({
            "q": f"{company_name} company logo site:pngtree.com OR site:seeklogo.com OR site:wikipedia.org",
            "tbm": "isch", "num": 5, "api_key": SERPAPI_KEY
        })
        for img in search.get_dict().get("images_results", []):
            url = img.get("original") or img.get("thumbnail")
            if url and url.startswith("http"):
                return url
    except: pass
    domain = company_name.lower().replace(" ", "") + ".com"
    return f"https://www.google.com/s2/favicons?sz=64&domain_url={domain}"