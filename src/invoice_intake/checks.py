"""Deterministic business checks on extracted data.

LLM output is never trusted blindly: arithmetic and consistency are verified
in code, and anything suspicious is routed to a human reviewer.
"""

from __future__ import annotations

from decimal import Decimal

from .models import InvoiceData

TOLERANCE = Decimal("0.02")
KNOWN_VAT_RATES = {Decimal(r) for r in ("0", "4", "5", "10", "19", "20", "21", "22", "23")}


def _close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCE


def check_invoice(data: InvoiceData, *, seen_numbers: set[tuple[str, str]] | None = None) -> list[str]:
    issues: list[str] = []

    for i, item in enumerate(data.line_items, start=1):
        if not _close(item.quantity * item.unit_price, item.line_total):
            issues.append(
                f"Line {i}: quantity × unit price = {item.quantity * item.unit_price:.2f}, "
                f"but line total is {item.line_total:.2f}."
            )

    if data.line_items:
        lines_sum = sum((i.line_total for i in data.line_items), Decimal("0"))
        if not _close(lines_sum, data.net_amount):
            issues.append(f"Sum of lines ({lines_sum:.2f}) differs from net amount ({data.net_amount:.2f}).")
    else:
        issues.append("No line items found.")

    if not _close(data.net_amount + data.vat_amount, data.total_amount):
        issues.append(
            f"Net + VAT = {data.net_amount + data.vat_amount:.2f}, but total is {data.total_amount:.2f}."
        )

    if data.net_amount > 0:
        rate = (data.vat_amount / data.net_amount * 100).quantize(Decimal("1"))
        if rate not in KNOWN_VAT_RATES:
            issues.append(f"Unusual VAT rate (~{rate}%).")

    if data.due_date and data.due_date < data.issue_date:
        issues.append("Due date is before the issue date.")

    if len(data.currency) != 3 or not data.currency.isalpha():
        issues.append(f"Invalid currency code '{data.currency}'.")

    if not data.supplier_vat_id:
        issues.append("Supplier VAT number missing.")

    if seen_numbers and (data.supplier_name.lower(), data.invoice_number) in seen_numbers:
        issues.append("Possible duplicate: same supplier and invoice number already registered.")

    return issues
