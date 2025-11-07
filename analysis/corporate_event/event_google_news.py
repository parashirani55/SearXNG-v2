# event_google_news.py
# Fetches corporate event-related news from Google via SerpAPI

import os


SERP_API_KEY = os.getenv("SERPAPI_KEY")


def fetch_google_news(company: str):
    from serpapi import GoogleSearch
    if not SERP_API_KEY:
        print("⚠️ SerpAPI key missing, skipping Google News")
        return []

    try:
        search = GoogleSearch({
            "engine": "google_news",
            "q": f"{company} corporate event OR press release OR acquisition",
            "api_key": SERP_API_KEY
        })

        results = search.get_dict().get("news_results", [])
        events = []

        for item in results:
            events.append({
                "title": item.get("title", "Unknown Event"),
                "date": item.get("published_date", ""),
                "source": "Google News",
                "description": item.get("snippet", "")
            })

        return events

    except Exception as e:
        print(f"⚠️ Google News fetch failed: {e}")
        return []
