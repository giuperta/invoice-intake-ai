from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient

from invoice_intake.api import create_app
from invoice_intake.demo import build_demo_service
from invoice_intake.repository import InvoiceRepository
from invoice_intake.service import InvoiceService

from .conftest import StaticExtractor


@pytest.fixture
def make_client():
    def _make(data):
        return TestClient(create_app(InvoiceService(InvoiceRepository(), StaticExtractor(data))))
    return _make


def upload(client, name="inv.txt", body=b"INVOICE HM-0098"):
    return client.post("/api/invoices", files={"file": (name, body, "text/plain")})


def test_happy_path_upload_approve_export(make_client, clean_invoice):
    client = make_client(clean_invoice)
    inv = upload(client).json()
    assert inv["status"] == "ready_for_approval"

    approved = client.post(f"/api/invoices/{inv['id']}/approve", json={"reviewer": "Giuseppe"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    csv_text = client.get("/api/invoices/export.csv").text
    assert "HM-0098" in csv_text and "Giuseppe" in csv_text


def test_cannot_approve_with_open_issues_until_corrected(make_client, clean_invoice):
    wrong = clean_invoice.model_copy(update={"total_amount": D("9999")})
    client = make_client(wrong)
    inv = upload(client).json()
    assert inv["status"] == "needs_review" and inv["issues"]

    assert client.post(f"/api/invoices/{inv['id']}/approve", json={"reviewer": "G"}).status_code == 409

    fixed = client.put(f"/api/invoices/{inv['id']}/data", json=clean_invoice.model_dump(mode="json"))
    assert fixed.json()["status"] == "ready_for_approval"
    assert client.post(f"/api/invoices/{inv['id']}/approve", json={"reviewer": "G"}).status_code == 200


def test_reject_requires_note_and_closes_invoice(make_client, clean_invoice):
    client = make_client(clean_invoice)
    inv_id = upload(client).json()["id"]
    assert client.post(f"/api/invoices/{inv_id}/reject", json={"reviewer": "G"}).status_code == 409
    r = client.post(f"/api/invoices/{inv_id}/reject", json={"reviewer": "G", "note": "Not our order"})
    assert r.json()["status"] == "rejected"
    # closed invoices cannot be changed any more
    assert client.post(f"/api/invoices/{inv_id}/approve", json={"reviewer": "G"}).status_code == 409


def test_second_upload_is_flagged_as_duplicate(make_client, clean_invoice):
    client = make_client(clean_invoice)
    upload(client)
    second = upload(client, "copy.txt").json()
    assert any("duplicate" in i for i in second["issues"])


def test_validation_and_errors(make_client, clean_invoice):
    client = make_client(clean_invoice)
    assert upload(client, "photo.jpg").status_code == 415
    assert client.get("/api/invoices/42").status_code == 404
    assert client.post("/api/invoices/1/approve", json={"reviewer": ""}).status_code == 422


def test_filter_by_status_and_dashboard(make_client, clean_invoice):
    client = make_client(clean_invoice)
    upload(client)
    assert len(client.get("/api/invoices", params={"status": "approved"}).json()) == 0
    assert len(client.get("/api/invoices", params={"status": "ready_for_approval"}).json()) == 1
    assert "Invoice Intake AI" in client.get("/").text


def test_demo_dataset_covers_every_check():
    service = build_demo_service()
    by_file = {i.filename: i for i in service.repo.list()}
    assert by_file["helix-media-HM-0098.txt"].status.value == "ready_for_approval"
    assert any("Net + VAT" in x for x in by_file["alpine-logistics-A-7781.txt"].issues)
    cobalt = " ".join(by_file["cobalt-systems-INV-2210.txt"].issues)
    assert "VAT number missing" in cobalt and "Due date" in cobalt
    assert any("duplicate" in x for x in by_file["nimbus-cloud-2026-0412-copy.txt"].issues)
