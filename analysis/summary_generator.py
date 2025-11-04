from .api_client import openrouter_chat
from .wiki_utils import get_wikipedia_summary

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
