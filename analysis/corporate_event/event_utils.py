from datetime import datetime
import re
from typing import List, Dict, Any

# ============================================================
# Text Cleaning — Safe for Lists, Strings, None
# ============================================================
def clean_text(text) -> str:
    """Safely clean text: accepts str, list, or None → returns str"""
    if isinstance(text, list):
        text = " ".join(str(i).strip() for i in text if i)
    if not isinstance(text, str):
        text = str(text or "")
    text = re.sub(r"<[^>]+>", "", text)  # strip HTML
    text = re.sub(r"\s+", " ", text).strip()  # collapse spaces
    return text


# ============================================================
# Date Normalization
# ============================================================
def normalize_date(date_str: str) -> str:
    if not date_str or not isinstance(date_str, str):
        return "Unknown"
    date_str = date_str.strip().replace("·", "").replace(",", "")
    formats = [
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y",
        "%b %d %Y", "%B %d %Y", "%d %b %Y", "%d %B %Y",
        "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        return str(datetime.fromisoformat(date_str.split("T")[0]).date())
    except Exception:
        return "Unknown"


# ============================================================
# Deduplication
# ============================================================
def deduplicate_events(events: List[Dict]) -> List[Dict]:
    seen = set()
    unique = []
    for e in events:
        key = (
            clean_text(e.get("title") or e.get("description") or "").lower(),
            e.get("date", "Unknown"),
            clean_text(e.get("source") or "").lower()
        )
        if key not in seen:
            seen.add(key)
            unique.append(e)
    return unique


# ============================================================
# Merge & Clean — Fully Safe
# ============================================================
def merge_and_clean_events(events: List[Dict]) -> List[Dict]:
    if not events or not isinstance(events, list):
        return []

    cleaned = []
    for evt in events:
        title = clean_text(evt.get("title") or evt.get("description") or evt.get("event_name") or "")
        if not title or title in ["Unknown", ""]:
            continue

        cleaned.append({
            "date": normalize_date(clean_text(evt.get("date") or "")),
            "title": title,
            "description": clean_text(evt.get("description") or title),
            "event_type": clean_text(evt.get("event_type") or evt.get("type") or "Other"),
            "counterparty": clean_text(evt.get("counterparty") or evt.get("other_party") or evt.get("counter_party") or ""),
            "amount": clean_text(evt.get("amount") or evt.get("investment") or evt.get("value") or "Undisclosed"),
            "enterprise_value": clean_text(evt.get("enterprise_value") or "Not available"),
            "advisors": clean_text(evt.get("advisors") or "N/A"),
            "source": clean_text(evt.get("source") or "Unknown"),
            "url": clean_text(evt.get("url") or evt.get("link") or ""),
            "confidence": evt.get("confidence", "C"),
        })

    cleaned = deduplicate_events(cleaned)
    return sort_events(cleaned)


# ============================================================
# Sorting by completeness & recency
# ============================================================
def sort_events(events: List[Dict]) -> List[Dict]:
    def completeness_score(e):
        score = 0
        if e.get("date") not in ["Unknown", "N/A"]: score += 3
        if e.get("event_type") not in ["Unknown", "Other", None]: score += 2
        if e.get("counterparty") not in ["Unknown", "Not available", ""]: score += 1
        if e.get("amount") not in ["Not available", "Unknown", "–"]: score += 1
        return score

    for e in events:
        try:
            e["_sort_date"] = datetime.fromisoformat(e["date"]) if e["date"] not in ["Unknown", "N/A"] else datetime.min
        except Exception:
            e["_sort_date"] = datetime.min

    sorted_events = sorted(events, key=lambda e: (completeness_score(e), e["_sort_date"]), reverse=True)
    for e in sorted_events:
        e.pop("_sort_date", None)
    return sorted_events


# ============================================================
# Confidence Assignment
# ============================================================
def validate_event_confidence(events: List[Dict]) -> List[Dict]:
    for e in events:
        if e.get("confidence") in ["A", "B", "C"]:
            continue
        source = str(e.get("source", "")).lower()
        if any(x in source for x in ["gemini", "finnhub", "sec", "reuters", "bloomberg"]):
            e["confidence"] = "A"
        elif any(x in source for x in ["prnewswire", "businesswire", "cnbc", "forbes"]):
            e["confidence"] = "B"
        else:
            e["confidence"] = "C"
    return events
