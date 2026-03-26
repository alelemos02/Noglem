"""Detect physical vs DCS instruments based on vectorial graphics/symbology."""

import logging
from typing import List, Tuple

from app.services.pid.models.instrument import Instrument

logger = logging.getLogger(__name__)


def classify_instruments(instruments: List[Instrument], edges: list) -> None:
    """Classify instruments based on the graphic elements around them (edges).

    Modifies instruments in place by setting symbol, is_physical and classification.
    """
    if not instruments:
        return

    classified_dcs = 0
    classified_room = 0

    for inst in instruments:
        if not inst.position:
            continue

        cx = inst.position.center_x
        cy = inst.position.center_y

        # Filter edges near this instrument (e.g., within 40px radius)
        nearby_edges = []
        for e in edges:
            x0, top = float(e.get("x0", 0)), float(e.get("top", 0))
            x1, bot = float(e.get("x1", 0)), float(e.get("bottom", 0))
            if (x0 - 45) < cx < (x1 + 45) and (top - 45) < cy < (bot + 45):
                nearby_edges.append(e)

        # Check for Horizontal line intersecting center
        has_hline = False
        for e in nearby_edges:
            w, h = float(e.get("width", 0)), float(e.get("height", 0))
            x0, y0 = float(e.get("x0", 0)), float(e.get("top", 0))
            x1 = float(e.get("x1", 0))
            # It's a horizontal line if height is very small
            if h < 2 and w > 5:
                # Does it intersect the center horizontally?
                if abs(y0 - cy) < 15 and x0 < cx < x1:
                    has_hline = True
                    break

        # Check for Box (lines above, below, left, right)
        has_top = has_bot = has_left = has_right = False
        for e in nearby_edges:
            w, h = float(e.get("width", 0)), float(e.get("height", 0))
            x0, y0 = float(e.get("x0", 0)), float(e.get("top", 0))
            x1, y1 = float(e.get("x1", 0)), float(e.get("bottom", 0))

            # Horizontal strokes (top/bottom)
            if h < 2 and w > 5:
                if 8 < (cy - y0) < 35 and (x0 - 15) < cx < (x1 + 15):
                    has_top = True
                elif 8 < (y0 - cy) < 35 and (x0 - 15) < cx < (x1 + 15):
                    has_bot = True

            # Vertical strokes (left/right)
            if w < 2 and h > 5:
                if 8 < (cx - x0) < 35 and (y0 - 15) < cy < (y1 + 15):
                    has_left = True
                elif 8 < (x0 - cx) < 35 and (y0 - 15) < cy < (y1 + 15):
                    has_right = True

        in_square = (has_top and has_bot and has_left and has_right)

        if in_square:
            inst.symbol = "square"
            inst.classification = "DCS/Supervisório"
            inst.is_physical = False
            classified_dcs += 1
        elif has_hline:
            inst.symbol = "hline"
            inst.classification = "Sala de Controle"
            inst.is_physical = False
            classified_room += 1
        else:
            inst.symbol = "circle"
            inst.classification = "Instrumento de Campo"
            inst.is_physical = True

    logger.debug(
        f"Symbology: {classified_dcs} DCS, {classified_room} Control Room, "
        f"{len(instruments) - classified_dcs - classified_room} Field"
    )
