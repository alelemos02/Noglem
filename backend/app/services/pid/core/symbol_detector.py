"""Detect physical vs DCS instruments based on vectorial graphics/symbology.

Classification uses actual rectangles and lines from pdfplumber, NOT raw edges.
This avoids false positives from process piping / CAD elements being mistaken
for DCS squares around instrument balloons.

Rules:
  - Simple circle (no square, no horizontal line) → FIELD instrument (physical)
  - Circle inside a square rectangle → DCS/Supervisory signal
  - Circle with horizontal line through center → Control Room / shared

All pixel thresholds are BASE values calibrated for A3 landscape (841×595 pts).
They are automatically scaled via DocumentScale when provided.
"""

import logging
import re
from typing import List, Optional, Tuple

from app.services.pid.models.instrument import Instrument
from app.services.pid.core.document_scale import DocumentScale, _s

logger = logging.getLogger(__name__)


def _prefilter_edges(edges: list) -> Tuple[list, list]:
    """Split raw edges into short horizontal and vertical segments for square detection."""
    h_edges, v_edges = [], []
    for e in edges:
        try:
            x0  = float(e['x0'])
            top = float(e['top'])
            x1  = float(e['x1'])
            bot = float(e['bottom'])
        except (KeyError, TypeError, ValueError):
            continue
        w = abs(x1 - x0)
        h = abs(bot - top)
        if h < 1.5 and 5 < w < 120:
            h_edges.append((x0, (top + bot) / 2, x1))
        elif w < 1.5 and 5 < h < 120:
            v_edges.append(((x0 + x1) / 2, top, bot))
    return h_edges, v_edges


def _instrument_in_square(cx: float, cy: float, inst_h: float,
                           h_edges: list, v_edges: list) -> bool:
    """Return True if (cx, cy) is enclosed in a square formed by edge segments."""
    min_d = max(inst_h * 0.6, 4.0)
    max_d = max(inst_h * 2.5, 20.0)

    near_h = [(ex0, ey, ex1) for ex0, ey, ex1 in h_edges
              if abs((ex0 + ex1) / 2 - cx) < max_d * 2]
    near_v = [(ex, ey0, ey1) for ex, ey0, ey1 in v_edges
              if abs((ey0 + ey1) / 2 - cy) < max_d * 2]

    h_above = [ey for _, ey, _ in near_h if min_d < cy - ey < max_d]
    h_below = [ey for _, ey, _ in near_h if min_d < ey - cy < max_d]
    v_left  = [ex for ex, _, _ in near_v if min_d < cx - ex < max_d]
    v_right = [ex for ex, _, _ in near_v if min_d < ex - cx < max_d]

    if not (h_above and h_below and v_left and v_right):
        return False

    top_y   = max(h_above)
    bot_y   = min(h_below)
    left_x  = max(v_left)
    right_x = min(v_right)

    height = bot_y - top_y
    width  = right_x - left_x
    if height <= 0 or width <= 0:
        return False
    aspect = width / height

    top_segs   = [(ex0, ey, ex1) for ex0, ey, ex1 in near_h if abs(ey - top_y) < 1.0]
    bot_segs   = [(ex0, ey, ex1) for ex0, ey, ex1 in near_h if abs(ey - bot_y) < 1.0]
    left_segs  = [(ex, ey0, ey1) for ex, ey0, ey1 in near_v if abs(ex - left_x) < 1.0]
    right_segs = [(ex, ey0, ey1) for ex, ey0, ey1 in near_v if abs(ex - right_x) < 1.0]

    top_span   = (max(e[2] for e in top_segs)   - min(e[0] for e in top_segs))   if top_segs   else 0
    bot_span   = (max(e[2] for e in bot_segs)   - min(e[0] for e in bot_segs))   if bot_segs   else 0
    left_span  = (max(e[2] for e in left_segs)  - min(e[1] for e in left_segs))  if left_segs  else 0
    right_span = (max(e[2] for e in right_segs) - min(e[1] for e in right_segs)) if right_segs else 0

    min_coverage = 0.50
    coverage_ok = (top_span   >= width  * min_coverage and
                   bot_span   >= width  * min_coverage and
                   left_span  >= height * min_coverage and
                   right_span >= height * min_coverage)

    return 0.75 < aspect < 1.35 and coverage_ok


def _classify_by_isa_type(isa_type: str) -> Optional[str]:
    """Classify instrument using ISA 5.1 last-letter convention.

    Returns 'FIELD', 'DCS', or None (ambiguous → fall through to geometry).
    """
    if not isa_type:
        return None
    last = isa_type.upper()[-1]
    if last in ('T', 'E', 'V', 'W', 'G', 'O'):
        return 'FIELD'
    if last == 'C':
        return 'DCS'
    return None


