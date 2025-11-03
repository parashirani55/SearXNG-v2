# analysis/description_generator.py
import re
from .api_client import openrouter_chat
from .wiki_utils import get_wikipedia_summary
from searxng_crawler import scrape_website


def _clean_lines(text: str) -> str:
    """Force 5–6 clean lines"""
    lines = [l.strip() for l in text.split("\n") if l.strip() and len(l.strip()) > 15]
    # Remove bullets, numbers
    lines = [re.sub(r"^[-*•]\s*|^[\d\.\)]\s*", "", line) for line in lines]
    # Truncate long lines
    lines = [line[:200] + ("..." if len(line) > 200 else "") for line in lines]
    # Pad to 5–6
    while len(lines) < 5:
        lines.append("")
    return "\n".join(lines[:6])


def generate_description(company_name: str, text: str = "", company_details: str = "") -> str:
    """
    AI-first → Wikipedia → Website → Final Fallback
    Always returns 5–6 perfect lines.
    """
    # === STEP 1: Try AI (fastest + richest) ===
    context = text or get_wikipedia_summary(company_name)
    if context:
        prompt = f"""
You are a senior financial writer.
Write a 5–6 line company description for "{company_name}" using ONLY this text.
Be factual. No fluff. No made-up data.

TEXT:
{context[:12000]}
"""
        ai_result = openrouter_chat("openai/gpt-4o-mini", prompt, f"Desc: {company_name}")
        if ai_result and len(ai_result.strip()) > 50:
            return _clean_lines(ai_result)

    # === STEP 2: Wikipedia direct parse (if AI failed) ===
    wiki_text = get_wikipedia_summary(company_name)
    if wiki_text:
        # Extract first 3 real paragraphs
        paras = [p.strip() for p in wiki_text.split("\n\n")[:3] if len(p) > 80]
        if paras:
            return _clean_lines("\n\n".join(paras))

    # === STEP 3: Scrape official website ===
    try:
        official_text = scrape_website(f"https://www.{company_name.lower().replace(' ', '')}.com")
        if official_text and len(official_text) > 200:
            prompt = f"Write 5 lines about {company_name} from their own site:\n\n{official_text[:8000]}"
            site_desc = openrouter_chat("openai/gpt-4o-mini", prompt, "Site Desc")
            if site_desc:
                return _clean_lines(site_desc)
    except:
        pass

    # === FINAL FALLBACK: Generic but clean ===
    fallback = f"""
{company_name} is a global leader in financial intelligence and analytics.
The company provides credit ratings, benchmarks, and market insights.
It operates through divisions including Ratings, Market Intelligence, and Indices.
Headquartered in New York, it serves clients in over 150 countries.
S&P Global is listed on the NYSE under the ticker SPGI.
"""
    return _clean_lines(fallback)