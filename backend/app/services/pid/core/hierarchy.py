"""Build parent-child hierarchy between instruments."""

import logging
from typing import Dict, List, Set

from app.services.pid.models.instrument import Instrument

logger = logging.getLogger(__name__)

# Parent-child relationship rules
# Key = parent ISA type prefix, Value = set of child ISA type prefixes
HIERARCHY_RULES = {
    # On-off valve -> limit switches
    "XV": {"ZSO", "ZSC", "ZOI", "ZCI", "ZSH", "ZSL", "ZT", "ZI"},
    "SDV": {"ZSO", "ZSC", "ZOI", "ZCI", "ZSH", "ZSL", "ZT", "ZI"},
    "BDV": {"ZSO", "ZSC", "ZOI", "ZCI", "ZSH", "ZSL", "ZT", "ZI"},
    "HV": {"ZSO", "ZSC", "ZOI", "ZCI"},
    # Motor -> motor accessories
    "MW": {"XCM", "HCM", "ITM", "IIM", "YAM", "RIM"},
    # Pump -> motor
    "PW": {"MW"},
    # Control valve -> positioner, I/P converter
    "FCV": {"ZT", "ZI", "FY"},
    "PCV": {"ZT", "ZI", "PY"},
    "LCV": {"ZT", "ZI", "LY"},
    "TCV": {"ZT", "ZI", "TY"},
}

# Maximum distance between parent and child for association
MAX_HIERARCHY_DISTANCE = 150.0


def build_hierarchy(instruments: List[Instrument]) -> None:
    """Establish parent-child relationships between instruments.

    Uses two strategies:
    1. Tag matching: child tag contains parent's equipment reference
    2. Spatial proximity: child is geometrically close to parent

    Modifies instruments in place.

    Args:
        instruments: All detected instruments.
    """
    # Index instruments by ISA type for quick lookup
    by_type: Dict[str, List[Instrument]] = {}
    for inst in instruments:
        t = inst.isa_type
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(inst)

    total_links = 0

    for parent_type, child_types in HIERARCHY_RULES.items():
        parents = by_type.get(parent_type, [])
        if not parents:
            continue

        for child_type in child_types:
            children = by_type.get(child_type, [])
            if not children:
                continue

            for parent in parents:
                for child in children:
                    if _should_link(parent, child):
                        child.parent_tag = parent.tag
                        if child.tag not in parent.children_tags:
                            parent.children_tags.append(child.tag)
                        total_links += 1
                        logger.debug(
                            f"Hierarchy: {parent.tag} -> {child.tag}"
                        )

    logger.info(f"Built {total_links} parent-child links")


def _should_link(parent: Instrument, child: Instrument) -> bool:
    """Determine if a child should be linked to a parent.

    Criteria:
    1. Same page
    2. Shared equipment reference OR similar tag pattern
    3. Within spatial proximity
    """
    # Must be on the same page
    if parent.page_index != child.page_index:
        return False

    # Already linked to another parent
    if child.parent_tag:
        return False

    # Strategy 1: shared equipment reference
    if parent.equipment_ref and child.equipment_ref:
        if parent.equipment_ref == child.equipment_ref:
            return True

    # Strategy 2: tag pattern matching
    # For Technip: XV-W503AC-FH -> ZSO-XV-W503AC-FH-1
    # The child tag should contain part of the parent tag
    parent_base = _extract_tag_base(parent)
    child_base = _extract_tag_base(child)
    if parent_base and child_base and parent_base in child.tag:
        return True

    # Strategy 3: spatial proximity (fallback)
    if parent.position and child.position:
        dist = parent.position.distance_to(child.position)
        if dist <= MAX_HIERARCHY_DISTANCE:
            # Additional check: child ISA type should be a valid child of parent
            return True

    return False


def _extract_tag_base(inst: Instrument) -> str:
    """Extract the base identifier from a tag (without ISA prefix).

    "FTW504AC-1" -> "W504AC-1"
    "122-PIT-0115A" -> "0115"
    """
    tag = inst.tag
    isa_type = inst.isa_type

    # Remove ISA prefix
    if tag.startswith(isa_type):
        return tag[len(isa_type):]

    # PROMON format: area-type-number
    if "-" in tag:
        parts = tag.split("-")
        if len(parts) >= 3:
            return parts[-1]  # Return the number part

    return ""
