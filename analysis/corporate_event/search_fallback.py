# ============================================================
# 🔹 search_fallback.py
# Used when searxng_analyzer isn't loaded yet
# ============================================================

def search_company_news(company: str, months: int = 12):
    return f"[Fallback] No live news data for '{company}' (search skipped)."
