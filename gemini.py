"""Google Gemini integration boundary.

Gemini is responsible ONLY for extracting business information from uploaded
Purchase Order documents. This module owns the AI extraction integration. It
must not perform validation or Excel generation (see CLAUDE.md).

Prompts are always loaded from the ``prompts/`` directory and never hardcoded.
The schema is appended to the extraction prompt so the model returns data in
the canonical shape.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from ai_gateway import AIGateway
from utils.helpers import read_text_file
from utils.json_handler import load_schema, parse_model_json

logger = logging.getLogger(__name__)


# Appended at call time so the on-disk prompt files remain unchanged. Improves
# extraction on hard documents (handwriting, photos, low-quality scans, rotated
# pages, stamps) and teaches common business abbreviations without hallucinating.
_OCR_UNDERSTANDING_GUIDANCE = (
    "DOCUMENT UNDERSTANDING GUIDANCE:\n"
    "- The document may be a mobile photo, low-quality scan, rotated page, or "
    "contain stamps and mixed printed/handwritten text. Read it carefully.\n"
    "- Interpret common business abbreviations and expand them to their real "
    "meaning while preserving the underlying value: Qty=Quantity, Amt=Amount, "
    "Inv=Invoice, Del=Delivery, Cons=Consignee, Exp=Export, Desc=Description, "
    "UOM=Unit of Measure, HSN=HSN Code, Net Wt=Net Weight, Gross Wt=Gross "
    "Weight, Pkg=Packages, PO=Purchase Order.\n"
    "- Do NOT hallucinate. If a value is uncertain, still extract your best "
    "reading; never invent data that is not present."
)

# Optional confidence-map request appended only by extract_with_confidence.
_CONFIDENCE_GUIDANCE = (
    "CONFIDENCE REPORTING:\n"
    "In addition to the schema fields, include a top-level key named "
    '"_confidence" whose value is a flat JSON object mapping each field\'s '
    "dotted path to an integer confidence from 0 to 100 (e.g. "
    '{"purchase_order.po_number": 100, "buyer.company_name": 98}). '
    "For line-item fields use indexed paths such as \"items[0].quantity\". "
    "Assign high confidence (95-100) to clear printed values, medium (70-94) "
    "to values that required interpretation, and low (0-69) to unclear, "
    "handwritten, or ambiguous values. Base confidence on legibility, not on "
    "how common the value is."
)


class GeminiExtractionError(RuntimeError):
    """Raised when the Gemini extraction call fails or returns unusable output."""


class GeminiClient:
    """Client boundary for extracting document data via Google Gemini.

    The client never selects a model or key itself. It builds the extraction
    instruction and delegates execution to the shared :class:`AIGateway`, which
    chooses the model + key and retries transparently across all of them. This
    keeps every processor on the same failover policy.
    """

    def __init__(
        self,
        gateway: AIGateway,
        system_prompt_path: Path,
        extraction_prompt_path: Path,
        schema_path: Path,
    ) -> None:
        """Initialize the client and load prompts and schema from disk.

        Keys and models are never chosen here; the gateway selects them at
        request time so key + model failover can occur transparently. Models are
        not hardcoded in this extraction engine — they come from the gateway.

        Args:
            gateway: The shared Enterprise AI Gateway (sole AI entry point).
            system_prompt_path: Path to the system prompt file.
            extraction_prompt_path: Path to the extraction prompt file.
            schema_path: Path to the canonical document schema.

        Raises:
            GeminiExtractionError: If no API keys are configured.
        """
        if not gateway.has_capacity():
            raise GeminiExtractionError(
                "No Gemini API keys configured. Set GEMINI_API_KEY or "
                "GEMINI_API_KEY_1, GEMINI_API_KEY_2, ... in the .env file."
            )

        self._gateway = gateway
        self._system_prompt = read_text_file(system_prompt_path)
        self._extraction_prompt = read_text_file(extraction_prompt_path)
        self._schema = load_schema(schema_path)
        logger.info("GeminiClient initialized (gateway-backed).")

    def _build_instruction(self, with_confidence: bool = False) -> str:
        """Combine the extraction prompt with the canonical schema.

        The OCR-understanding guidance and (optional) confidence-map request are
        appended at call time so the on-disk prompt files are never modified.

        Args:
            with_confidence: When True, also request a parallel confidence map.

        Returns:
            The full instruction text.
        """
        schema_text = json.dumps(self._schema, indent=2, ensure_ascii=False)
        instruction = (
            f"{self._extraction_prompt}\n\n"
            f"JSON SCHEMA (return data matching this exact structure):\n"
            f"{schema_text}\n\n"
            f"{_OCR_UNDERSTANDING_GUIDANCE}"
        )
        if with_confidence:
            instruction += f"\n\n{_CONFIDENCE_GUIDANCE}"
        return instruction

    def _generate(
        self, document_bytes: bytes, mime_type: str, with_confidence: bool
    ) -> dict[str, Any]:
        """Run an extraction call through the gateway with key + model failover.

        The request is retried transparently across all configured models and
        API keys by the gateway; the caller never re-uploads the document.
        Retryable vs. fatal classification is centralized in the gateway.
        """
        document_part = types.Part.from_bytes(data=document_bytes, mime_type=mime_type)
        instruction = self._build_instruction(with_confidence)

        def _call(api_key: str, model: str) -> str:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=[instruction, document_part],
                config=types.GenerateContentConfig(
                    system_instruction=self._system_prompt,
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            text = getattr(response, "text", None)
            if not text:
                raise GeminiExtractionError("Gemini returned no text output.")
            return text

        # The gateway raises AIServiceUnavailable when every model/key is
        # exhausted, and re-raises fatal errors unchanged. Only the JSON parse
        # path is reshaped here.
        raw_text = self._gateway.generate(_call)

        try:
            return parse_model_json(raw_text)
        except ValueError as exc:
            logger.error("Failed to parse Gemini output as JSON.")
            raise GeminiExtractionError(str(exc)) from exc

    def extract(self, document_bytes: bytes, mime_type: str) -> dict[str, Any]:
        """Extract standardized document data using the configured prompts/schema.

        This is the document-agnostic extraction entry point. The behaviour is
        identical regardless of document type — the prompts and schema supplied
        at construction time determine what is extracted.

        Args:
            document_bytes: Raw bytes of the uploaded PDF or image.
            mime_type: MIME type of the document.

        Returns:
            The parsed extraction result as a dictionary.

        Raises:
            GeminiExtractionError: If the API call fails or output is unusable.
        """
        return self._generate(document_bytes, mime_type, with_confidence=False)

    def extract_with_confidence(
        self, document_bytes: bytes, mime_type: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Extract data plus an AI-reported per-field confidence map.

        The confidence map (under the ``_confidence`` key) is requested via an
        appended instruction and stripped from the returned data so the document
        still matches its schema.

        Args:
            document_bytes: Raw bytes of the uploaded PDF or image.
            mime_type: MIME type of the document.

        Returns:
            A tuple ``(data, ai_confidence_map)``. The confidence map may be
            empty if the model omitted it; the engine falls back to heuristics.
        """
        result = self._generate(document_bytes, mime_type, with_confidence=True)
        ai_scores = result.pop("_confidence", {}) or {}
        if not isinstance(ai_scores, dict):
            ai_scores = {}
        return result, ai_scores

    def extract_purchase_order(
        self, document_bytes: bytes, mime_type: str
    ) -> dict[str, Any]:
        """Backward-compatible alias for :meth:`extract` (Purchase Order)."""
        return self.extract(document_bytes, mime_type)
