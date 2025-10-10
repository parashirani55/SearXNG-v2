from openai import OpenAI
import os
from dotenv import load_dotenv

# ✅ Load environment variables
load_dotenv()

# ✅ Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_summary(text):
    prompt = f"""
You are an expert company information extractor.

Your job is to **always return a structured Company Details summary** — even if the input text is short, incomplete, or unclear.
Do not explain what you are doing or ask for more information.
If a value cannot be confidently found, leave that field blank (but still include it).

---

### 🧾 Extract the Following Fields:
1. **Year Founded** — The official or approximate founding/incorporation year.  
2. **Website** — The company’s main website (e.g., https://example.com).  
3. **LinkedIn** — The LinkedIn company page (e.g., https://linkedin.com/company/example).  
4. **Headquarters (HQ)** — The primary city and country/state of the company’s headquarters.  
5. **CEO / Key Executive** — The current CEO, Managing Director, or Founder.

---

### 🧩 Output Rules:
- Always use the **exact markdown format** shown below.  
- Do **not** add commentary, instructions, disclaimers, or “please provide more text.”  
- If information is missing, still keep the field but leave it empty.  
- Focus on factual extraction from the given content only.  
- Never say “I need more information” — just output what you can.

---

### ✅ Output Format Example
**Company Details**
- Year Founded: 1907  
- Website: https://www.shell.com  
- LinkedIn: https://linkedin.com/company/shell  
- Headquarters: The Hague, Netherlands  
- CEO: Wael Sawan  

---

Now extract and return **only** in this exact format using the content below:

{text[:8000]}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content
