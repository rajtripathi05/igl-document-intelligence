"""Department catalog for the Enterprise Document Intelligence Platform.

The catalog defines the company's departments and their navigation order/icons.
It deliberately holds **no processor list** — business processes are discovered
from processor manifests (``processors/<key>/manifest.json``) and grouped by
``department.key`` at runtime via the registry. This keeps the platform scalable:
adding a process is adding a processor folder, never editing this file.

Departments with no processors yet still appear in navigation and render an
empty "coming soon" state.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Department:
    """A company department shown in navigation.

    Attributes:
        key: Stable identifier used to group processors.
        name: Human-readable department name.
        icon: Emoji/icon shown beside the name.
        order: Sort order in navigation (lower first).
    """

    key: str
    name: str
    icon: str = "🏢"
    order: int = 100


#: The eleven India Glycols departments, in navigation order. Three have live
#: processors today (Store→IGP, Marketing→Sales Order, Export→Shipping Bill);
#: the rest surface their declared business processes as "coming soon".
DEPARTMENTS: list[Department] = [
    Department("store", "Store", "📦", 1),
    Department("marketing", "Marketing", "📣", 2),
    Department("finance", "Finance", "💰", 3),
    Department("export", "Export", "🚢", 4),
    Department("supply_chain", "Supply Chain", "🚚", 5),
    Department("hr", "Human Resources", "👥", 6),
    Department("operations", "Operations", "⚙️", 7),
    Department("mechanical", "Mechanical", "🔧", 8),
    Department("chemical", "Chemical", "🧪", 9),
    Department("production", "Production", "🏭", 10),
    Department("management", "Management", "📊", 11),
]


def get_department(key: str) -> Department | None:
    """Return the department with the given key, or None if not found."""
    return next((d for d in DEPARTMENTS if d.key == key), None)


def department_name(key: str) -> str:
    """Return a display name for a department key (falls back to the key)."""
    dept = get_department(key)
    return dept.name if dept else key.replace("_", " ").title()
