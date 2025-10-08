import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Valuation Reports ---
def store_report(company, summary):
    supabase.table("valuation_reports").insert({
        "company": company,
        "summary": summary
    }).execute()

def get_reports():
    response = supabase.table("valuation_reports").select("*").order("id", desc=True).execute()
    return response.data

# --- Search History ---
def store_search(query, results, summary):
    """Save raw search query, results text, and AI summary."""
    supabase.table("search_history").insert({
        "query": query,
        "results": results,
        "summary": summary
    }).execute()

def get_search_history():
    """Retrieve previous search history."""
    response = supabase.table("search_history").select("*").order("id", desc=True).execute()
    return response.data
