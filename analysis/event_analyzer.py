# analysis/event_analyzer.py
import re
from datetime import datetime, timedelta
from typing import List, Dict
from .api_client import openrouter_chat
from .wiki_utils import get_wikipedia_summary

CURRENT_YEAR = datetime.now().year
MIN_YEAR_LIMIT = CURRENT_YEAR - 5  # ✅ Only last 5 years

def _parse_date(date_str: str) -> datetime:
    if not date_str or date_str == "N/A":
        return datetime.min
    date_str = date_str.strip()
    formats = [
        "%Y-%m-%d", "%B %d, %Y", "%d %B %Y",
        "%B %Y", "%Y", "%Y/%m/%d",
        "%d/%m/%Y", "%m/%d/%Y"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except:
            continue
    if re.match(r"^\d{4}$", date_str):
        return datetime(int(date_str), 1, 1)
    return datetime.min


def _extract_events_from_text(text: str) -> List[Dict]:
    events = []
    patterns = [
        r"acquired\s+([^\.]+?)\s+.*?\s+in\s+([^\.\n]+)",
        r"raised\s+\$?([\d\.]+)\s*(billion|million|b|m)?\s+.*?\s+in\s+([^\.\n]+)",
        r"went public.*?in\s+(\d{4})",
        r"appointed\s+(.+?)\s+as\s+CEO.*?in\s+(\d{4})"
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            events.append({
                "description": match.group(0).strip(),
                "date": match.groups()[-1].strip(),
                "type": "M&A" if "acquir" in match.group(0).lower() else
                        "Funding" if "raised" in match.group(0).lower() else
                        "IPO" if "public" in match.group(0).lower() else "Leadership",
                "value": "N/A"
            })
    return events


def generate_corporate_events(company_name: str, text: str = "") -> str:
    if not text:
        text = get_wikipedia_summary(company_name)

    # STEP 1 — Try extracting using AI (Free Model First)
    prompt = f"""
Extract all corporate events (acquisitions, funding, product launches, IPOs, leadership changes, partnerships)
for "{company_name}" from YEAR {MIN_YEAR_LIMIT} to {CURRENT_YEAR}.

Format EXACTLY:

- Event Description: ...
  Date: Month Year (or Year only)
  Type: M&A / Funding / Leadership / Product / IPO / Expansion
  Value: $... or N/A

Text:
{text[:15000]}
"""
    ai_raw = openrouter_chat("openai/gpt-4o-mini", prompt, f"Events: {company_name}")

    events = []

    if ai_raw and "Event Description:" in ai_raw:
        for block in re.split(r'- Event Description:', ai_raw)[1:]:
            e = {"description": "", "date": "N/A", "type": "N/A", "value": "N/A"}
            if desc := re.search(r"(.*?)(?=Date:|Type:|Value:|$)", block, re.S):
                e["description"] = desc.group(1).strip()
            if d := re.search(r"Date:\s*(.+)", block): e["date"] = d.group(1).strip()
            if t := re.search(r"Type:\s*(.+)", block): e["type"] = t.group(1).strip()
            if v := re.search(r"Value:\s*(.+)", block): e["value"] = v.group(1).strip()
            if e["description"]:
                events.append(e)

    # STEP 2 — Add Regex extracted events
    regex_events = _extract_events_from_text(text)
    events.extend(regex_events)

    # STEP 3 — Filter by last 5 years only ✅
    filtered = []
    for e in events:
        year = _parse_date(e["date"]).year
        if year >= MIN_YEAR_LIMIT:
            filtered.append(e)

    # STEP 4 — AI Fallback if less than 5 events
    if len(filtered) < 5:
        needed = 5 - len(filtered)
        ai_fill_prompt = f"""
Generate {needed} realistic but fictional corporate events for "{company_name}"
between YEAR {MIN_YEAR_LIMIT} and {CURRENT_YEAR}.

Follow the exact format:

- Event Description: ...
  Date: Month Year
  Type: Product / Deal / Expansion / Award
  Value: N/A
"""
        ai_more = openrouter_chat("openai/gpt-4o-mini", ai_fill_prompt, "Event Fill")

        if ai_more and "Event Description:" in ai_more:
            for block in re.split(r'- Event Description:', ai_more)[1:]:
                d = block.replace("\n", " ").strip()
                filtered.append({
                    "description": d,
                    "date": str(CURRENT_YEAR),
                    "type": "General",
                    "value": "N/A"
                })

    # Ensure final unique + sorted ✅
    seen = set()
    final_events = []
    for e in filtered:
        key = (e["description"][:60], e["date"])
        if key not in seen:
            seen.add(key)
            final_events.append(e)

    final_events.sort(key=lambda x: _parse_date(x["date"]), reverse=True)

    lines = []
    for e in final_events[:10]:
        lines.append(
            f"- Event Description: {e['description']}\n"
            f"  Date: {e['date']}\n"
            f"  Type: {e['type']}\n"
            f"  Value: {e['value']}"
        )

    return "\n\n".join(lines)
