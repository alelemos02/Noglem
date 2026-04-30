"""Build instrument loops by grouping related instruments."""

import logging
import re
from collections import defaultdict
from typing import Dict, List

from app.services.pid.models.instrument import Instrument, Loop

logger = logging.getLogger(__name__)

# ISA function categories for loop completeness validation
LOOP_ROLES = {
    "sensor": {"E", "TE", "FE", "PE", "LE", "AE"},  # Primary elements
    "transmitter": {"T", "IT", "FT", "PT", "LT", "TT", "AT", "FIT", "PIT", "LIT", "TIT", "AIT"},
    "indicator": {"I", "PI", "TI", "FI", "LI", "AI", "FQI", "PDI"},
    "controller": {"C", "IC", "FC", "PC", "LC", "TC", "AC", "FIC", "PIC", "LIC", "TIC", "AIC"},
    "control_valve": {"V", "CV", "FCV", "PCV", "LCV", "TCV"},
    "switch": {"S", "SH", "SL", "SHH", "SLL", "FS", "PS", "LS", "TS",
               "FSH", "FSL", "PSH", "PSL", "LSH", "LSL", "TSH", "TSL",
               "LSHH", "LSLL", "PSHH", "PSLL", "TSHH", "TSLL"},
    "alarm": {"A", "AH", "AL", "AHH", "ALL", "FAH", "FAL", "PAH", "PAL",
              "LAH", "LAL", "TAH", "TAL", "LAHH", "LALL", "PAHH", "PALL"},
    "relay": {"Y", "FY", "PY", "LY", "TY"},
    "safety": {"SV", "PSV", "PSE", "SDV", "BDV"},
    "recorder": {"R", "FR", "PR", "LR", "TR"},
    "totalizer": {"Q", "FQ", "FQI", "FQIT"},
}

# A basic control loop should have at minimum a transmitter or indicator
MINIMUM_LOOP = {"transmitter", "indicator"}

# Expected combinations for complete control loops
EXPECTED_CONTROL_LOOP = {"transmitter", "controller", "control_valve"}


def build_loops(instruments: List[Instrument]) -> List[Loop]:
    """Group instruments into loops based on shared loop identifiers.

    Loop grouping strategy depends on the tag format:
    - PROMON: group by tag_number (e.g., "0115" groups PIT-0115A, PIC-0115)
    - Technip: group by equipment+suffix (e.g., "W504AC-1" groups FTW504AC-1, FICW504AC-1)

    Args:
        instruments: All detected instruments.

    Returns:
        List of Loop objects.
    """
    # Group by loop identifier
    loop_groups = _group_by_loop_id(instruments)

    loops = []
    for loop_id, inst_list in loop_groups.items():
        if len(inst_list) < 1:
            continue

        # Determine which roles are present in the loop
        roles_present = set()
        for inst in inst_list:
            role = _get_instrument_role(inst.isa_type)
            if role:
                roles_present.add(role)

        # Check loop completeness
        is_complete = bool(roles_present & MINIMUM_LOOP)
        missing = []
        if roles_present & {"transmitter", "controller"}:
            # If we have a transmitter and controller, check for control valve
            expected = EXPECTED_CONTROL_LOOP
            missing_roles = expected - roles_present
            missing = list(missing_roles)
            is_complete = len(missing_roles) == 0

        loop = Loop(
            loop_id=loop_id,
            instruments=[inst.tag for inst in inst_list],
            is_complete=is_complete,
            missing=missing,
        )
        loops.append(loop)

        # Set loop_id on each instrument
        for inst in inst_list:
            inst.loop_id = loop_id

    logger.info(
        f"Built {len(loops)} loops, "
        f"{sum(1 for l in loops if l.is_complete)} complete"
    )

    return loops


def _group_by_loop_id(instruments: List[Instrument]) -> Dict[str, List[Instrument]]:
    """Group instruments by their loop identifier."""
    groups = defaultdict(list)

    for inst in instruments:
        loop_id = _extract_loop_id(inst)
        if loop_id:
            groups[loop_id].append(inst)

    return dict(groups)


def _extract_loop_id(inst: Instrument) -> str:
    """Extract loop identifier from instrument tag.

    PROMON format: "122-PIT-0115A" -> loop_id = "0115"
    Technip format: "FTW504AC-1" -> loop_id = "W504AC-1"
    """
    if inst.tag_number:
        # PROMON: use the base number (strip qualifier)
        # "0115A" -> "0115", "0215" -> "0215"
        base_number = re.sub(r'[A-Z]$', '', inst.tag_number)
        if base_number:
            return base_number

    if inst.equipment_ref:
        # Technip: use equipment + suffix as loop id
        # Extract suffix from tag
        tag = inst.tag
        isa_type = inst.isa_type
        if tag.startswith(isa_type):
            remainder = tag[len(isa_type):]
            return remainder

    # Fallback: use full tag minus ISA type
    tag = inst.tag
    isa_type = inst.isa_type
    if tag.startswith(isa_type):
        return tag[len(isa_type):]

    return ""


def _get_instrument_role(isa_type: str) -> str:
    """Determine the functional role of an instrument based on ISA type.

    Returns the role category (transmitter, controller, etc.) or empty string.
    """
    # Extract the succeeding letters (function part)
    # ISA type like "PIT" -> first letter "P" (pressure), succeeding "IT"
    # We need to match the full type and also just the succeeding letters
    for role, type_set in LOOP_ROLES.items():
        if isa_type in type_set:
            return role

        # Also check just the succeeding letters
        # For "PIT": succeeding = "IT" -> matches "indicator+transmitter"
        if len(isa_type) >= 2:
            succeeding = isa_type[1:]
            if succeeding in type_set:
                return role

    return ""
