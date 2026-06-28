"""Automatic document classifier.

Given an uploaded document and the set of candidate processors (from the
registry), the classifier detects which document type it is and returns the
matching processor — no manual document-type selection required.

The classifier is fully driven by processor metadata (``ProcessorSpec``):
``document_type``, ``ai_description``, and ``keywords``. Adding a new processor
automatically extends classification with no changes here. There are no
per-document-type if/else branches.

Strategy:
1. Primary: ask Gemini to choose the best-matching ``use_case_key`` from the
   candidates' descriptions.
2. Fallback: keyword scoring over a quick text rendering of the document.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from google import genai
from google.genai import types

from api_key_manager import GeminiKeyManager
from gemini_errors import run_with_rotation
from processors.base import BaseProcessor

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClassificationResult:
    """Outcome of classifying a document.

    Attributes:
        processor: The matched processor, or None if unsupported.
        use_case_key: The detected use-case key (may be set even if processor
            is None when the detected type has no registered processor).
        document_type: Human-readable detected document type.
        confidence: Classification confidence (0–100).
        method: ``"ai"`` or ``"keyword"`` — how the match was made.
    """

    processor: BaseProcessor | None
    use_case_key: str | None
    document_type: str
    confidence: int
    method: str


class DocumentClassifier:
    """Detects a document's type and routes it to the correct processor."""

    def __init__(self, key_manager: GeminiKeyManager, model: str) -> None:
        """Initialize the classifier.

        Args:
            key_manager: The Gemini API key manager (sole source of keys).
            model: Gemini model identifier.
        """
        self._keys = key_manager
        self._model = model

    def classify(
        self,
        document_bytes: bytes,
        mime_type: str,
        candidates: list[BaseProcessor],
    ) -> ClassificationResult:
        """Classify a document against candidate processors.

        Args:
            document_bytes: Raw bytes of the uploaded document.
            mime_type: Document MIME type.
            candidates: Registered processors to choose among (e.g. those in the
                selected department, or all processors).

        Returns:
            A :class:`ClassificationResult`.
        """
        if not candidates:
            return ClassificationResult(None, None, "Unknown", 0, "keyword")

        if self._keys.has_available_key():
            result = self._classify_with_ai(document_bytes, mime_type, candidates)
            if result is not None:
                return result

        return self._classify_with_keywords(document_bytes, mime_type, candidates)

    def _classify_with_ai(
        self,
        document_bytes: bytes,
        mime_type: str,
        candidates: list[BaseProcessor],
    ) -> ClassificationResult | None:
        """Use Gemini to choose the best-matching processor."""
        catalog = [
            {
                "use_case_key": p.spec.use_case_key,
                "document_type": p.spec.document_type,
                "description": p.spec.ai_description,
                "keywords": p.spec.keywords,
            }
            for p in candidates
        ]
        instruction = (
            "You are a document classification engine. Identify the business "
            "document type of the attached file and choose the single best match "
            "from the catalog below. Respond ONLY with JSON of the form "
            '{"use_case_key": "<key or null>", "document_type": "<name>", '
            '"confidence": <0-100>}. Use null for use_case_key if none match.\n\n'
            f"CATALOG:\n{json.dumps(catalog, indent=2)}"
        )
        part = types.Part.from_bytes(data=document_bytes, mime_type=mime_type)

        def _call(api_key: str) -> str:
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=self._model,
                contents=[instruction, part],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", temperature=0.0
                ),
            )
            return getattr(response, "text", "") or "{}"

        try:
            payload = json.loads(run_with_rotation(self._keys, _call))
        except Exception:  # noqa: BLE001 - fall back to keyword scoring
            logger.exception("AI classification failed; falling back to keywords.")
            return None

        key = payload.get("use_case_key")
        by_key = {p.spec.use_case_key: p for p in candidates}
        processor = by_key.get(key)
        document_type = payload.get("document_type") or (
            processor.spec.document_type if processor else "Unknown"
        )
        confidence = int(payload.get("confidence") or (90 if processor else 0))
        logger.info("AI classified document as '%s' (%s%%).", document_type, confidence)
        return ClassificationResult(
            processor=processor,
            use_case_key=key,
            document_type=document_type,
            confidence=confidence,
            method="ai",
        )

    def _classify_with_keywords(
        self,
        document_bytes: bytes,
        mime_type: str,
        candidates: list[BaseProcessor],
    ) -> ClassificationResult:
        """Score candidates by keyword overlap with a quick text rendering."""
        text = _extract_text(document_bytes, mime_type).lower()
        best: BaseProcessor | None = None
        best_score = 0
        for processor in candidates:
            score = sum(1 for kw in processor.spec.keywords if kw.lower() in text)
            if score > best_score:
                best, best_score = processor, score

        if best is None or best_score == 0:
            # Default to the only candidate if there is exactly one.
            if len(candidates) == 1:
                only = candidates[0]
                return ClassificationResult(
                    only, only.spec.use_case_key, only.spec.document_type, 60, "keyword"
                )
            return ClassificationResult(None, None, "Unknown", 0, "keyword")

        confidence = min(90, 50 + best_score * 10)
        logger.info(
            "Keyword classified as '%s' (score=%d).",
            best.spec.document_type,
            best_score,
        )
        return ClassificationResult(
            best, best.spec.use_case_key, best.spec.document_type, confidence, "keyword"
        )


def _extract_text(document_bytes: bytes, mime_type: str) -> str:
    """Best-effort quick text extraction for keyword fallback (PDF only)."""
    if mime_type != "application/pdf":
        return ""
    try:
        import fitz  # PyMuPDF

        with fitz.open(stream=document_bytes, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc)
    except Exception:  # noqa: BLE001 - text extraction is best-effort
        logger.debug("Quick PDF text extraction failed.", exc_info=True)
        return ""
