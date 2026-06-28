"""Purchase Order processor (declarative).

Self-contained processor for the Procurement → Purchase Order document type. It
declares its fields, sections, line items, and classification metadata via a
:class:`~processors.spec.ProcessorSpec`, and provides its own Gemini client,
schema, validation engine, and Excel generator.

It does NOT render its own UI — the generic engine renders confidence, editing,
preview, re-export, and validation uniformly for every processor. The prompts,
schema, validation, and Excel generation are unchanged from earlier versions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from config import gemini_key_manager, settings
from excel import ExcelGenerator
from gemini import GeminiClient
from processors.base import BaseProcessor
from processors.spec import (
    FieldKind,
    FieldSpec,
    LineItemColumn,
    ProcessorSpec,
    SectionSpec,
)
from utils.validators import validate_purchase_order

logger = logging.getLogger(__name__)


_SPEC = ProcessorSpec(
    use_case_key="purchase_order",
    document_type="Purchase Order",
    department_key="procurement",
    keywords=[
        "purchase order",
        "po number",
        "p.o.",
        "buyer",
        "supplier",
        "gst",
        "hsn",
        "payment terms",
    ],
    ai_description=(
        "A Purchase Order issued by a buyer to a supplier listing materials, "
        "quantities, prices, GST, HSN codes, and payment terms."
    ),
    json_suffix="output",
    sections=[
        SectionSpec(
            "Purchase Order",
            [
                FieldSpec("purchase_order.po_number", "PO Number"),
                FieldSpec("purchase_order.po_date", "PO Date"),
                FieldSpec("purchase_order.supplier_reference", "Supplier Reference"),
                FieldSpec("purchase_order.payment_terms", "Payment Terms"),
                FieldSpec("purchase_order.currency", "Currency"),
                FieldSpec("purchase_order.nature_of_supply", "Nature of Supply"),
            ],
        ),
        SectionSpec(
            "Buyer",
            [
                FieldSpec("buyer.company_name", "Buyer Company"),
                FieldSpec("buyer.gst_number", "Buyer GST"),
                FieldSpec("buyer.pan_number", "Buyer PAN"),
                FieldSpec("buyer.address", "Buyer Address", FieldKind.LONG_TEXT),
            ],
        ),
        SectionSpec(
            "Supplier",
            [
                FieldSpec("supplier.company_name", "Supplier Company"),
                FieldSpec("supplier.gst_number", "Supplier GST"),
                FieldSpec("supplier.pan_number", "Supplier PAN"),
                FieldSpec("supplier.address", "Supplier Address", FieldKind.LONG_TEXT),
            ],
        ),
        SectionSpec(
            "Summary",
            [
                FieldSpec("summary.subtotal", "Subtotal", FieldKind.NUMBER),
                FieldSpec("summary.cgst", "CGST", FieldKind.NUMBER),
                FieldSpec("summary.sgst", "SGST", FieldKind.NUMBER),
                FieldSpec("summary.igst", "IGST", FieldKind.NUMBER),
                FieldSpec("summary.grand_total", "Grand Total", FieldKind.NUMBER),
                FieldSpec("summary.amount_in_words", "Amount in Words"),
            ],
        ),
    ],
    line_items_path="items",
    line_item_columns=[
        LineItemColumn("line_number", "Line #"),
        LineItemColumn("material_code", "Material Code"),
        LineItemColumn("description", "Description"),
        LineItemColumn("hsn_code", "HSN Code"),
        LineItemColumn("quantity", "Quantity", FieldKind.NUMBER),
        LineItemColumn("unit", "Unit"),
        LineItemColumn("unit_price", "Unit Price", FieldKind.NUMBER),
        LineItemColumn("taxable_amount", "Taxable Amount", FieldKind.NUMBER),
        LineItemColumn("gst_type", "GST Type"),
        LineItemColumn("gst_percent", "GST %", FieldKind.NUMBER),
        LineItemColumn("gst_amount", "GST Amount", FieldKind.NUMBER),
        LineItemColumn("total_amount", "Total Amount", FieldKind.NUMBER),
    ],
)


class PurchaseOrderProcessor(BaseProcessor):
    """Declarative processor for Purchase Orders."""

    @property
    def spec(self) -> ProcessorSpec:
        """Return the Purchase Order specification."""
        return _SPEC

    def schema_path(self) -> Path:
        """Return the Purchase Order schema path."""
        return settings.schema_path

    def build_client(self) -> GeminiClient:
        """Construct a Gemini client configured for Purchase Orders."""
        return GeminiClient(
            key_manager=gemini_key_manager,
            system_prompt_path=settings.system_prompt_path,
            extraction_prompt_path=settings.extraction_prompt_path,
            schema_path=settings.schema_path,
            model=settings.gemini_model,
        )

    def validate(self, data: dict[str, Any]) -> list[str]:
        """Validate normalized Purchase Order data."""
        return validate_purchase_order(data)

    def build_excel_bytes(self, data: dict[str, Any]) -> bytes:
        """Render the Purchase Order Excel workbook to bytes."""
        return ExcelGenerator().to_bytes(data)
