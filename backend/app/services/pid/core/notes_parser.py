"""Parse drawing notes that affect instrument specifications."""

import logging
import re
from typing import List, Optional

from app.services.pid.models.instrument import DrawingNote, ExtractedWord, ISA_TYPE_DESCRIPTIONS
from app.services.pid.core.document_scale import DocumentScale, _s

logger = logging.getLogger(__name__)

INSTRUMENT_KEYWORDS = [
    "INSTRUMENT", "GAUGE", "TRANSMITTER", "VALVE", "SWITCH",
    "THERMOWELL", "DIAPHRAGM", "PSV", "PT", "PI", "FT", "FI",
    "INDICATOR", "CONTROLLER", "SENSOR", "ELEMENT",
    "FLANGE", "RATING", "CLASS", "SPECIFICATION",
    "ALL", "EVERY", "EACH", "SHALL", "MUST",
]


def parse_notes(
    words: List[ExtractedWord],
    page_width: float,
    page_height: float,
    scale: Optional[DocumentScale] = None,
) -> List[DrawingNote]:
    """Extract numbered notes from the drawing."""
    notes_region_words = _find_notes_region(words, page_width, page_height, scale)
    if not notes_region_words:
        notes_region_words = words

    lines = _reconstruct_lines(notes_region_words, y_tolerance=_s(scale, 5.0))
    notes = _parse_numbered_notes(lines)

    logger.info(f"Parsed {len(notes)} drawing notes")
    return notes


def _find_notes_region(
    words: List[ExtractedWord],
    page_width: float,
    page_height: float,
    scale: Optional[DocumentScale] = None,
) -> List[ExtractedWord]:
    """Find the region containing drawing notes."""
    notes_header = None
    for w in words:
        if w.text.upper() in ("NOTES", "NOTES:", "NOTAS", "NOTAS:"):
            notes_header = w
            break

    if not notes_header:
        return []

    header_y = notes_header.position.top
    header_x = notes_header.position.x0
    x_margin = page_width * 0.3
    top_margin = _s(scale, 5.0)

    return [
        w for w in words
        if (
            w.position.top >= header_y - top_margin
            and abs(w.position.x0 - header_x) < x_margin
        )
    ]


def _reconstruct_lines(
    words: List[ExtractedWord], y_tolerance: float = 5.0
) -> List[str]:
    """Reconstruct text lines from individual words."""
    if not words:
        return []

    sorted_words = sorted(words, key=lambda w: (w.position.top, w.position.x0))

    lines = []
    current_line_words = [sorted_words[0]]
    current_y = sorted_words[0].position.top

    for word in sorted_words[1:]:
        if abs(word.position.top - current_y) <= y_tolerance:
            current_line_words.append(word)
        else:
            lines.append(" ".join(w.text for w in current_line_words))
            current_line_words = [word]
            current_y = word.position.top

    if current_line_words:
        lines.append(" ".join(w.text for w in current_line_words))

    return lines


def _parse_numbered_notes(lines: List[str]) -> List[DrawingNote]:
    """Parse numbered notes from text lines."""
    notes = []
    current_note_num = None
    current_note_text = []

    note_start_pattern = re.compile(
        r'^(?:NOTE\s*)?(\d{1,2})[.\s:)\-]+\s*(.*)', re.IGNORECASE
    )

    for line in lines:
        match = note_start_pattern.match(line.strip())
        if match:
            if current_note_num is not None:
                note_text = " ".join(current_note_text).strip()
                notes.append(_create_note(current_note_num, note_text))

            try:
                current_note_num = int(match.group(1))
            except (ValueError, TypeError):
                logger.warning("Número de nota inválido: %r — ignorado", match.group(1))
                current_note_num = None
                continue
            current_note_text = [match.group(2)]
        elif current_note_num is not None:
            current_note_text.append(line.strip())

    if current_note_num is not None:
        note_text = " ".join(current_note_text).strip()
        notes.append(_create_note(current_note_num, note_text))

    return notes


def _create_note(number: int, text: str) -> DrawingNote:
    """Create a DrawingNote and determine if it affects instruments."""
    text_upper = text.upper()
    affects = any(kw in text_upper for kw in INSTRUMENT_KEYWORDS)

    affected_types = []
    if affects:
        for isa_type in ISA_TYPE_DESCRIPTIONS:
            if len(isa_type) >= 2 and isa_type in text_upper:
                affected_types.append(isa_type)

        all_pattern = re.compile(r'ALL\s+(\w+)', re.IGNORECASE)
        all_pattern.findall(text)
        types_in_text = re.findall(r'\b([A-Z]{2,4})\b', text_upper)
        for t in types_in_text:
            if t in ISA_TYPE_DESCRIPTIONS and t not in affected_types:
                affected_types.append(t)

    return DrawingNote(
        number=number,
        text=text,
        affects_instruments=affects,
        affected_types=affected_types,
    )
