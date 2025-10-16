import os
from supabase import create_client, Client
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# --- Initialize Supabase client ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------
# Helper: Clean text before storing
# -----------------------------
def clean_text(text):
    """Sanitize text to avoid None, null bytes, or unwanted characters."""
    if not text:
        return ""
    if not isinstance(text, str):
        text = str(text)
    return text.strip().replace("\0", "")[:10000]  # Limit length to avoid DB issues

# -----------------------------
# Valuation Reports
# -----------------------------
def store_report(company, summary, description):
    """Store valuation summary and description for a company."""
    data = {
        "company": clean_text(company),
        "summary": clean_text(summary),
        "description": clean_text(description)
    }
    try:
        response = supabase.table("valuation_reports").insert(data).execute()
        if response.data:
            print(f"✅ Report stored successfully for: {data['company']}")
            return response.data
        else:
            print(f"⚠️ Report not stored: {data}")
            return False
    except Exception as e:
        print(f"⚠️ Exception while storing report: {e}")
        return False

def get_reports():
    """Retrieve previous valuation reports."""
    try:
        response = supabase.table("valuation_reports").select("*").order("created_at", desc=True).execute()
        if response.data:
            return response.data
        else:
            return []
    except Exception as e:
        print(f"⚠️ Exception while fetching reports: {e}")
        return []

# -----------------------------
# Search History
# -----------------------------
def store_search(query, results, summary, description, corporate_events=""):
    """Store a search history entry including corporate events."""
    data = {
        "query": clean_text(query),
        "results": clean_text(results),
        "summary": clean_text(summary),
        "description": clean_text(description),
        "corporate_events": clean_text(corporate_events) or "No events found."  # Ensure not null
    }
    try:
        response = supabase.table("search_history").insert(data).execute()
        if response.data:
            print(f"✅ Search history stored for query: {data['query']}")
            return response.data
        else:
            print(f"⚠️ Search history not stored: {data}")
            return False
    except Exception as e:
        print(f"⚠️ Exception while storing search history: {e}")
        return False

def get_search_history():
    """Retrieve previous search history, filtering duplicates by query."""
    try:
        response = supabase.table("search_history").select("*").order("created_at", desc=True).execute()
        if response.data:
            # Deduplicate by query
            seen = set()
            unique = []
            for item in response.data:
                if item['query'] not in seen:
                    seen.add(item['query'])
                    # Ensure corporate_events has default if missing
                    if not item.get('corporate_events'):
                        item['corporate_events'] = "No events found."
                    unique.append(item)
            return unique
        else:
            return []
    except Exception as e:
        print(f"⚠️ Exception while fetching search history: {e}")
        return []