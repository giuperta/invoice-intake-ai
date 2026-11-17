from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

import pytest

from invoice_intake.models import InvoiceData, LineItem


@pytest.fixture
def clean_invoice() -> InvoiceData:
    return InvoiceData(
        supplier_name="Helix Media S.r.l.",
        supplier_vat_id="IT09182736451",
        invoice_number="HM-0098",
        issue_date=date(2026, 11, 2),
        due_date=date(2026, 12, 2),
        currency="EUR",
        line_items=[
            LineItem(description="Product video", quantity=D("1"), unit_price=D("2400"), line_total=D("2400")),
            LineItem(description="Social cuts", quantity=D("4"), unit_price=D("150"), line_total=D("600")),
        ],
        net_amount=D("3000.00"),
        vat_amount=D("660.00"),
        total_amount=D("3660.00"),
    )


class FakeMessages:
    """Mimics anthropic.Anthropic().messages and records the request."""

    def __init__(self, blocks):
        self.blocks = blocks
        self.last_request = None

    def create(self, **kwargs):
        self.last_request = kwargs
        return SimpleNamespace(content=self.blocks)


def fake_client(payload=None, blocks=None):
    if blocks is None:
        blocks = [SimpleNamespace(type="tool_use", name="record_invoice", input=payload)]
    return SimpleNamespace(messages=FakeMessages(blocks))


class StaticExtractor:
    def __init__(self, data):
        self.data = data

    def extract(self, document_text):
        return self.data
