import io

import pytest
from reportlab.pdfgen import canvas

from invoice_intake.text_extraction import UnsupportedDocument, extract_text


def make_pdf(lines):
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 18
    c.save()
    return buf.getvalue()


def test_pdf_text_is_extracted():
    pdf = make_pdf(["INVOICE No. HM-0098", "TOTAL DUE 3660.00"])
    text = extract_text("invoice.PDF", pdf)
    assert "HM-0098" in text and "3660.00" in text


def test_plain_text():
    assert extract_text("a.txt", b"  Invoice 1  ") == "Invoice 1"


def test_unsupported_format():
    with pytest.raises(UnsupportedDocument):
        extract_text("photo.jpg", b"\xff\xd8")


def test_pdf_without_text_layer():
    with pytest.raises(UnsupportedDocument, match="OCR"):
        extract_text("scan.pdf", make_pdf([]))
