from openai import OpenAI
import os
from dotenv import load_dotenv  # ✅ import this

# Load .env file
load_dotenv()

# Initialize OpenAI client with your API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def generate_summary(text):
    prompt = f"""You are an expert financial and market research analyst.
Analyze the following web content and produce a clear, data-rich Valuation Summary Report.

Format your answer as:
- **Company:** [Name and website]
- **Overview:** [Short intro, focus area, business type]
- **Ownership/Funding:** [Investors, PE/VC details, founding year]
- **Products/Services:** [Main offerings]
- **Clients/Market:** [Client types, markets served]
- **Key Metrics:** [Revenue, growth %, margins, multiples if found]
- **Insights:** [Strategic notes, differentiators]

Content:
{text[:8000]}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content
