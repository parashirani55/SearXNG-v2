# ============================================================
# 🔹 summary_generator.py
# Purpose: Generate company summaries and descriptions
# Works with OpenRouter + Wikipedia fallback
# ============================================================

from .api_client import openrouter_chat
from .wiki_utils import get_wikipedia_summary


# ============================================================
# 🔹 Generate Summary (Basic Company Info Extraction)
# ============================================================
def generate_summary(company_name: str, text: str = "") -> str:
    # ✅ 1️⃣ First try text from pipeline (best)
    source = "input"
    if not text:
        # ✅ 2️⃣ Fallback to Wikipedia (free)
        text = get_wikipedia_summary(company_name)
        source = "wikipedia" if text else "none"

    # ✅ 3️⃣ Build correct prompt based on what we found
    if text:
        prompt = f"""
Extract company details for "{company_name}" from the following text.

Rules:
- If a field is missing → write "Unknown".
- If you infer from context and not fully sure → write "(estimated)".
- Never leave any field blank.
- Stick to this exact markdown structure:

**Company Details**
- Year Founded:
- Website:
- LinkedIn:
- Headquarters:
- CEO:

Text to analyze:
{text[:8000]}
"""
    else:
        # ✅ 4️⃣ No real data → AI guess fallback (still must fill all fields)
        prompt = f"""
We only know the company name: "{company_name}"

Provide the most likely company details.
- If completely unsure → "Unknown"
- If guessed → mark "(estimated)"
- Never leave any field blank.

Strict format:

**Company Details**
- Year Founded:
- Website:
- LinkedIn:
- Headquarters:
- CEO:
"""

    # ✅ 5️⃣ Try **free model** first
    result = openrouter_chat("openai/gpt-4o-mini", prompt, "Summary Extractor")

    # ✅ 6️⃣ If free model fails → use paid model fallback
    if not result or "Unknown" in result:
        result = openrouter_chat("openai/gpt-4o", prompt, "Summary Extractor Pro")

    return result.strip() if result else "No summary generated."


# ============================================================
# 🔹 Generate Description (Narrative Company Overview)
# ============================================================
def generate_description(company_name: str, text: str = "") -> str:
    """
    Create a readable and factual paragraph describing the company.
    - Uses Wikipedia or fallback text if available.
    - Returns an investor-style narrative suitable for company reports.
    """
    # ✅ Use Wikipedia if no text provided
    if not text:
        text = get_wikipedia_summary(company_name) or ""

    prompt = f"""
You are a senior equity research analyst.

Write a factual, clear, and concise **company description** for "{company_name}".
It should read like the introductory paragraph of an investor report or Wikipedia page.

Include:
- What the company does (products/services)
- Its main industry and regions of operation
- Its scale, significance, or leadership position
- Mention subsidiaries or divisions if applicable

Input context (if any):
{text[:6000]}

Rules:
- Do not make up data without marking "(estimated)".
- Avoid marketing tone or exaggeration.
- Output plain text (1–2 paragraphs, 5–7 sentences).
"""

    # ✅ Try fast model first
    result = openrouter_chat("openai/gpt-4o-mini", prompt, "Company Description Generator")

    # ✅ Fallback to pro model if too generic
    if not result or len(result.split()) < 30:
        result = openrouter_chat("openai/gpt-4o", prompt, "Company Description Generator Pro")

    return result.strip() if result else f"Description unavailable for {company_name}."
