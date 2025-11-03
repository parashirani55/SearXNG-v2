# analysis/management_analyzer.py
from .api_client import openrouter_chat
from .wiki_utils import get_wikipedia_summary

def get_top_management(company_name: str, text: str = "") -> tuple:
    if not text:
        text = get_wikipedia_summary(company_name)

    prompt = f"""
Extract current and past leadership for {company_name}.
Return JSON:
{{"current": [{{"name": "", "position": ""}}], "past": [{{"name": "", "position": ""}}]}}

Text:
{text[:10000]}
"""
    raw = openrouter_chat("openai/gpt-4o-mini", prompt, "Management Extractor")
    try:
        data = eval(raw) if raw.startswith("{") else {}
        current = data.get("current", [])
        past = data.get("past", [])
        for p in current + past:
            p["status"] = "Current" if p in current else "Past"
        all_mgmt = current + past
        text_out = "\n".join([f"{p['name']} — {p['position']} ({p['status']})" for p in all_mgmt])
        return all_mgmt, text_out
    except:
        return [], "No management data."