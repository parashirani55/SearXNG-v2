from fpdf import FPDF
import io
import os

# Load font relative to current file
FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")

# 🧹 Emoji & symbol cleaner (prevents missing glyph errors)
def clean_text(text: str) -> str:
    if not text:
        return ""
    replacements = {
        "✅": "[OK]",
        "❌": "[X]",
        "⚠️": "[Warning]",
        "🚀": "[Launch]",
        "💡": "[Idea]",
        "📈": "[Up]",
        "📉": "[Down]",
        "🏢": "[Company]",
        "👤": "[Person]",
        "📊": "[Chart]",
        "🌍": "[World]",
        "🔍": "[Search]",
        "🔗": "[Link]",
        "⭐": "[Star]",
        "🔥": "[Hot]",
        "📄": "[Doc]",
        "🧠": "[Brain]",
        "🪙": "[Coin]",
    }
    for emoji, replacement in replacements.items():
        text = text.replace(emoji, replacement)
    return text

def create_pdf_from_text(title: str, summary: str, description: str = "", corporate_events: str = "", top_management: str = "") -> io.BytesIO:
    """
    Create a PDF including company description, summary, corporate events, and top management.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Add Unicode font
    pdf.add_font("DejaVu", "", FONT_PATH, uni=True)
    pdf.add_font("DejaVu", "B", FONT_PATH, uni=True)

    # 🩶 Title
    pdf.set_font("DejaVu", "B", 18)
    pdf.multi_cell(0, 10, clean_text(title), align="C")
    pdf.ln(8)

    # 🩵 Description
    if description:
        pdf.set_font("DejaVu", "", 12)
        pdf.multi_cell(0, 8, clean_text(description))
        pdf.ln(5)

    # 🟦 Summary
    if summary:
        pdf.set_font("DejaVu", "", 12)
        pdf.multi_cell(0, 8, clean_text(summary))
        pdf.ln(5)

    # 📅 Corporate Events
    if corporate_events:
        pdf.set_font("DejaVu", "B", 14)
        pdf.multi_cell(0, 10, "Corporate Events:")
        pdf.set_font("DejaVu", "", 12)
        pdf.multi_cell(0, 8, clean_text(corporate_events))
        pdf.ln(5)

    # 👥 Top Management
    if top_management:
        pdf.set_font("DejaVu", "B", 14)
        pdf.multi_cell(0, 10, "Top Management:")
        pdf.set_font("DejaVu", "", 12)
        pdf.multi_cell(0, 8, clean_text(top_management))

    # ✅ Return as BytesIO safely
    pdf_bytes = pdf.output(dest="S")
    if isinstance(pdf_bytes, bytearray):
        pdf_bytes = bytes(pdf_bytes)

    return io.BytesIO(pdf_bytes)
