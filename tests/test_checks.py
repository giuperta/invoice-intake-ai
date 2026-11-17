from datetime import date
from decimal import Decimal as D

from invoice_intake.checks import check_invoice


def test_clean_invoice_has_no_issues(clean_invoice):
    assert check_invoice(clean_invoice) == []


def test_wrong_total_is_flagged(clean_invoice):
    bad = clean_invoice.model_copy(update={"total_amount": D("3700.00")})
    issues = check_invoice(bad)
    assert any("Net + VAT" in i for i in issues)


def test_line_arithmetic_is_flagged(clean_invoice):
    item = clean_invoice.line_items[1].model_copy(update={"line_total": D("650")})
    bad = clean_invoice.model_copy(update={"line_items": [clean_invoice.line_items[0], item]})
    issues = check_invoice(bad)
    assert any(i.startswith("Line 2") for i in issues)
    assert any("Sum of lines" in i for i in issues)


def test_rounding_within_tolerance_is_accepted(clean_invoice):
    ok = clean_invoice.model_copy(update={"total_amount": D("3660.01")})
    assert check_invoice(ok) == []


def test_dates_vat_and_currency(clean_invoice):
    bad = clean_invoice.model_copy(update={
        "due_date": date(2026, 10, 1),
        "supplier_vat_id": None,
        "currency": "EURO",
        "vat_amount": D("400.00"),
        "total_amount": D("3400.00"),
    })
    issues = " | ".join(check_invoice(bad))
    assert "Due date is before" in issues
    assert "VAT number missing" in issues
    assert "Invalid currency" in issues
    assert "Unusual VAT rate" in issues


def test_duplicate_detection(clean_invoice):
    seen = {("helix media s.r.l.", "HM-0098")}
    assert any("duplicate" in i for i in check_invoice(clean_invoice, seen_numbers=seen))
