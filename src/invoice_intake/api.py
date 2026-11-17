"""REST API and review dashboard."""

from __future__ import annotations

import csv
import io
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from .extractor import ClaudeExtractor, Extractor
from .models import Invoice, InvoiceData, ReviewDecision, Status
from .repository import InvoiceRepository
from .service import InvalidTransition, InvoiceService
from .text_extraction import UnsupportedDocument

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def create_app(service: InvoiceService | None = None) -> FastAPI:
    if service is None:
        repo = InvoiceRepository(os.getenv("INVOICE_DB", "data/invoices.db"))
        extractor: Extractor = ClaudeExtractor()
        service = InvoiceService(repo, extractor)

    app = FastAPI(
        title="Invoice Intake AI",
        description="Extract supplier invoices with Claude, verify them in code, approve them with a human in the loop.",
        version="1.0.0",
    )
    app.state.service = service

    def _get(invoice_id: int) -> Invoice:
        invoice = service.repo.get(invoice_id)
        if invoice is None:
            raise HTTPException(404, "Invoice not found")
        return invoice

    @app.get("/", include_in_schema=False)
    def dashboard() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.post("/api/invoices", response_model=Invoice, status_code=201)
    async def upload(file: UploadFile) -> Invoice:
        content = await file.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "File too large (max 10 MB)")
        try:
            return service.ingest(file.filename or "upload", content)
        except UnsupportedDocument as exc:
            raise HTTPException(415, str(exc)) from exc

    @app.get("/api/invoices", response_model=list[Invoice])
    def list_invoices(status: Status | None = None) -> list[Invoice]:
        return service.repo.list(status)

    @app.get("/api/invoices/export.csv")
    def export_approved() -> StreamingResponse:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "supplier", "vat_id", "number", "issue_date", "due_date",
                         "currency", "net", "vat", "total", "approved_by"])
        for inv in service.repo.list(Status.APPROVED):
            d = inv.data
            writer.writerow([inv.id, d.supplier_name, d.supplier_vat_id or "", d.invoice_number,
                             d.issue_date, d.due_date or "", d.currency, d.net_amount,
                             d.vat_amount, d.total_amount, inv.reviewed_by])
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=approved_invoices.csv"},
        )

    @app.get("/api/invoices/{invoice_id}", response_model=Invoice)
    def get_invoice(invoice_id: int) -> Invoice:
        return _get(invoice_id)

    @app.put("/api/invoices/{invoice_id}/data", response_model=Invoice)
    def correct(invoice_id: int, data: InvoiceData) -> Invoice:
        try:
            return service.correct(_get(invoice_id), data)
        except InvalidTransition as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/invoices/{invoice_id}/approve", response_model=Invoice)
    def approve(invoice_id: int, decision: ReviewDecision) -> Invoice:
        try:
            return service.approve(_get(invoice_id), decision)
        except InvalidTransition as exc:
            raise HTTPException(409, str(exc)) from exc

    @app.post("/api/invoices/{invoice_id}/reject", response_model=Invoice)
    def reject(invoice_id: int, decision: ReviewDecision) -> Invoice:
        try:
            return service.reject(_get(invoice_id), decision)
        except InvalidTransition as exc:
            raise HTTPException(409, str(exc)) from exc

    return app


def main() -> None:
    import uvicorn

    uvicorn.run(create_app(), host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8000")))
