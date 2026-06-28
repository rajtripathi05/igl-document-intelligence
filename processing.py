"""Per-document processing orchestration.

Ties together classification, extraction, confidence scoring, normalization, and
validation for a single uploaded document — independent of document type. This
is the only place Gemini is called; once a ``DocumentState`` carries ``data``,
all editing and re-export happen without further AI calls.
"""

from __future__ import annotations

import logging

from api_key_manager import AllKeysExhausted
from classifier import DocumentClassifier
from config import gemini_key_manager, settings
from document_state import DocumentState
from gemini import GeminiExtractionError
from processors.base import BaseProcessor
from utils.confidence import compute_confidence
from utils.json_handler import load_schema
from utils.validators import normalize_to_schema

logger = logging.getLogger(__name__)


def classify_document(
    doc: DocumentState,
    classifier: DocumentClassifier,
    candidates: list[BaseProcessor],
) -> None:
    """Detect the document type and assign the matching processor in place.

    Args:
        doc: The document to classify (updated in place).
        classifier: The shared document classifier.
        candidates: Candidate processors (e.g. department-scoped).
    """
    result = classifier.classify(doc.file_bytes, doc.mime_type, candidates)
    doc.processor = result.processor
    doc.document_type = result.document_type
    doc.classification_confidence = result.confidence
    doc.classification_method = result.method
    if result.processor is None:
        doc.status = "unsupported"
        doc.error = "Unsupported document type."


def extract_document(doc: DocumentState) -> None:
    """Run extraction + confidence + normalization + validation in place.

    Args:
        doc: A classified, supported document (updated in place).
    """
    if doc.processor is None:
        doc.status = "unsupported"
        doc.error = "Unsupported document type."
        return

    try:
        client = doc.processor.build_client()
        raw, ai_scores = client.extract_with_confidence(doc.file_bytes, doc.mime_type)

        schema = load_schema(doc.processor.schema_path())
        normalized = normalize_to_schema(raw, schema)
        normalized.setdefault("metadata", {}).setdefault("source", {})[
            "filename"
        ] = doc.filename

        doc.data = normalized
        doc.confidence = compute_confidence(normalized, ai_scores)
        doc.issues = doc.processor.validate(normalized)
        doc.status = "done"
        logger.info("Extracted '%s' as %s.", doc.filename, doc.document_type)
    except AllKeysExhausted as exc:
        # Friendly, non-sensitive message; every key is rate-limited.
        logger.warning("Extraction halted for %s: all keys rate-limited.", doc.filename)
        doc.status = "error"
        doc.error = str(exc)
    except (GeminiExtractionError, ValueError) as exc:
        logger.exception("Extraction failed for %s.", doc.filename)
        doc.status = "error"
        doc.error = str(exc)


def build_classifier() -> DocumentClassifier:
    """Construct a classifier from application settings."""
    return DocumentClassifier(
        key_manager=gemini_key_manager, model=settings.gemini_model
    )
