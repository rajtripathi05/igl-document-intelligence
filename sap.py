"""SAP-readiness assessment.

After extraction, every document is scored for how ready it is to post to SAP.
The score reflects whether the SAP-critical business fields are present and
confidently read (GST, PO/Order number, HS/HSN code, invoice date, etc.).

Which fields count as critical is driven by the processor, not hardcoded per
document type — preserving the plugin architecture:

1. The manifest's optional ``sap.required`` block (``spec.sap_required``), else
2. the ``required`` fields declared in the manifest ``sections``, else
3. a keyword-matched set of common SAP-critical fields from the spec, else
4. every scalar field in the spec (last-resort fallback).

Status bands mirror the confidence palette: Green ≥95 "Ready for SAP",
Yellow 75–94 "Needs Review", Red <75 "Not Ready".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from processors.spec import FieldSpec, ProcessorSpec, get_path
from utils.confidence import HIGH_MIN, REVIEW_MIN, band, field_score

#: Readiness status codes.
READY = "ready"
REVIEW = "review"
NOT_READY = "error"

#: Human labels per status.
_STATUS_LABELS = {
    READY: "Ready for SAP",
    REVIEW: "Needs Review",
    NOT_READY: "Not Ready",
}

#: Path/label substrings used to auto-detect SAP-critical fields when a processor
#: declares no required/SAP fields (lower-cased match on path or label).
_CRITICAL_MARKERS = (
    "gst",
    "gstin",
    "pan",
    "po_number",
    "order_number",
    "po number",
    "order number",
    "invoice_number",
    "invoice number",
    "invoice_date",
    "invoice date",
    "hs_code",
    "hsn",
    "hs code",
    "iec",
    "shipping_bill_number",
    "grand_total",
    "total",
    "currency",
    "date",
)


@dataclass(frozen=True)
class SapReadiness:
    """Outcome of a SAP-readiness assessment for one document."""

    score: int
    status: str
    label: str
    reasons: list[str] = field(default_factory=list)
    present: int = 0
    total: int = 0
    fields: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_ready(self) -> bool:
        """True when the document is ready to post to SAP."""
        return self.status == READY


def _is_present(value: Any) -> bool:
    """True when a field carries a usable value (0 and False count as present)."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def _critical_fields(spec: ProcessorSpec) -> list[FieldSpec]:
    """Resolve the SAP-critical fields for a processor (see module docstring)."""
    if spec.sap_required:
        return list(spec.sap_required)

    section_fields = [f for section in spec.sections for f in section.fields]
    required = [f for f in section_fields if f.required]
    if required:
        return required

    keyword_matched = [
        f
        for f in section_fields
        if any(m in f.path.lower() or m in f.label.lower() for m in _CRITICAL_MARKERS)
    ]
    if keyword_matched:
        return keyword_matched

    return section_fields


def _status_for(score: int) -> str:
    """Map a readiness score to a status code using the confidence bands."""
    if score >= HIGH_MIN:
        return READY
    if score >= REVIEW_MIN:
        return REVIEW
    return NOT_READY


def assess(doc: Any, spec: ProcessorSpec) -> SapReadiness:
    """Assess how ready a processed document is to post to SAP.

    Args:
        doc: A processed ``DocumentState`` (uses ``doc.data`` and ``doc.confidence``).
        spec: The processor spec that produced the document.

    Returns:
        A :class:`SapReadiness` with score, status, reasons, and per-field detail.
    """
    data = doc.data or {}
    confidence = getattr(doc, "confidence", {}) or {}
    critical = _critical_fields(spec)

    if not critical:
        # Nothing to assess against; treat as needing review rather than failing.
        return SapReadiness(
            score=0, status=NOT_READY, label=_STATUS_LABELS[NOT_READY],
            reasons=["No SAP-critical fields are defined for this processor."],
            present=0, total=0, fields=[],
        )

    weights: list[float] = []
    reasons: list[str] = []
    details: list[dict[str, Any]] = []
    present_count = 0

    for fspec in critical:
        value = get_path(data, fspec.path)
        present = _is_present(value)
        conf = field_score(confidence, fspec.path, default=90) if present else 0
        if present:
            present_count += 1
            weight = min(conf, 100) / 100.0
            if conf < REVIEW_MIN:
                reasons.append(f"{fspec.label} low confidence")
        else:
            weight = 0.0
            reasons.append(f"{fspec.label} missing")
        weights.append(weight)
        details.append(
            {
                "label": fspec.label,
                "path": fspec.path,
                "present": present,
                "confidence": conf,
                "band": band(conf) if present else "verify",
            }
        )

    score = round(100 * sum(weights) / len(weights))
    status = _status_for(score)
    return SapReadiness(
        score=score,
        status=status,
        label=_STATUS_LABELS[status],
        reasons=reasons[:8],
        present=present_count,
        total=len(critical),
        fields=details,
    )
