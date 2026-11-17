"""Domain models for extracted invoices and their review workflow."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str = Field(description="Item or service description as written on the invoice")
    quantity: Decimal = Field(description="Quantity billed")
    unit_price: Decimal = Field(description="Price per unit, excluding VAT")
    line_total: Decimal = Field(description="Line amount excluding VAT")


class InvoiceData(BaseModel):
    """Structured content of a supplier invoice, as extracted by the model."""

    supplier_name: str = Field(description="Legal name of the company issuing the invoice")
    supplier_vat_id: str | None = Field(None, description="Supplier VAT number, if present")
    invoice_number: str = Field(description="Invoice number exactly as printed")
    issue_date: date = Field(description="Invoice date (ISO 8601)")
    due_date: date | None = Field(None, description="Payment due date, if present (ISO 8601)")
    currency: str = Field(description="ISO 4217 currency code, e.g. EUR")
    line_items: list[LineItem] = Field(default_factory=list)
    net_amount: Decimal = Field(description="Total excluding VAT")
    vat_amount: Decimal = Field(description="Total VAT")
    total_amount: Decimal = Field(description="Amount due including VAT")


class Status(str, Enum):
    NEEDS_REVIEW = "needs_review"          # automatic checks found issues
    READY = "ready_for_approval"           # checks passed, a human still approves
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "extraction_failed"


class Invoice(BaseModel):
    id: int
    filename: str
    status: Status
    data: InvoiceData | None = None
    issues: list[str] = Field(default_factory=list)
    created_at: datetime
    reviewed_by: str | None = None
    review_note: str | None = None


class ReviewDecision(BaseModel):
    reviewer: str = Field(min_length=1)
    note: str | None = None
