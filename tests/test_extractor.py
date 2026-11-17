from types import SimpleNamespace

import pytest

from invoice_intake.extractor import TOOL_NAME, ClaudeExtractor, ExtractionError

from .conftest import fake_client


def test_forces_structured_tool_call_and_parses_result(clean_invoice):
    client = fake_client(clean_invoice.model_dump(mode="json"))
    data = ClaudeExtractor(client=client, model="test-model").extract("INVOICE HM-0098 ...")

    assert data == clean_invoice
    req = client.messages.last_request
    assert req["model"] == "test-model"
    assert req["tool_choice"] == {"type": "tool", "name": TOOL_NAME}
    schema = req["tools"][0]["input_schema"]
    assert {"invoice_number", "total_amount", "line_items"} <= set(schema["properties"])
    assert "<invoice>" in req["messages"][0]["content"]


def test_missing_tool_call_raises():
    client = fake_client(blocks=[SimpleNamespace(type="text", text="Sorry")])
    with pytest.raises(ExtractionError, match="structured data"):
        ClaudeExtractor(client=client).extract("text")


def test_invalid_payload_raises(clean_invoice):
    payload = clean_invoice.model_dump(mode="json")
    payload["issue_date"] = "not a date"
    with pytest.raises(ExtractionError, match="validation"):
        ClaudeExtractor(client=fake_client(payload)).extract("text")
