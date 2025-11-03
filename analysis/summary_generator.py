# analysis/summary_generator.py
from .api_client import openrouter_chat
from .wiki_utils import get_wikipedia_summary

def generate_summary(company_name: str, text: str = "") -> str:
    if not text:
        text = get_wikipedia_summary(company_name)
    if not text:
        return "No data found."

    prompt = f"""
Extract exact company details for "{company_name}" in this markdown format:

**Company Details**
- Year Founded: 
- Website: 
- LinkedIn: 
- Headquarters: 
- CEO: 

Text:
{text[:8000]}
"""
    result = openrouter_chat("openai/gpt-4o-mini", prompt, "Summary Extractor")
    return result.strip() if result else "No summary generated."