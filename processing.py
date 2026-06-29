"""Per-document processing orchestration.

Ties together preprocessing, classification (auto mode) or direct assignment
(manual mode), AI extraction, the extraction cache, deterministic auto-fix,
schema normalization, confidence scoring, and validation for a single uploaded
document — independent of document type. This is the only place Gemini is
called; once a ``DocumentState`` carries ``data`` all editing and re-export
happen without further AI calls.

``process_batch`` decouples the per-document loop from the UI (it takes a plain
progress callback and never touches Streamlit), so it can later be driven by a
background worker/queue without changes here.
"""

from __future__ import annotations

import copy
import logging
from typing import Callable

import cache
import cost
import preprocess
from ai_gateway import AIServiceUnavailable
from classifier import DocumentClassifier
from config import ai_gateway
from document_state import DocumentState
from gemini import GeminiExtractionError
from processors.base import BaseProcessor
from utils.confidence import compute_confidence
from utils.json_handler import load_schema
from utils.validators import normalize_to_schema

logger = logging.getLogger(__name__)

#: progress_cb(done: float, total: int, doc: DocumentState, phase: str) -> None
ProgressCallback = Callable[[float, int, DocumentState, str], None]


def classify_document(
    doc: DocumentState,
    classifier: DocumentClassifier,
    candidates: list[BaseProcessor],
) -> None:
    """Detect the document type and assign the matching processor in place.

    Args:
        doc: The document to classify (updated in place).
        classifier: The shared document classifier.
        candidates: Candidate processors (department-scoped, production only).
    """
    result = classifier.classify(doc.file_bytes, doc.mime_type, candidates)
    doc.processor = result.processor
    doc.document_type = result.document_type
    doc.classification_confidence = result.confidence
    doc.classification_method = result.method
    if result.processor is None:
        doc.status = "unsupported"
        doc.error = "Unsupported document type."


def assign_processor(doc: DocumentState, processor: BaseProcessor) -> None:
    """Assign a processor directly (Manual mode — no classification needed)."""
    doc.processor = processor
    doc.document_type = processor.spec.document_type
    doc.classification_confidence = 100
    doc.classification_method = "manual"


def extract_document(doc: DocumentState) -> None:
    """Run extraction + auto-fix + normalization + confidence + validation.

    Uses the extraction cache (keyed by content + processor + prompt version) to
    skip Gemini on repeat uploads, applies OCR preprocessing before the model,
    and records token usage for cost tracking.

    Args:
        doc: A classified/assigned, supported document (updated in place).
    """
    if doc.processor is None:
        doc.status = "unsupported"
        doc.error = "Unsupported document type."
        return

    processor = doc.processor
    spec = processor.spec
    try:
        cache_key = cache.make_key(doc.file_bytes, spec.use_case_key, spec.prompt_version)
        cached = cache.load(cache_key)
        if cached is not None:
            raw, ai_scores = cached.get("data", {}), cached.get("ai_scores", {})
        else:
            parts = [
                (part.data, part.mime_type)
                for part in preprocess.prepare(doc.file_bytes, doc.mime_type)
            ]
            client = processor.build_client()
            raw, ai_scores = client.extract_with_confidence(parts)
            doc.usage = client.last_usage
            cost.record(
                spec.use_case_key,
                spec.department_key,
                str(ai_gateway.status().get("model", "")),
                doc.usage,
            )
            cache.store(cache_key, raw, ai_scores)

        schema = load_schema(processor.schema_path())
        normalized = normalize_to_schema(raw, schema)
        normalized.setdefault("metadata", {}).setdefault("source", {})[
            "filename"
        ] = doc.filename

        # Validation -> Auto-Fix -> (review) -> Export: deterministic repairs run
        # before validation; the data the reviewer sees becomes the audit baseline.
        normalized, notes = processor.auto_fix(normalized)
        doc.autofix_notes = notes

        doc.data = normalized
        doc.extracted_original = copy.deepcopy(normalized)
        doc.confidence = compute_confidence(normalized, ai_scores)
        doc.issues = processor.validate(normalized)
        doc.status = "done"
        logger.info("Extracted '%s' as %s.", doc.filename, doc.document_type)
    except AIServiceUnavailable as exc:
        # Every model/key was exhausted across all retry cycles. Surface the
        # clean, non-sensitive "AI Service Temporarily Unavailable" message.
        logger.warning(
            "Extraction halted for %s: AI service temporarily unavailable.",
            doc.filename,
        )
        doc.status = "error"
        doc.error = str(exc)
    except (GeminiExtractionError, ValueError) as exc:
        logger.exception("Extraction failed for %s.", doc.filename)
        doc.status = "error"
        doc.error = str(exc)


def process_batch(
    docs: list[DocumentState],
    *,
    processor: BaseProcessor | None = None,
    classifier: DocumentClassifier | None = None,
    candidates: list[BaseProcessor] | None = None,
    progress_cb: ProgressCallback | None = None,
) -> None:
    """Process a batch of documents (each independently), reporting progress.

    Exactly one routing strategy is used:
    - **Manual mode**: pass ``processor`` to assign it to every document.
    - **Auto Detect**: pass ``classifier`` + ``candidates`` to classify each.

    Args:
        docs: Documents to process (mutated in place).
        processor: Fixed processor for manual mode.
        classifier: Classifier for auto mode.
        candidates: Candidate processors for auto mode.
        progress_cb: Optional progress callback (no Streamlit dependency).
    """
    total = len(docs)
    for index, doc in enumerate(docs):
        if progress_cb:
            progress_cb(index, total, doc, "classifying")
        if processor is not None:
            assign_processor(doc, processor)
        elif classifier is not None and candidates:
            classify_document(doc, classifier, candidates)
        else:
            doc.status = "unsupported"
            doc.error = "No processor selected."

        if doc.supported:
            if progress_cb:
                progress_cb(index + 0.5, total, doc, "extracting")
            extract_document(doc)

        if progress_cb:
            progress_cb(index + 1, total, doc, "done")


def build_classifier() -> DocumentClassifier:
    """Construct a classifier backed by the shared AI gateway."""
    return DocumentClassifier(gateway=ai_gateway)
