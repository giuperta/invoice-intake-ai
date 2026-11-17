"""Offline demo: runs the dashboard with sample invoices and no API key.

The scripted extractor below stands in for Claude and returns pre-extracted
data for the files in ``samples/``; everything else (checks, workflow,
persistence, API, UI) is the real application code.
"""

from __future__ import annotations

import os
from datetime import date
from decimal import Decimal as D
from pathlib import Path

from .extractor import ExtractionError
from .models import InvoiceData, LineItem
from .repository import InvoiceRepository
from .service import InvoiceService

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


def _inv(supplier, vat_id, number, issued, due, lines, vat_rate, total=None, vat=None):
    items = [LineItem(description=d, quantity=D(q), unit_price=D(p), line_total=D(q) * D(p)) for d, q, p in lines]
    net = sum((i.line_total for i in items), D("0"))
    vat_amount = D(vat) if vat else (net * D(vat_rate) / 100).quantize(D("0.01"))
    return InvoiceData(
        supplier_name=supplier, supplier_vat_id=vat_id, invoice_number=number,
        issue_date=issued, due_date=due, currency="EUR", line_items=items,
        net_amount=net, vat_amount=vat_amount, total_amount=D(total) if total else net + vat_amount,
    )


SCRIPTED: dict[str, InvoiceData] = {
    "nimbus-cloud-2026-0412.txt": _inv(
        "Nimbus Cloud S.r.l.", "IT04829310962", "2026/0412", date(2026, 10, 3), date(2026, 11, 2),
        [("Managed Kubernetes cluster - October", "1", "1450.00"), ("Object storage (TB)", "3.5", "38.00")], 22),
    "alpine-logistics-A-7781.txt": _inv(
        "Alpine Logistics GmbH", "DE298374651", "A-7781", date(2026, 10, 12), date(2026, 11, 11),
        [("Pallet transport Milan-Munich", "6", "185.00"), ("Fuel surcharge", "1", "64.50")], 19,
        total="1455.00"),  # printed total contains an arithmetic error
    "cobalt-systems-INV-2210.txt": _inv(
        "Cobalt Systems S.p.A.", None, "INV-2210", date(2026, 10, 20), date(2026, 10, 15),
        [("Barcode scanners", "12", "179.90")], 22),
    "helix-media-HM-0098.txt": _inv(
        "Helix Media S.r.l.", "IT09182736451", "HM-0098", date(2026, 11, 2), date(2026, 12, 2),
        [("Product video - 60s cut", "1", "2400.00"), ("Social media adaptations", "4", "150.00")], 22),
    "nimbus-cloud-2026-0412-copy.txt": None,  # filled below: duplicate of the first one
}
SCRIPTED["nimbus-cloud-2026-0412-copy.txt"] = SCRIPTED["nimbus-cloud-2026-0412.txt"]


class ScriptedExtractor:
    """Returns pre-extracted data keyed by the invoice number found in the text."""

    def extract(self, document_text: str) -> InvoiceData:
        for data in SCRIPTED.values():
            if data.invoice_number in document_text:
                return data
        raise ExtractionError("Demo mode only knows the files in samples/.")


def build_demo_service() -> InvoiceService:
    service = InvoiceService(InvoiceRepository(":memory:"), ScriptedExtractor())
    for name in SCRIPTED:
        path = SAMPLES / name
        if path.exists():
            service.ingest(name, path.read_bytes())
    return service


def main() -> None:
    import uvicorn

    from .api import create_app

    uvicorn.run(create_app(build_demo_service()), host="127.0.0.1", port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":
    main()
