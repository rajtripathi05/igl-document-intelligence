"""Shipping Bill processor (declarative).

Self-contained, first-class processor for the Export → Shipping Bill document
type. It declares its fields, sections, line items, and classification metadata
via a :class:`~processors.spec.ProcessorSpec`, and provides its own Gemini
client, schema, validation engine, and Excel generator.

A Shipping Bill is a customs export document with a business schema entirely
different from a Purchase Order. It shares no concrete Purchase Order logic —
only the :class:`~processors.base.BaseProcessor` interface and the generic
``gemini`` / ``utils`` boundaries. The generic engine renders confidence,
editing, preview, re-export, and validation for it automatically.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from config import settings
from excel_shipping_bill import ShippingBillExcelGenerator
from gemini import GeminiClient
from processors.base import BaseProcessor
from processors.spec import (
    FieldKind,
    FieldSpec,
    LineItemColumn,
    ProcessorSpec,
    SectionSpec,
)
from utils.shipping_bill_validators import validate_shipping_bill

logger = logging.getLogger(__name__)


_SPEC = ProcessorSpec(
    use_case_key="shipping_bill",
    document_type="Shipping Bill",
    department_key="export",
    keywords=[
        "shipping bill",
        "customs",
        "port code",
        "iec",
        "fob",
        "leo",
        "exporter",
        "consignee",
        "drawback",
        "let export order",
    ],
    ai_description=(
        "An Export Shipping Bill / customs document declaring goods for export, "
        "including ports, FOB value, HS codes, exporter IEC, consignee, "
        "container details, and customs LEO information."
    ),
    json_suffix="shipping_bill",
    sections=[
        SectionSpec(
            "Shipping Bill",
            [
                FieldSpec("shipping_bill.shipping_bill_number", "Shipping Bill Number"),
                FieldSpec("shipping_bill.shipping_bill_date", "Shipping Bill Date"),
                FieldSpec("shipping_bill.customs_house", "Customs House"),
                FieldSpec("shipping_bill.port_code", "Port Code"),
                FieldSpec("shipping_bill.port_of_loading", "Port of Loading"),
                FieldSpec("shipping_bill.port_of_discharge", "Port of Discharge"),
                FieldSpec(
                    "shipping_bill.country_of_destination", "Country of Destination"
                ),
                FieldSpec("shipping_bill.shipping_scheme", "Shipping Scheme"),
                FieldSpec(
                    "shipping_bill.export_promotion_scheme", "Export Promotion Scheme"
                ),
                FieldSpec("shipping_bill.leo_number", "LEO Number"),
                FieldSpec("shipping_bill.leo_date", "LEO Date"),
            ],
        ),
        SectionSpec(
            "Exporter",
            [
                FieldSpec("exporter.name", "Exporter Name"),
                FieldSpec("exporter.iec_number", "IEC Number"),
                FieldSpec("exporter.gstin", "GSTIN"),
                FieldSpec("exporter.address", "Exporter Address", FieldKind.LONG_TEXT),
            ],
        ),
        SectionSpec(
            "Consignee / Buyer",
            [
                FieldSpec("consignee.name", "Consignee Name"),
                FieldSpec("consignee.country", "Consignee Country"),
                FieldSpec("buyer.name", "Buyer Name"),
                FieldSpec("buyer.country", "Buyer Country"),
            ],
        ),
        SectionSpec(
            "Invoice",
            [
                FieldSpec("invoice.invoice_number", "Invoice Number"),
                FieldSpec("invoice.invoice_date", "Invoice Date"),
                FieldSpec("invoice.invoice_value", "Invoice Value", FieldKind.NUMBER),
                FieldSpec("invoice.fob_value", "FOB Value", FieldKind.NUMBER),
                FieldSpec("invoice.freight", "Freight", FieldKind.NUMBER),
                FieldSpec("invoice.insurance", "Insurance", FieldKind.NUMBER),
                FieldSpec("invoice.currency", "Currency"),
                FieldSpec("invoice.exchange_rate", "Exchange Rate", FieldKind.NUMBER),
            ],
        ),
        SectionSpec(
            "Shipment",
            [
                FieldSpec("shipment.container_number", "Container Number"),
                FieldSpec("shipment.seal_number", "Seal Number"),
                FieldSpec("shipment.vehicle_number", "Vehicle Number"),
                FieldSpec("shipment.total_packages", "Total Packages", FieldKind.NUMBER),
                FieldSpec(
                    "shipment.total_gross_weight", "Total Gross Weight", FieldKind.NUMBER
                ),
                FieldSpec(
                    "shipment.total_net_weight", "Total Net Weight", FieldKind.NUMBER
                ),
            ],
        ),
        SectionSpec(
            "Summary",
            [
                FieldSpec(
                    "summary.total_invoice_value", "Total Invoice Value", FieldKind.NUMBER
                ),
                FieldSpec("summary.total_fob_value", "Total FOB Value", FieldKind.NUMBER),
                FieldSpec("summary.total_freight", "Total Freight", FieldKind.NUMBER),
                FieldSpec("summary.total_insurance", "Total Insurance", FieldKind.NUMBER),
                FieldSpec("summary.currency", "Currency"),
            ],
        ),
    ],
    line_items_path="items",
    line_item_columns=[
        LineItemColumn("line_number", "Line #"),
        LineItemColumn("product_description", "Product Description"),
        LineItemColumn("hs_code", "HS Code"),
        LineItemColumn("quantity", "Quantity", FieldKind.NUMBER),
        LineItemColumn("unit", "Unit (UQC)"),
        LineItemColumn("unit_price", "Unit Price", FieldKind.NUMBER),
        LineItemColumn("fob_value", "FOB Value", FieldKind.NUMBER),
        LineItemColumn("gross_weight", "Gross Weight", FieldKind.NUMBER),
        LineItemColumn("net_weight", "Net Weight", FieldKind.NUMBER),
        LineItemColumn("number_of_packages", "Packages", FieldKind.NUMBER),
    ],
)


class ShippingBillProcessor(BaseProcessor):
    """Declarative processor for Export Shipping Bills."""

    @property
    def spec(self) -> ProcessorSpec:
        """Return the Shipping Bill specification."""
        return _SPEC

    def schema_path(self) -> Path:
        """Return the Shipping Bill schema path."""
        return settings.shipping_bill_schema_path

    def build_client(self) -> GeminiClient:
        """Construct a Gemini client configured for Shipping Bills."""
        return GeminiClient(
            api_key=settings.gemini_api_key,
            system_prompt_path=settings.shipping_bill_system_prompt_path,
            extraction_prompt_path=settings.shipping_bill_extraction_prompt_path,
            schema_path=settings.shipping_bill_schema_path,
            model=settings.gemini_model,
        )

    def validate(self, data: dict[str, Any]) -> list[str]:
        """Validate normalized Shipping Bill data."""
        return validate_shipping_bill(data)

    def build_excel_bytes(self, data: dict[str, Any]) -> bytes:
        """Render the Shipping Bill Excel workbook to bytes."""
        return ShippingBillExcelGenerator().to_bytes(data)
