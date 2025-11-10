from pathlib import Path

def build_verified_prompt(company: str, start_year: int, end_year: int, extra_context: str = None) -> str:
    """
    Build a dynamic verified-event prompt by replacing placeholders
    with company name, start year, and end year.
    """
    prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "verified_event_prompt.txt"
    with open(prompt_path, "r", encoding="utf-8") as f:
        base_prompt = f.read()

    prompt = (
        base_prompt
        .replace("{{COMPANY_NAME}}", company)
        .replace("{{START_YEAR}}", str(start_year))
        .replace("{{END_YEAR}}", str(end_year))
    )

    if extra_context:
        prompt += f"\n\n### Additional Context:\n{extra_context[:3000]}"
    return prompt
