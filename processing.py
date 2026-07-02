"""Per-document processing orchestration.

Ties together preprocessing, classification (auto mode) or direct assignment
(manual mode), AI extraction, the extraction cache, deterministic auto-fix,
schema normalization, confidence scoring, validation, SAP-readiness, and cost
tracking for a single uploaded document — independent of document type. This is
the only place AI extraction is invoked; once a ``DocumentState`` carries
``data`` all editing and re-export happen without further AI calls.

Two extraction entry points share one finalization core:

- :func:`extract_document` — normal processing on the DEFAULT model.
- :func:`retry_extract_document` — the single, user-triggered retry on the
  RETRY (stronger) model. It reuses the cached OCR/preprocessing and the uploaded
  document, replaces the extraction only on success, and never overwrites good
  data on failure.

``process_batch`` decouples the per-document loop from the UI (it takes a plain
progress callback and never touches Streamlit), so it can later be driven by a
background worker/queue without changes here.
"""

from __future__ import annotations

import copy
import logging
import time
from typing import Callable

import cache
import cost
import duplicates
import preprocess
import sap
from ai_gateway import AIServiceUnavailable
from classifier import DocumentClassifier
from config import ai_gateway
from document_state import DocumentState
from gemini import GeminiExtractionError
from processors.base import BaseProcessor
from providers.base import AIError
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
    """Detect the document type and assign the matching processor in place."""
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


def _prepared_parts(doc: DocumentState) -> list[tuple[bytes, str]]:
    """Return preprocessed document parts, caching them on the doc for reuse."""
    if doc.parts is None:
        doc.parts = [
            (part.data, part.mime_type)
            for part in preprocess.prepare(doc.file_bytes, doc.mime_type)
        ]
    return doc.parts


def _finalize(
    doc: DocumentState,
    raw: dict,
    ai_scores: dict,
    on_stage: Callable[[str], None] | None = None,
) -> None:
    """Normalize → auto-fix → validate → confidence → SAP (shared by both paths)."""
    def _stage(name: str) -> None:
        if on_stage is not None:
            on_stage(name)

    processor = doc.processor
    assert processor is not None
    spec = processor.spec

    _stage("extraction")
    schema = load_schema(processor.schema_path())
    normalized = normalize_to_schema(raw, schema)
    normalized.setdefault("metadata", {}).setdefault("source", {})["filename"] = doc.filename

    # Validation -> Auto-Fix -> (review) -> Export: deterministic repairs run
    # before validation; the data the reviewer sees becomes the audit baseline.
    normalized, notes = processor.auto_fix(normalized)
    doc.autofix_notes = notes
    doc.data = normalized
    doc.extracted_original = copy.deepcopy(normalized)

    _stage("validation")
    doc.issues = processor.validate(normalized)

    _stage("confidence")
    doc.confidence = compute_confidence(normalized, ai_scores)

    _stage("sap")
    doc.sap = sap.assess(doc, spec)

    doc.status = "done"


