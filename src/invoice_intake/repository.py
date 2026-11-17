"""SQLite persistence for invoices (swap for PostgreSQL in production)."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from .models import Invoice, InvoiceData, Status

SCHEMA = """
CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    status TEXT NOT NULL,
    data TEXT,
    issues TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    reviewed_by TEXT,
    review_note TEXT
);
"""


class InvoiceRepository:
    def __init__(self, path: Path | str = ":memory:") -> None:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()

    def _to_model(self, row: sqlite3.Row) -> Invoice:
        return Invoice(
            id=row["id"],
            filename=row["filename"],
            status=Status(row["status"]),
            data=InvoiceData.model_validate_json(row["data"]) if row["data"] else None,
            issues=json.loads(row["issues"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            reviewed_by=row["reviewed_by"],
            review_note=row["review_note"],
        )

    def add(self, filename: str, status: Status, data: InvoiceData | None, issues: list[str]) -> Invoice:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO invoices (filename, status, data, issues, created_at) VALUES (?,?,?,?,?)",
                (
                    filename,
                    status.value,
                    data.model_dump_json() if data else None,
                    json.dumps(issues),
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
        return self.get(cur.lastrowid)

    def get(self, invoice_id: int) -> Invoice | None:
        row = self._conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        return self._to_model(row) if row else None

    def list(self, status: Status | None = None) -> list[Invoice]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM invoices WHERE status = ? ORDER BY id DESC", (status.value,)
            )
        else:
            rows = self._conn.execute("SELECT * FROM invoices ORDER BY id DESC")
        return [self._to_model(r) for r in rows]

    def update(self, invoice: Invoice) -> Invoice:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE invoices SET status=?, data=?, issues=?, reviewed_by=?, review_note=? WHERE id=?",
                (
                    invoice.status.value,
                    invoice.data.model_dump_json() if invoice.data else None,
                    json.dumps(invoice.issues),
                    invoice.reviewed_by,
                    invoice.review_note,
                    invoice.id,
                ),
            )
        return self.get(invoice.id)

    def known_numbers(self, exclude_id: int | None = None) -> set[tuple[str, str]]:
        seen = set()
        for inv in self.list():
            if inv.data and inv.id != exclude_id and inv.status != Status.REJECTED:
                seen.add((inv.data.supplier_name.lower(), inv.data.invoice_number))
        return seen
