import os
import re
import requests
from typing import List, Dict, Any
from datetime import datetime
from typing import List, Dict, Any
import requests
from datetime import datetime

OPENROUTER_API_KEY = os.getenv("OPEN_ROUTER_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Best → Backup → Backup-2
AI_MODELS = [
    "openai/gpt-4.1-mini",
    "deepseek/deepseek-chat",
    "anthropic/claude-3-haiku"
]


def _extract_field(block: str, label: str) -> str:
    """Extract structured fields from AI formatted block"""
    pattern = rf"{label}:\s*(.*)"
    match = re.search(pattern, block, flags=re.IGNORECASE)
    return match.group(1).strip() if match else "Unknown"


def _parse_ai_response(text: str) -> List[Dict[str, Any]]:
    """Convert AI message response → Event List"""
    events = []
    chunks = re.split(r"- Event:", text, flags=re.IGNORECASE)[1:]

    for ch in chunks:
        evt = {
            "description": _extract_field(ch, "Description"),
            "date": _extract_field(ch, "Date"),
            "type": _extract_field(ch, "Type"),
            "other_party": _extract_field(ch, "Other Counterparty"),
            "counterparty_status": _extract_field(ch, "Counterparty Status"),
            "investment": _extract_field(ch, "Investment"),
            "enterprise_value": _extract_field(ch, "Enterprise Value"),
            "advisors": _extract_field(ch, "Advisors"),
            "source": "AI"
        }

        if len(evt["description"]) > 3:
            events.append(evt)

    return events


def _build_ai_prompt(company: str, raw_events: List[Dict]) -> List[Dict]:
    """Format data for AI refinement"""
    blocks = ""
    for e in raw_events[:10]:
        blocks += (
            f"- Event:\n"
            f"  Description: {e.get('description', 'Unknown')}\n"
            f"  Date: {e.get('date', 'Unknown')}\n"
            f"  Type: {e.get('type', 'Unknown')}\n"
            f"  Source: {e.get('source', 'Unknown')}\n\n"
        )
    return blocks


def _is_within_last_5_years(date_str: str) -> bool:
    """Filter stale/old dates"""
    try:
        event_year = int(date_str[:4])
        return event_year >= datetime.now().year - 5
    except:
        return True  # If AI gave non-year text → keep for now




def refine_events_with_ai(
    company: str,
    raw_events: List[Dict[str, Any]],
    text: str = None  # Optional additional context
) -> List[Dict]:
    """
    Refine corporate events using AI.
    Optionally, `text` can provide additional context for better enrichment.
    
    Args:
        company (str): Company name.
        raw_events (List[Dict]): Raw corporate events.
        text (str, optional): Additional context (e.g., company summary).
    
    Returns:
        List[Dict]: Refined and enriched events.
    """

    if not raw_events:
        return []

    if not OPENROUTER_API_KEY:
        print("❌ No OPENROUTER_API_KEY found in environment.")
        return raw_events

    # Build AI prompt including optional text context
    user_prompt = _build_ai_prompt(company, raw_events)
    if text:
        user_prompt += f"\n\nAdditional context:\n{text}"

    payload_base = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert in Corporate Intelligence.\n"
                    "Improve event completeness: add missing financial values,\n"
                    "identify deal type, and validate date range (last 5 years).\n"
                    "Return ONLY structured formatted output."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Corporate events for: {company}\n"
                    "Output format:\n"
                    "- Event:\n"
                    "  Description:\n"
                    "  Date:\n"
                    "  Type:\n"
                    "  Other Counterparty:\n"
                    "  Counterparty Status:\n"
                    "  Investment:\n"
                    "  Enterprise Value:\n"
                    "  Advisors:\n\n"
                    f"Raw Data:\n{user_prompt}"
                ),
            },
        ],
        "temperature": 0.25,
        "max_tokens": 1100,
    }

    for model in AI_MODELS:
        try:
            print(f"🤖 Using AI Model: {model}")
            payload = {**payload_base, "model": model}

            resp = requests.post(
                OPENROUTER_URL,
                json=payload,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )

            result = resp.json()
            ai_content = result["choices"][0]["message"]["content"]
            ai_events = _parse_ai_response(ai_content)

            refined = []
            ai_idx = 0

            for evt in raw_events:
                enriched = ai_events[ai_idx] if ai_idx < len(ai_events) else evt
                ai_idx += 1

                # Skip events older than 5 years
                if not _is_within_last_5_years(enriched.get("date", "")):
                    continue

                refined.append({**evt, **enriched})

            return refined

        except Exception as e:
            print(f"⚠️ AI model {model} failed: {e}")

    print("🚨 All AI models failed — returning raw events")
    return raw_events
