import os
import sys

# ✅ Add project root to Python path dynamically
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
sys.path.insert(0, PROJECT_ROOT)

from analysis.summary_generator import generate_summary

def test_generate_summary():
    company_name = "Google"

    print(f"\n🔍 Testing summary generation for: {company_name}")

    try:
        summary = generate_summary(company_name)
        if summary and isinstance(summary, str) and len(summary.strip()) > 30:
            print("✅ Summary Generated Successfully!\n")
            print(summary)
        else:
            print("❌ Summary generation failed or returned empty result\n")
            print("Returned:", summary)

    except Exception as e:
        print("❌ Error occurred while testing generate_summary()")
        print("Error:", e)

if __name__ == "__main__":
    test_generate_summary()
