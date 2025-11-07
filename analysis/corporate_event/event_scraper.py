import os
import requests
from datetime import datetime
from urllib.parse import quote
from typing import List, Dict, Any

CURRENT_YEAR = datetime.now().year
MIN_YEAR_LIMIT = CURRENT_YEAR - 5
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

FINNHUB_URL_MNA = "https://finnhub.io/api/v1/merger?symbol={}&token={}"


# ✅ Score filter: remove irrelevant PR/Rank news
def _is_valid_event(title: str) -> bool:
    title = title.lower()
    positive_keywords = [
        "acquire", "acquisition", "merger", "invest", "investment",
        "sell", "divest", "spin", "stake", "buy", "funding"
    ]
    negative_keywords = [
        "ranked", "best", "award", "named", "survey", "economy",
        "report", "index", "pmi", "score", "recognition"
    ]

    score = 0
    for w in positive_keywords:
        if w in title: score += 10
    for w in negative_keywords:
        if w in title: score -= 20

    return score >= 5


def fetch_yahoo_finance(company: str) -> List[Dict]:
    events = []
    try:
        res = requests.get(
            f"https://query2.finance.yahoo.com/v1/finance/search?q={quote(company)}",
            timeout=10
        ).json()
    except:
        return events

    for item in res.get("news", []):
        pub_time = item.get("providerPublishTime")
        title = item.get("title", "")

        if not pub_time or not title:
            continue

        dt = datetime.utcfromtimestamp(pub_time)
        if dt.year < MIN_YEAR_LIMIT:
            continue

        if not _is_valid_event(title):
            continue  # ❌ filter junk events

        events.append({
            "description": title,
            "date": dt.strftime("%Y-%m-%d"),
            "type": "Corporate Event",
            "source": "Yahoo Finance"
        })

    return events


def fetch_google_finance(company: str) -> List[Dict]:
    events = []
    try:
        res = requests.get(
            f"https://news.google.com/rss/search?q={quote(company + ' acquisition OR invest OR merger')}&hl=en-IN&gl=IN&ceid=IN:en",
            timeout=10
        )
        if res.status_code != 200:
            return events

        import xml.etree.ElementTree as ET
        root = ET.fromstring(res.text)

        for item in root.findall(".//item"):
            title = item.find("title").text
            pub_date = item.find("pubDate").text

            dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
            if dt.year < MIN_YEAR_LIMIT:
                continue

            if not _is_valid_event(title):
                continue  

            events.append({
                "description": title,
                "date": dt.strftime("%Y-%m-%d"),
                "type": "Corporate Event",
                "source": "Google Finance"
            })
    except:
        pass

    return events


def fetch_finnhub_mna(company: str) -> List[Dict]:
    if not FINNHUB_API_KEY:
        return []

    symbol = company.upper()
    try:
        res = requests.get(
            FINNHUB_URL_MNA.format(symbol, FINNHUB_API_KEY),
            timeout=10
        ).json()
    except:
        return []

    events = []
    for d in res.get("data", []):
        date = d.get("date")
        title = d.get("headline", "")

        if not title:
            continue

        if date and date[:4].isdigit() and int(date[:4]) < MIN_YEAR_LIMIT:
            continue

        if not _is_valid_event(title):
            continue

        events.append({
            "description": title,
            "date": date,
            "type": "M&A",
            "other_party": d.get("partner", "N/A"),
            "investment": d.get("value", "N/A"),
            "source": "Finnhub"
        })

    return events


def scrape_all_sources(company: str) -> List[Dict]:
    events = []
    events.extend(fetch_finnhub_mna(company))
    events.extend(fetch_yahoo_finance(company))
    events.extend(fetch_google_finance(company))
    return events
