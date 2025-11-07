# event_analyzer.py
# Main Intelligence Event Fetcher — Global + Hybrid + AI-Structured Output

import os
import json
import csv
from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown
from pathlib import Path

# Local
from analysis.corporate_event.event_scraper import scrape_all_sources
from analysis.corporate_event.event_finnhub import fetch_finnhub_events
from analysis.corporate_event.event_google_news import fetch_google_news
from analysis.corporate_event.event_ai import refine_events_with_ai
from analysis.corporate_event.event_utils import merge_and_clean_events
from analysis.corporate_event.event_verified import generate_verified_corporate_events

load_dotenv(dotenv_path=Path(__file__).resolve().parents[1] / ".env")
console = Console()
LOG_PREFIX = "[bold blue]Corporate Event System:[/bold blue]"
USE_VERIFIED_PIPELINE = os.getenv("USE_VERIFIED_PIPELINE", "true").lower() == "true"

def log(msg): console.print(f"{LOG_PREFIX} {msg}")



# ============================================================
# Sorting & Splitting
# ============================================================
def sort_events(events):
    def score(e):
        s = 0
        if e.get("date") not in ["Unknown", "N/A"]: s += 3
        if e.get("event_type") not in ["Unknown", None, ""]: s += 2
        if e.get("counterparty") not in ["Unknown", ""]: s += 1
        if e.get("amount") not in ["–", "Unknown", "Not available"]: s += 1
        return s
    return sorted(events, key=score, reverse=True)

def split_complete_incomplete(events):
    complete = [e for e in events if e.get("date") not in ["Unknown","N/A"] and e.get("event_type") not in ["Unknown",None,""]]
    incomplete = [e for e in events if e not in complete]
    return complete, incomplete

# ============================================================
# Save & Print
# ============================================================
def save_results(company: str, events: list):
    base = company.replace(" ", "_")
    os.makedirs("output", exist_ok=True)
    json_path = f"output/{base}_events.json"
    csv_path = f"output/{base}_events.csv"

    with open(json_path, "w") as f:
        json.dump(events, f, indent=2)
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date","title","event_type","counterparty","amount","source","url"])
        writer.writeheader()
        for e in events:
            writer.writerow({
                "date": e.get("date"),
                "title": e.get("title") or e.get("description"),
                "event_type": e.get("event_type") or e.get("type"),
                "counterparty": e.get("counterparty"),
                "amount": e.get("amount"),
                "source": e.get("source"),
                "url": e.get("url") or e.get("link"),
            })
    console.print(f"Saved JSON: {json_path}")
    console.print(f"Saved CSV: {csv_path}")

def print_event_table(title: str, events: list):
    table = Table(title=title)
    for col in ["Date","Title","Type","Counterparty","Amount","Source"]:
        table.add_column(col, style="cyan" if col=="Date" else "white")
    for e in events:
        table.add_row(
            e.get("date","Unknown"),
            (e.get("title") or e.get("description") or "No Title")[:100],
            e.get("event_type") or e.get("type","Unknown"),
            e.get("counterparty","Unknown"),
            e.get("amount","–"),
            e.get("source","Unknown"),
        )
    console.print(table)

def show_table(company_profile: dict, events: list, structured_summary: dict = None):
    console.print("\n[bold green]Company Profile[/bold green]")
    for k, v in company_profile.items():
        console.print(f"[bold]{k}:[/bold] {v}")

    console.print("\n[bold yellow]Corporate Events[/bold yellow]")
    complete, incomplete = split_complete_incomplete(sort_events(events))
    if complete: print_event_table("Fully-Structured Events", complete)
    if incomplete: print_event_table("Incomplete Metadata", incomplete)

    # Markdown Table (Chat Style)
    if structured_summary and structured_summary.get("markdown_table"):
        console.print("\n[bold cyan]Markdown Table (Copy-Paste Ready)[/bold cyan]")
        console.print(Markdown(structured_summary["markdown_table"]))

        if structured_summary.get("key_insights"):
            console.print("\n[bold magenta]Key Insights[/bold magenta]")
            for i in structured_summary["key_insights"]:
                console.print(f"• {i}")

        if structured_summary.get("total_value_estimate"):
            console.print(f"\n[bold yellow]Total Value Estimate:[/bold yellow] {structured_summary['total_value_estimate']}")

# ============================================================
# Legacy Pipeline
# ============================================================
def _legacy_generate_corporate_events(company: str, years: int = 5, text: str = None):
    log(f"[legacy] Starting for: [yellow]{company}[/yellow]")
    events = []
    profile = {"name": company}

    try: events.extend(scrape_all_sources(company) or []); log("Scraped")
    except Exception as e: log(f"Scrape failed: {e}")

    try: events.extend(fetch_finnhub_events(company, years) or []); log("Finnhub")
    except Exception as e: log(f"Finnhub failed: {e}")

    try: events.extend(fetch_google_news(company) or []); log("Google News")
    except Exception as e: log(f"Google News failed: {e}")

    refined = refine_events_with_ai(company, events, text=text)
    final = sort_events(merge_and_clean_events(refined))
    show_table(profile, final)
    save_results(company, final)
    return {"company": profile, "events": final, "last_updated": datetime.utcnow().isoformat()}

# ============================================================
# Main Entry
# ============================================================
def generate_corporate_events(company: str, years: int = 5, text: str = None) -> dict:
    if USE_VERIFIED_PIPELINE:
        log(f"Using VERIFIED pipeline for: [yellow]{company}[/yellow]")
        try:
            data = generate_verified_corporate_events(company, years=years, text=text)
            profile = data["company"]
            events = data["events"]
            structured = data.get("structured_summary")

            show_table(profile, events, structured)
            save_results(company, events)

            log(f"Verified Events: [green]{len(events)}[/green]")
            return {
                "company": profile,
                "events": events,
                "last_updated": data["last_updated"],
                "structured_summary": structured
            }
        except Exception as e:
            log(f"Verified failed: {e} → falling back")
    return _legacy_generate_corporate_events(company, years=years, text=text)

if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else input("Enter company name: ")
    generate_corporate_events(name)

