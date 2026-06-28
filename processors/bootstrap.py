"""Processor bootstrap: register all available document processors.

This is the single place where concrete processors are wired into the registry.
Importing this module activates every implemented document type.

When the Shipping Bill processor is implemented, enabling it requires ONLY:

    from processors.shipping_bill import ShippingBillProcessor
    register_processor(ShippingBillProcessor())

No existing processor or routing code needs to change.
"""

from __future__ import annotations

from processors.purchase_order import PurchaseOrderProcessor
from processors.registry import register_processor
from processors.shipping_bill import ShippingBillProcessor

_BOOTSTRAPPED = False


def bootstrap_processors() -> None:
    """Register all implemented processors exactly once."""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    register_processor(PurchaseOrderProcessor())
    register_processor(ShippingBillProcessor())
    _BOOTSTRAPPED = True
