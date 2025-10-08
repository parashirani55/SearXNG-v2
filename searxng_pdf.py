from fpdf import FPDF
import io
import os

# Load font relative to current file
FONT_PATH = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")

def create_pdf_from_text(title, summary):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Add Unicode font
    pdf.add_font("DejaVu", "", FONT_PATH, uni=True)
    pdf.add_font("DejaVu", "B", FONT_PATH, uni=True)

    # Title
    pdf.set_font("DejaVu", "B", 18)
    pdf.multi_cell(0, 10, title, align="C")
    pdf.ln(8)

    # Summary
    pdf.set_font("DejaVu", "", 12)
    pdf.multi_cell(0, 8, summary)

    # Return as BytesIO directly, no encode needed
    pdf_bytes = pdf.output(dest="S")  # returns bytearray
    return io.BytesIO(pdf_bytes)
