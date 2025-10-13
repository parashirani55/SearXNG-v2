import os
from supabase import create_client, Client
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Valuation Reports ---
def store_report(company, summary, description):
    """Store valuation summary and description for a company."""
    supabase.table("valuation_reports").insert({
        "company": company,
        "summary": summary,
        "description": description
    }).execute()

def get_reports():
    """Retrieve previous valuation reports."""
    response = supabase.table("valuation_reports").select("*").order("id", desc=True).execute()
    return response.data or []

# --- Search History ---
def store_search(query, results, summary, description):
    """Save raw search query, scraped text, AI summary, and description."""
    supabase.table("search_history").insert({
        "query": query,
        "results": results,
        "summary": summary,
        "description": description
    }).execute()

def get_search_history():
    """Retrieve previous search history."""
    response = supabase.table("search_history").select("*").order("id", desc=True).execute()
    return response.data or []
