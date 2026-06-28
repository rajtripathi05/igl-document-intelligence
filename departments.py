"""Department and document use-case registry.

This registry decouples the UI from the set of departments and their document
use cases. Adding a new department or a new use case is a data change here, not
a UI rewrite — this keeps the platform scalable across the company (see the
Future Roadmap in CLAUDE.md).

Only use cases marked ``active`` are wired to a working processor. Everything
else renders a professional "coming soon" placeholder.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class UseCase:
    """A document processing use case within a department.

    Attributes:
        key: Stable identifier used internally for routing.
        name: Full human-readable name shown in the UI.
        active: Whether a working processor exists for this use case.
        description: Short description shown to the user.
    """

    key: str
    name: str
    active: bool = False
    description: str = ""


@dataclass(frozen=True)
class Department:
    """A company department and its available document use cases.

    Attributes:
        key: Stable identifier.
        name: Full human-readable department name.
        icon: Emoji/icon shown beside the department name.
        use_cases: Ordered list of use cases for this department.
    """

    key: str
    name: str
    icon: str = "🏢"
    use_cases: list[UseCase] = field(default_factory=list)

    @property
    def active(self) -> bool:
        """True if the department has at least one active use case."""
        return any(uc.active for uc in self.use_cases)


# The Purchase Order processor is the single working use case in Version 1.
# It is exposed under Procurement (primary) and Marketing (as requested).
_PURCHASE_ORDER = UseCase(
    key="purchase_order",
    name="Purchase Order",
    active=True,
    description=(
        "Upload a Purchase Order (PDF or image), extract standardized "
        "ERP-ready data with Google Gemini, review it, and export JSON and Excel."
    ),
)


DEPARTMENTS: list[Department] = [
    Department(
        key="procurement",
        name="Procurement",
        icon="📦",
        use_cases=[_PURCHASE_ORDER],
    ),
    Department(
        key="marketing",
        name="Marketing",
        icon="📣",
        use_cases=[_PURCHASE_ORDER],
    ),
    Department(
        key="sales",
        name="Sales",
        icon="🤝",
        use_cases=[
            UseCase("sales_order", "Sales Order"),
            UseCase("quotation", "Quotation"),
        ],
    ),
    Department(
        key="finance",
        name="Finance / Accounts",
        icon="💰",
        use_cases=[
            UseCase("gst_invoice", "GST Invoice"),
            UseCase("credit_note", "Credit Note"),
        ],
    ),
    Department(
        key="hr",
        name="Human Resources",
        icon="👥",
        use_cases=[UseCase("hr_document", "HR Document")],
    ),
    Department(
        key="operations",
        name="Operations",
        icon="⚙️",
        use_cases=[UseCase("delivery_challan", "Delivery Challan")],
    ),
    Department(
        key="mechanical",
        name="Mechanical",
        icon="🔧",
        use_cases=[UseCase("work_order", "Work Order")],
    ),
    Department(
        key="chemical",
        name="Chemical",
        icon="🧪",
        use_cases=[UseCase("material_safety_sheet", "Material Safety Data Sheet")],
    ),
    # Export is fully independent from Procurement. None of its document types
    # share the Purchase Order schema or processor. Each will later get its own
    # prompts, schema, validation, Excel template, SAP mapping, and processor.
    # Shipping Bill is listed first as the reference for the next implementation.
    Department(
        key="export",
        name="Export",
        icon="🚢",
        use_cases=[
            UseCase(
                "shipping_bill",
                "Shipping Bill",
                active=True,
                description=(
                    "Upload an Export Shipping Bill (PDF or image), extract "
                    "customs-ready data with Google Gemini, review it, and "
                    "export JSON and Excel."
                ),
            ),
            UseCase("commercial_invoice", "Commercial Invoice"),
            UseCase("packing_list", "Packing List"),
            UseCase("bill_of_lading", "Bill of Lading"),
            UseCase("certificate_of_origin", "Certificate of Origin"),
            UseCase("export_invoice", "Export Invoice"),
            UseCase("export_declaration", "Export Declaration"),
            UseCase("customs_documents", "Customs Documents"),
        ],
    ),
]


def get_department(key: str) -> Department | None:
    """Return the department with the given key, or None if not found."""
    return next((d for d in DEPARTMENTS if d.key == key), None)