def classify_instruments(
    instruments: List[Instrument],
    edges: list,
    page_rects: list = None,
    page_lines: list = None,
    scale: Optional[DocumentScale] = None,
    profile: Optional[dict] = None,
) -> None:
    """Classify instruments based on the graphic elements around them.

    Uses REAL rectangles (page.rects) and lines (page.lines) from pdfplumber
    rather than raw edges, to avoid false positives from process piping.

    If page_rects/page_lines are not provided, falls back to edge-based
    detection but with much tighter constraints.

    Modifies instruments in place by setting symbol, is_physical and classification.
    """
    if not instruments:
        return

    if page_rects is not None and page_lines is not None:
        _classify_with_rects_and_lines(instruments, page_rects, page_lines, scale, profile,
                                       fallback_edges=edges)
    else:
        _classify_with_edges_strict(instruments, edges, scale, profile)


def _classify_with_rects_and_lines(
    instruments: List[Instrument],
    rects: list,
    lines: list,
    scale: Optional[DocumentScale] = None,
    profile: Optional[dict] = None,
    fallback_edges: list = None,
) -> None:
    """Classify using actual rectangle and line objects from pdfplumber."""
    sym_cfg   = (profile or {}).get("symbols", {})
    hline_min = _s(scale, sym_cfg.get("hline_min", 28.0))
    hline_max = _s(scale, sym_cfg.get("hline_max", 45.0))

    dcs_squares = []
    for r in rects:
        try:
            x0  = float(r.get("x0", 0))
            top = float(r.get("top", 0))
            x1  = float(r.get("x1", 0))
            bot = float(r.get("bottom", 0))
        except (TypeError, ValueError):
            continue
        w = x1 - x0
        h = bot - top
        if w > 0.5 and h > 0.5 and 0.7 < w / h < 1.4:
            dcs_squares.append((x0, top, x1, bot))

    use_edge_squares = len(dcs_squares) == 0 and fallback_edges
    h_edges_pre: list = []
    v_edges_pre: list = []
    if use_edge_squares:
        h_edges_pre, v_edges_pre = _prefilter_edges(fallback_edges)
        logger.debug(f"DCS square fallback: {len(h_edges_pre)} h-edges, {len(v_edges_pre)} v-edges")

    balloon_hlines = []
    for l in lines:
        try:
            x0 = float(l.get("x0", 0))
            y0 = float(l.get("top", 0))
            x1 = float(l.get("x1", 0))
            y1 = float(l.get("bottom", 0))
        except (TypeError, ValueError):
            continue
        if abs(y0 - y1) < _s(scale, 2.0):
            length = abs(x1 - x0)
            if hline_min < length < hline_max:
                cx = (x0 + x1) / 2
                balloon_hlines.append((cx, y0, length))

    classified_dcs = 0
    classified_room = 0

    for inst in instruments:
        if not inst.position:
            continue

        isa_class = _classify_by_isa_type(inst.isa_type)
        if isa_class == 'FIELD':
            inst.symbol = "circle"
            inst.classification = "Instrumento de Campo"
            inst.is_physical = True
            continue
        if isa_class == 'DCS':
            inst.symbol = "square"
            inst.classification = "DCS/Supervisório"
            inst.is_physical = False
            classified_dcs += 1
            continue

        cx = inst.position.center_x
        cy = inst.position.center_y
        inst_h = max(inst.position.bottom - inst.position.top, 4.0)

        if dcs_squares:
            in_square = _is_inside_square(cx, cy, dcs_squares, scale, inst_h=inst_h)
        elif use_edge_squares:
            in_square = _instrument_in_square(cx, cy, inst_h, h_edges_pre, v_edges_pre)
        else:
            in_square = False

        has_hline = _has_horizontal_line(cx, cy, balloon_hlines, scale, inst_h=inst_h)

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

    _penalize_diamond_instruments(instruments, fallback_edges or [], profile=profile)

    logger.info(
        f"Symbology (rects+lines): {classified_dcs} DCS, {classified_room} Control Room, "
        f"{len(instruments) - classified_dcs - classified_room} Field"
    )


def _is_inside_square(
    cx: float,
    cy: float,
    squares: list,
    scale: Optional[DocumentScale] = None,
    inst_h: float = 0.0,
) -> bool:
    """Check if instrument center is inside a DCS square."""
    if inst_h > 0:
        min_side = inst_h * 0.8
        max_side = inst_h * 10.0
        margin   = inst_h * 0.5
    else:
        min_side = _s(scale, 4.0)
        max_side = _s(scale, 100.0)
        margin   = _s(scale, 10.0)

    for sx0, stop, sx1, sbot in squares:
        w = sx1 - sx0
        h = sbot - stop
        if w <= 0 or h <= 0:
            continue
        if not (min_side < w < max_side and min_side < h < max_side):
            continue
        if (sx0 - margin) <= cx <= (sx1 + margin) and (stop - margin) <= cy <= (sbot + margin):
            return True
    return False


