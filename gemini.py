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
    "- MULTI-PAGE: Treat every page/image provided as ONE logical document. "
    "Combine information across all pages; a value printed on one page applies "
    "to the whole document. Never process pages in isolation.\n"
    "- HANDWRITING: When the same field appears both printed and handwritten and "
    "the handwritten value is a clear correction or the actual recorded value, "
    "PREFER the confident handwritten value over the printed one.\n"
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
        #: Token usage of the most recent request (populated after each call).
        self._last_usage: dict[str, int] = {}
        logger.info("GeminiClient initialized (gateway-backed).")

    @property
    def last_usage(self) -> dict[str, int]:
        """Token usage of the most recent extraction (for cost tracking)."""
        return dict(self._last_usage)

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
        self, parts: list[tuple[bytes, str]], with_confidence: bool
    ) -> dict[str, Any]:
        """Run an extraction call through the gateway with key + model failover.

        Sends one or more document parts (a native PDF, or one image per page of
        a preprocessed scan) as a single logical document. The request is retried
        transparently across all configured models and API keys by the gateway;
        the caller never re-uploads. Retryable vs. fatal classification is
        centralized in the gateway. Token usage is captured for cost tracking.

        Args:
            parts: A non-empty list of ``(bytes, mime_type)`` document parts.
            with_confidence: Whether to also request a parallel confidence map.
        """
        document_parts = [
            types.Part.from_bytes(data=data, mime_type=mime) for data, mime in parts
        ]
        instruction = self._build_instruction(with_confidence)
        self._last_usage = {}

        def _call(api_key: str, model: str) -> str:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model,
                contents=[instruction, *document_parts],
                config=types.GenerateContentConfig(
                    system_instruction=self._system_prompt,
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            self._capture_usage(response)
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

    def _capture_usage(self, response: Any) -> None:
        """Record token usage from a response's usage metadata (best-effort)."""
        meta = getattr(response, "usage_metadata", None)
        if meta is None:
            return
        input_tokens = int(getattr(meta, "prompt_token_count", 0) or 0)
        output_tokens = int(getattr(meta, "candidates_token_count", 0) or 0)
        total = int(getattr(meta, "total_token_count", 0) or (input_tokens + output_tokens))
        self._last_usage = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total,
        }

    @staticmethod
    def _as_parts(
        document: bytes | list[tuple[bytes, str]],
        mime_type: str | None,
    ) -> list[tuple[bytes, str]]:
        """Normalize a (bytes, mime) pair or an explicit parts list into parts."""
        if isinstance(document, (bytes, bytearray)):
            if not mime_type:
                raise GeminiExtractionError("mime_type is required for raw bytes.")
            return [(bytes(document), mime_type)]
        return list(document)

    def extract(
        self,
        document: bytes | list[tuple[bytes, str]],
        mime_type: str | None = None,
    ) -> dict[str, Any]:
        """Extract standardized document data using the configured prompts/schema.

        This is the document-agnostic extraction entry point. Accepts either raw
        ``document`` bytes with a ``mime_type``, or an explicit list of
        ``(bytes, mime_type)`` parts (e.g. preprocessed page images).

        Returns:
            The parsed extraction result as a dictionary.

        Raises:
            GeminiExtractionError: If the API call fails or output is unusable.
        """
        return self._generate(self._as_parts(document, mime_type), with_confidence=False)

    def extract_with_confidence(
        self,
        document: bytes | list[tuple[bytes, str]],
        mime_type: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Extract data plus an AI-reported per-field confidence map.

        The confidence map (under the ``_confidence`` key) is requested via an
        appended instruction and stripped from the returned data so the document
        still matches its schema. Accepts raw bytes + MIME type or an explicit
        list of ``(bytes, mime_type)`` parts.

        Returns:
            A tuple ``(data, ai_confidence_map)``. The confidence map may be
            empty if the model omitted it; the engine falls back to heuristics.
        """
        result = self._generate(self._as_parts(document, mime_type), with_confidence=True)
        ai_scores = result.pop("_confidence", {}) or {}
        if not isinstance(ai_scores, dict):
            ai_scores = {}
        return result, ai_scores
