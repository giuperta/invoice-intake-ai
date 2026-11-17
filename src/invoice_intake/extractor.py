"""Structured extraction with the Claude API.

The model is *forced* to answer by calling a tool whose input schema is the
Pydantic model, so the output is always machine-readable JSON that we then
validate with Pydantic. No fragile parsing of free text.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

from pydantic import ValidationError

from .models import InvoiceData

SYSTEM_PROMPT = """\
You extract data from supplier invoices for an accounts-payable team.
Rules:
- Copy values exactly as printed; never invent missing data (use null for optional fields).
- Amounts are plain numbers without currency symbols or thousand separators.
- Dates in ISO 8601 (YYYY-MM-DD). Convert from European formats (DD/MM/YYYY) when needed.
- Do not correct arithmetic errors in the document: report what is written.
"""

TOOL_NAME = "record_invoice"


class ExtractionError(RuntimeError):
    pass


class Extractor(Protocol):
    def extract(self, document_text: str) -> InvoiceData: ...


def _tool_definition() -> dict[str, Any]:
    return {
        "name": TOOL_NAME,
        "description": "Record the structured content of one invoice.",
        "input_schema": InvoiceData.model_json_schema(),
    }


class ClaudeExtractor:
    def __init__(self, client: Any = None, model: str | None = None, max_tokens: int = 2048) -> None:
        if client is None:
            import anthropic  # imported lazily so tests don't need an API key

            client = anthropic.Anthropic()
        self.client = client
        self.model = model or os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
        self.max_tokens = max_tokens

    def extract(self, document_text: str) -> InvoiceData:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            tools=[_tool_definition()],
            tool_choice={"type": "tool", "name": TOOL_NAME},
            messages=[
                {
                    "role": "user",
                    "content": f"<invoice>\n{document_text}\n</invoice>",
                }
            ],
        )
        payload = next(
            (b.input for b in response.content if getattr(b, "type", None) == "tool_use"),
            None,
        )
        if payload is None:
            raise ExtractionError("The model did not return structured data.")
        try:
            return InvoiceData.model_validate(payload)
        except ValidationError as exc:
            raise ExtractionError(f"Extracted data failed validation: {exc}") from exc
