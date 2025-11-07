# event_finnhub.py
# Fetches company financial corporate events via Finnhub API

import os
import finnhub

FINNHUB_KEY = os.getenv("FINNHUB_API_KEY")
client = finnhub.Client(api_key=FINNHUB_KEY) if FINNHUB_KEY else None


def fetch_finnhub_events(company: str, years: int = 5):
    if not client:
        print("⚠️ Finnhub API key missing, skipping Finnhub events")
        return []

    try:
        response = client.company_earnings(symbol=company.upper(), limit=years * 4)
        events = []

        for item in response:
            events.append({
                "title": f"Earnings Call",
                "date": str(item.get("date", "")),
                "source": "Finnhub API",
                "description": f"{company} earnings report released."
            })

        return events

    except Exception as e:
        print(f"⚠️ Finnhub failed: {e}")
        return []
