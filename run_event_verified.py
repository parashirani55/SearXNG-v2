# ============================================================
# 🔹 File: run_event_verified.py
# Purpose: Quick CLI runner for event_verified.py testing
# ============================================================

import logging
from analysis.corporate_event.event_verified import generate_verified_corporate_events
from datetime import datetime

# ------------------------------------------------------------
# 🔧 Config
# ------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Change company name here to test
COMPANY = "S&P Global"

# How many past years to include
YEARS = 5

# ------------------------------------------------------------
# 🚀 Run Verification
# ------------------------------------------------------------
if __name__ == "__main__":
    print(f"\n=== Corporate Event System: Using VERIFIED pipeline for: {COMPANY} ===")
    start_time = datetime.now()

    try:
        result = generate_verified_corporate_events(COMPANY, years=YEARS)
        print("\n✅ Data collection complete!\n")

        print(f"Company Profile: {result['company']['name']}")
        print(f"Verified Events: {result['verified_count']}")
        print(f"Last Updated: {result['last_updated']}\n")

        print("Top 5 events:")
        for e in result['events'][:5]:
            print(f" - {e['date']}: {e['title']} ({e['event_type']}) — {e['amount']}")

        print("\n🧾 Markdown Table Preview:")
        print(result['structured_summary']['markdown_table'][:1500])  # short preview

        print(f"\n✅ Output saved to: /output/{COMPANY.replace(' ', '_')}_events.csv")
        print(f"✅ Output saved to: /output/{COMPANY.replace(' ', '_')}_events.json")

    except Exception as e:
        print(f"\n❌ Error during execution: {e}")

    end_time = datetime.now()
    print(f"\nExecution Time: {end_time - start_time}\n")