def _has_horizontal_line(
    cx: float,
    cy: float,
    hlines: list,
    scale: Optional[DocumentScale] = None,
    inst_h: float = 0.0,
) -> bool:
    """Check if a horizontal line passes through the center of the balloon."""
    tolerance_y = max(inst_h * 1.5, _s(scale, 8.0)) if inst_h > 0 else _s(scale, 20.0)
    for lx, ly, length in hlines:
        if abs(lx - cx) < length / 2 and abs(ly - cy) < tolerance_y:
            return True
    return False


def _penalize_diamond_instruments(
    instruments: List[Instrument],
    edges: list,
    profile: Optional[dict] = None,
) -> None:
    """Set confidence to 0.1 for instruments whose ISA type is listed as a SIS/SIL element."""
    sil_types = set(t.upper() for t in (profile or {}).get("sil_isa_types", []))
    if not sil_types:
        return

    for inst in instruments:
        if inst.isa_type.upper() in sil_types:
            old = inst.confidence
            inst.confidence = 0.1
            logger.debug(
                f"SIS element {inst.tag} (type={inst.isa_type}): "
                f"confidence {old:.2f}→0.10"
            )


def _classify_with_edges_strict(
    instruments: List[Instrument],
    edges: list,
    scale: Optional[DocumentScale] = None,
    profile: Optional[dict] = None,
) -> None:
    """Fallback: classify using raw edges but with VERY strict constraints."""
    sym_cfg = (profile or {}).get("symbols", {})
    sym_min  = _s(scale, sym_cfg.get("min_size",  25.0))
    sym_max  = _s(scale, sym_cfg.get("max_size",  50.0))
    hline_min = _s(scale, sym_cfg.get("hline_min", 28.0))
    hline_max = _s(scale, sym_cfg.get("hline_max", 45.0))

    edge_radius   = _s(scale, 35.0)
    hline_y_tol   = _s(scale, 12.0)
    square_near   = _s(scale, 10.0)
    square_far    = _s(scale, 30.0)
    square_margin = _s(scale, 10.0)

    classified_dcs = 0
    classified_room = 0

    for inst in instruments:
        if not inst.position:
            continue

        isa_class = _classify_by_isa_type(inst.isa_type)
        if isa_class == 'FIELD':
            inst.symbol = "circle"
            inst.classification = "Instrumento de Campo"
            inst.is_physical = True
            continue
        if isa_class == 'DCS':
            inst.symbol = "square"
            inst.classification = "DCS/Supervisório"
            inst.is_physical = False
            classified_dcs += 1
            continue

        cx = inst.position.center_x
        cy = inst.position.center_y

        nearby_edges = []
        for e in edges:
            try:
                x0  = float(e.get("x0", 0))
                top = float(e.get("top", 0))
                x1  = float(e.get("x1", 0))
                bot = float(e.get("bottom", 0))
            except (TypeError, ValueError):
                continue
            if (x0 - edge_radius) < cx < (x1 + edge_radius) and \
               (top - edge_radius) < cy < (bot + edge_radius):
                nearby_edges.append(e)

        has_hline = False
        for e in nearby_edges:
            try:
                w  = float(e.get("width", 0))
                h  = float(e.get("height", 0))
                x0 = float(e.get("x0", 0))
                y0 = float(e.get("top", 0))
                x1 = float(e.get("x1", 0))
            except (TypeError, ValueError):
                continue
            if h < _s(scale, 2.0) and hline_min < w < hline_max:
                if abs(y0 - cy) < hline_y_tol and x0 < cx < x1:
                    has_hline = True
                    break

        has_top = has_bot = has_left = has_right = False

        for e in nearby_edges:
            try:
                w  = float(e.get("width", 0))
                h  = float(e.get("height", 0))
                x0 = float(e.get("x0", 0))
                y0 = float(e.get("top", 0))
                x1 = float(e.get("x1", 0))
                y1 = float(e.get("bottom", 0))
            except (TypeError, ValueError):
                continue

            if h < _s(scale, 2.0) and sym_min < w < sym_max:
                if square_near < (cy - y0) < square_far and (x0 - square_margin) < cx < (x1 + square_margin):
                    has_top = True
                elif square_near < (y0 - cy) < square_far and (x0 - square_margin) < cx < (x1 + square_margin):
                    has_bot = True

            if w < _s(scale, 2.0) and sym_min < h < sym_max:
                if square_near < (cx - x0) < square_far and (y0 - square_margin) < cy < (y1 + square_margin):
                    has_left = True
                elif square_near < (x0 - cx) < square_far and (y0 - square_margin) < cy < (y1 + square_margin):
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

    logger.info(
        f"Symbology (edges-strict): {classified_dcs} DCS, {classified_room} Control Room, "
        f"{len(instruments) - classified_dcs - classified_room} Field"
    )
