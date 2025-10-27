import os
import json
from supabase import create_client, Client
from dotenv import load_dotenv

# ============================================================
# 🔹 Environment Setup and Supabase Initialization
# ============================================================
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ============================================================
# 🔹 Text Sanitization Helper
# ============================================================
def clean_text(text):
    """Ensure all stored data is safe and in string/JSON form."""
    if text is None:
        return ""
    if isinstance(text, (dict, list)):
        try:
            return json.dumps(text)
        except Exception:
            return str(text)
    if not isinstance(text, str):
        text = str(text)
    return text.strip().replace("\0", "")


# ============================================================
# 🔹 Valuation Reports Management
# ============================================================
def store_report(company, summary, description, corporate_events="", top_management=""):
    """
    Stores a valuation report for a company.
    Subsidiaries are stored separately in company_subsidiaries.
    """
    data = {
        "company": clean_text(company),
        "summary": clean_text(summary),
        "description": clean_text(description),
        "corporate_events": clean_text(corporate_events),
        "top_management": clean_text(top_management),
    }
    try:
        response = supabase.table("valuation_reports").insert(data).execute()
        if response.data:
            print(f"✅ Report stored successfully for: {company}")
            return response.data
        else:
            print(f"⚠️ Report not stored for: {company}")
            return False
    except Exception as e:
        print(f"⚠️ Exception while storing report for {company}: {e}")
        return False


def get_reports():
    """Retrieve all valuation reports from the database."""
    try:
        response = (
            supabase.table("valuation_reports")
            .select("*")
            .order("id", desc=True)
            .execute()
        )
        return response.data if response.data else []
    except Exception as e:
        print(f"⚠️ Exception while fetching reports: {e}")
        return []


# ============================================================
# 🔹 Search History Management
# ============================================================
def store_search(query, results, summary, description, corporate_events="", top_management=""):
    """
    Stores a search history entry.
    Subsidiaries are not stored here; they go in company_subsidiaries.
    """
    data = {
        "query": clean_text(query),
        "results": clean_text(results),
        "summary": clean_text(summary),
        "description": clean_text(description),
        "corporate_events": clean_text(corporate_events),
        "top_management": clean_text(top_management),
    }
    try:
        response = supabase.table("search_history").insert(data).execute()
        if response.data:
            print(f"✅ Search history stored for query: {query}")
            return response.data
        else:
            print(f"⚠️ Search history not stored for: {query}")
            return False
    except Exception as e:
        print(f"⚠️ Exception while storing search history for {query}: {e}")
        return False


def get_search_history():
    """Retrieve all previous search history entries."""
    try:
        response = (
            supabase.table("search_history")
            .select("*")
            .order("id", desc=True)
            .execute()
        )
        return response.data if response.data else []
    except Exception as e:
        print(f"⚠️ Exception while fetching search history: {e}")
        return []


# ============================================================
# 🔹 Company Subsidiaries Management
# ============================================================
def store_subsidiaries(company, subsidiaries):
    """
    Store multiple subsidiary records for a company in company_subsidiaries.
    Expects a list of dictionaries.
    """
    if not subsidiaries or not isinstance(subsidiaries, list):
        return

    data = []
    for sub in subsidiaries:
        data.append({
            "company": clean_text(company),
            "name": clean_text(sub.get("name", "")),
            "logo": clean_text(sub.get("logo", "")),
            "description": clean_text(sub.get("description", "")),
            "sector": clean_text(sub.get("sector", "")),
            "linkedin_members": sub.get("linkedin_members") or 0,
            "country": clean_text(sub.get("country", "")),
        })

    try:
        response = supabase.table("company_subsidiaries").insert(data).execute()
        if response.data:
            print(f"✅ {len(data)} subsidiaries stored for {company}")
            return response.data
    except Exception as e:
        print(f"⚠️ Failed to store subsidiaries for {company}: {e}")
        return False


def get_subsidiaries(company):
    """Retrieve all subsidiaries for a given company."""
    try:
        response = (
            supabase.table("company_subsidiaries")
            .select("*")
            .eq("company", company)
            .execute()
        )
        return response.data if response.data else []
    except Exception as e:
        print(f"⚠️ Error fetching subsidiaries for {company}: {e}")
        return []
