"""Spatial engine: associate instruments with equipment using geometric proximity."""

import logging
import re
from typing import Dict, List, Optional, Tuple

from app.services.pid.models.instrument import Equipment, ExtractedWord, Instrument, Position

logger = logging.getLogger(__name__)

# Common equipment tag patterns
EQUIPMENT_PATTERNS = [
    # Technip: W503AC, W504AC1, W521B, W524-1
    re.compile(r'\b(W\d{3}[A-Z]*\d*(?:-\d+)?)\b'),
    # PROMON: 122-VE01AB, 222-TQ01, 122-BA01
    re.compile(r'\b(\d{3}-[A-Z]{2}\d{2}[A-Z]{0,2})\b'),
    # Generic equipment: TK-101, V-201, P-301A
    re.compile(r'\b([A-Z]{1,3}-\d{3}[A-Z]?)\b'),
]

# Words that indicate equipment (not instruments)
EQUIPMENT_KEYWORDS = [
    "TANK", "TANQUE", "VESSEL", "VASO", "PUMP", "BOMBA",
    "COMPRESSOR", "HEAT", "EXCHANGER", "TROCADOR", "REACTOR",
    "REATOR", "COLUMN", "COLUNA", "TOWER", "TORRE", "FILTER",
    "FILTRO", "SEPARATOR", "SEPARADOR", "DRUM", "TAMBOR",
    "MIXER", "MISTURADOR", "AGITATOR", "AGITADOR",
]


def detect_equipment(
    words: List[ExtractedWord],
    instruments: List[Instrument],
) -> List[Equipment]:
    """Detect equipment tags in extracted words.

    Equipment tags are identified by:
    1. Matching known equipment patterns
    2. Not being instrument tags (already detected)
    3. Being near equipment keywords

    Args:
        words: All extracted words.
        instruments: Already detected instruments (to exclude).

    Returns:
        List of Equipment objects.
    """
    instrument_tags = {inst.tag for inst in instruments}
    equipment_map: Dict[str, Equipment] = {}

    for word in words:
        text = word.text.strip()
        if not text or text in instrument_tags:
            continue

        for pattern in EQUIPMENT_PATTERNS:
            match = pattern.search(text)
            if match:
                equip_tag = match.group(1)

                # Skip if it looks like an instrument tag
                if _looks_like_instrument(equip_tag):
                    continue

                if equip_tag not in equipment_map:
                    equipment_map[equip_tag] = Equipment(
                        tag=equip_tag,
                        position=word.position,
                        page_index=word.page_index,
                    )

                    # Look for description nearby
                    desc = _find_equipment_description(
                        word, words
                    )
                    if desc:
                        equipment_map[equip_tag].description = desc

    equipment = list(equipment_map.values())
    logger.info(f"Detected {len(equipment)} equipment tags")
    return equipment


def associate_instruments_to_equipment(
    instruments: List[Instrument],
    equipment: List[Equipment],
    max_distance: float = 200.0,
) -> None:
    """Associate each instrument to its nearest equipment using spatial proximity.

    Modifies instruments in place by setting equipment_ref.

    Args:
        instruments: Detected instruments.
        equipment: Detected equipment.
        max_distance: Maximum distance to associate.
    """
    if not equipment:
        logger.warning("No equipment detected, skipping association")
        return

    for inst in instruments:
        if not inst.position:
            continue

        # Skip if equipment already set (e.g., from tag parsing)
        if inst.equipment_ref:
            continue

        # Find nearest equipment on same page
        nearest = None
        nearest_dist = float("inf")

        for equip in equipment:
            if equip.page_index != inst.page_index:
                continue
            if not equip.position:
                continue

            dist = inst.position.distance_to(equip.position)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = equip

        if nearest and nearest_dist <= max_distance:
            inst.equipment_ref = nearest.tag
            nearest.associated_instruments.append(inst.tag)
            logger.debug(
                f"Associated {inst.tag} -> {nearest.tag} "
                f"(distance={nearest_dist:.1f})"
            )
        else:
            logger.debug(
                f"No equipment found for {inst.tag} "
                f"within {max_distance} units"
            )

    # Report associations
    associated = sum(1 for i in instruments if i.equipment_ref)
    logger.info(
        f"Associated {associated}/{len(instruments)} instruments to equipment"
    )


def _looks_like_instrument(tag: str) -> bool:
    """Check if a tag looks like an instrument rather than equipment."""
    from models.instrument import ISA_TYPE_DESCRIPTIONS

    for isa_type in ISA_TYPE_DESCRIPTIONS:
        if tag.startswith(isa_type) and len(tag) > len(isa_type):
            return True
    return False


def _find_equipment_description(
    equip_word: ExtractedWord,
    all_words: List[ExtractedWord],
    search_radius: float = 100.0,
) -> str:
    """Find a description near an equipment tag.

    Looks for equipment keywords near the tag position.
    """
    if not equip_word.position:
        return ""

    nearby_words = []
    for w in all_words:
        if w.page_index != equip_word.page_index:
            continue
        if w is equip_word:
            continue
        if not w.position:
            continue

        dist = equip_word.position.distance_to(w.position)
        if dist <= search_radius:
            text_upper = w.text.upper()
            if any(kw in text_upper for kw in EQUIPMENT_KEYWORDS):
                nearby_words.append(w.text)

    return " ".join(nearby_words) if nearby_words else ""
