import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from serpapi import GoogleSearch
import os
from searxng_analyzer import generate_summary  # For GPT fallback

# Optional: Playwright for JS-heavy sites
from playwright.sync_api import sync_playwright

def scrape_static_page(url):
    """Scrape static HTML from a page."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        texts = []

        for tag in soup.find_all(["p", "div", "article", "section"]):
            txt = tag.get_text(separator=" ", strip=True)
            if len(txt) > 50:
                texts.append(txt)

        return " ".join(texts)
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ""

def scrape_js_page(url, timeout=60000):
    """Scrape JS-heavy page using Playwright."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=timeout)
            text = page.inner_text("body")
            browser.close()
            return text
    except Exception as e:
        print(f"Error scraping JS page {url}: {e}")
        return ""

def fetch_wikipedia_text(company_name):
    """Fetch company Wikipedia text using SerpAPI."""
    query = f"{company_name} site:wikipedia.org"
    params = {
        "q": query,
        "hl": "en",
        "gl": "us",
        "num": 1,
        "api_key": os.getenv("SERPAPI_KEY")
    }
    try:
        search = GoogleSearch(params)
        results = search.get_dict().get("organic_results", [])
        if not results:
            return ""
        wiki_url = results[0].get("link")
        if not wiki_url:
            return ""
        r = requests.get(wiki_url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        paragraphs = [p.get_text() for p in soup.find_all("p") if len(p.get_text()) > 50]
        return " ".join(paragraphs)
    except Exception as e:
        print(f"Error fetching Wikipedia text for {company_name}: {e}")
        return ""

def scrape_website(base_url=None, company_name=None, use_js_fallback=True):
    """
    Scrape company info with layered fallback:
    1. Try website: /, /about, /leadership
    2. JS rendering if site scraping too short
    3. Wikipedia fallback
    4. GPT fallback if all else fails
    """
    combined_text = ""

    # --- 1️⃣ Website scraping ---
    if base_url:
        pages_to_scrape = [
            base_url,
            urljoin(base_url, "/about"),
            urljoin(base_url, "/leadership")
        ]

        for url in pages_to_scrape:
            text = scrape_static_page(url)
            combined_text += text + " "

        if use_js_fallback and len(combined_text.strip()) < 500:
            print("Static scraping insufficient, using JS rendering...")
            js_text = scrape_js_page(base_url)
            combined_text += js_text

    # --- 2️⃣ Wikipedia fallback ---
    if company_name and len(combined_text.strip()) < 500:
        print("Content too short, trying Wikipedia...")
        wiki_text = fetch_wikipedia_text(company_name)
        combined_text += wiki_text

    # --- 3️⃣ GPT fallback ---
    if company_name and len(combined_text.strip()) < 500:
        print("Still insufficient, using GPT to generate company info...")
        combined_text = generate_summary(f"Provide company info for: {company_name}")

    return combined_text.strip()
