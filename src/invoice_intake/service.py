"""Application service: orchestrates text extraction, AI extraction, checks and review."""

from __future__ import annotations

from .checks import check_invoice
from .extractor import ExtractionError, Extractor
from .models import Invoice, InvoiceData, ReviewDecision, Status
from .repository import InvoiceRepository
from .text_extraction import extract_text


class InvalidTransition(ValueError):
    pass


class InvoiceService:
    def __init__(self, repo: InvoiceRepository, extractor: Extractor) -> None:
        self.repo = repo
        self.extractor = extractor

    def ingest(self, filename: str, content: bytes) -> Invoice:
        text = extract_text(filename, content)  # raises UnsupportedDocument
        try:
            data = self.extractor.extract(text)
        except ExtractionError as exc:
            return self.repo.add(filename, Status.FAILED, None, [str(exc)])
        issues = check_invoice(data, seen_numbers=self.repo.known_numbers())
        status = Status.NEEDS_REVIEW if issues else Status.READY
        return self.repo.add(filename, status, data, issues)

    def correct(self, invoice: Invoice, data: InvoiceData) -> Invoice:
        """A reviewer fixes extracted values; checks run again."""
        self._ensure_open(invoice)
        invoice.data = data
        invoice.issues = check_invoice(data, seen_numbers=self.repo.known_numbers(invoice.id))
        invoice.status = Status.NEEDS_REVIEW if invoice.issues else Status.READY
        return self.repo.update(invoice)

    def approve(self, invoice: Invoice, decision: ReviewDecision) -> Invoice:
        self._ensure_open(invoice)
        if invoice.status != Status.READY:
            raise InvalidTransition("Resolve the open issues (or correct the data) before approving.")
        return self._close(invoice, Status.APPROVED, decision)

    def reject(self, invoice: Invoice, decision: ReviewDecision) -> Invoice:
        self._ensure_open(invoice)
        if not decision.note:
            raise InvalidTransition("A note is required when rejecting an invoice.")
        return self._close(invoice, Status.REJECTED, decision)

    def _close(self, invoice: Invoice, status: Status, decision: ReviewDecision) -> Invoice:
        invoice.status = status
        invoice.reviewed_by = decision.reviewer
        invoice.review_note = decision.note
        return self.repo.update(invoice)

    @staticmethod
    def _ensure_open(invoice: Invoice) -> None:
        if invoice.status in (Status.APPROVED, Status.REJECTED):
            raise InvalidTransition(f"Invoice already {invoice.status.value}.")