def extract_document(
    doc: DocumentState,
    on_stage: Callable[[str], None] | None = None,
) -> None:
    """Run extraction + auto-fix + normalization + confidence + validation + SAP.

    Uses the extraction cache (keyed by content + processor + prompt version) to
    skip the AI call on repeat uploads, applies OCR preprocessing before the
    model, records token usage + processing time for cost tracking, and registers
    the document's fingerprint for duplicate detection.

    Args:
        doc: A classified/assigned, supported document (updated in place).
        on_stage: Optional callback invoked with each pipeline stage name
            (``"ocr"``, ``"ai"``, ``"extraction"``, ``"validation"``,
            ``"confidence"``, ``"sap"``) so the UI can illuminate the pipeline.
    """
    if doc.processor is None:
        doc.status = "unsupported"
        doc.error = "Unsupported document type."
        return

    def _stage(name: str) -> None:
        if on_stage is not None:
            on_stage(name)

    processor = doc.processor
    spec = processor.spec
    try:
        _stage("ocr")
        cache_key = cache.make_key(doc.file_bytes, spec.use_case_key, spec.prompt_version)
        cached = cache.load(cache_key)
        started = time.perf_counter()
        if cached is not None:
            raw, ai_scores = cached.get("data", {}), cached.get("ai_scores", {})
            _stage("ai")
            doc.model_used = ai_gateway.default_model
        else:
            parts = _prepared_parts(doc)
            _stage("ai")
            client = processor.build_client()
            raw, ai_scores = client.extract_with_confidence(parts)
            doc.usage = client.last_usage
            model = str(ai_gateway.status().get("model", "")) or ai_gateway.default_model
            doc.proc_ms = int((time.perf_counter() - started) * 1000)
            doc.model_used = model
            cost.record(
                spec.use_case_key,
                spec.department_key,
                model,
                doc.usage,
                model_role=cost.ROLE_DEFAULT,
                proc_ms=doc.proc_ms,
                is_retry=False,
            )
            cache.store(cache_key, raw, ai_scores)

        _finalize(doc, raw, ai_scores, on_stage=_stage)

        duplicates.record(
            duplicates.fingerprint(doc.file_bytes),
            processor=spec.document_type or spec.use_case_key,
            department=spec.department_name or spec.department_key,
            filename=doc.filename,
            document_type=doc.document_type,
        )
        logger.info("Extracted '%s' as %s.", doc.filename, doc.document_type)
    except AIServiceUnavailable as exc:
        logger.warning(
            "Extraction halted for %s: AI service temporarily unavailable.",
            doc.filename,
        )
        doc.status = "error"
        doc.error = str(exc)
    except (GeminiExtractionError, AIError, ValueError) as exc:
        logger.exception("Extraction failed for %s.", doc.filename)
        doc.status = "error"
        doc.error = str(exc)


def retry_extract_document(doc: DocumentState) -> bool:
    """Re-run extraction once on the RETRY (stronger) model.

    Reuses the uploaded document and its cached OCR/preprocessing, performing only
    another AI inference. The previous extraction is replaced **only if the retry
    succeeds**; on any failure the previous data is kept intact. Exactly one retry
    is permitted per document.

    Args:
        doc: A processed document to re-extract (updated in place on success).

    Returns:
        True if the retry succeeded and replaced the extraction; False otherwise.
    """
    if doc.processor is None:
        doc.retry_message = "Retry unavailable: no processor is assigned."
        return False
    if doc.retry_used:
        doc.retry_message = "Retry already used for this document."
        return False

    processor = doc.processor
    spec = processor.spec
    retry_model = ai_gateway.retry_model

    # Consume the single retry regardless of outcome (only one attempt allowed).
    doc.retry_used = True
    try:
        parts = _prepared_parts(doc)
        client = processor.build_client()
        started = time.perf_counter()
        raw, ai_scores = client.extract_with_confidence(parts, use_retry_model=True)
        proc_ms = int((time.perf_counter() - started) * 1000)

        model = retry_model
        doc.usage = client.last_usage
        doc.proc_ms = proc_ms
        doc.model_used = model
        cost.record(
            spec.use_case_key,
            spec.department_key,
            model,
            doc.usage,
            model_role=cost.ROLE_RETRY,
            proc_ms=proc_ms,
            is_retry=True,
        )
        _finalize(doc, raw, ai_scores)
        doc.retry_message = f"Re-extracted with {model} (retry)."
        logger.info("Retry succeeded for %s on %s.", doc.filename, model)
        return True
    except (AIServiceUnavailable, GeminiExtractionError, AIError, ValueError) as exc:
        # Never overwrite good data: keep the previous extraction untouched.
        doc.retry_message = f"Retry failed; kept previous extraction. ({exc})"
        logger.warning("Retry failed for %s; previous extraction kept.", doc.filename)
        return False


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
                # Forward each fine-grained extraction stage to the UI so the
                # live pipeline can illuminate (OCR -> AI -> ... -> SAP).
                def _on_stage(name: str, _i: int = index, _doc: DocumentState = doc) -> None:
                    progress_cb(_i + 0.5, total, _doc, name)

                extract_document(doc, on_stage=_on_stage)
            else:
                extract_document(doc)

        if progress_cb:
            progress_cb(index + 1, total, doc, "done")


def build_classifier() -> DocumentClassifier:
    """Construct a classifier backed by the shared AI gateway."""
    return DocumentClassifier(gateway=ai_gateway)
