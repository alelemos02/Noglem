"""Parse drawing notes that affect instrument specifications."""

import logging
import re
from typing import List

from app.services.pid.models.instrument import DrawingNote, ExtractedWord, ISA_TYPE_DESCRIPTIONS

logger = logging.getLogger(__name__)

# Keywords that indicate a note affects instruments
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
) -> List[DrawingNote]:
    """Extract numbered notes from the drawing.

    Notes are typically in the top-right or bottom area,
    formatted as "1. note text" or "NOTE 1: text".

    Args:
        words: All extracted words from the page.
        page_width: Page width in points.
        page_height: Page height in points.

    Returns:
        List of DrawingNote objects.
    """
    # First, try to find the notes section by looking for "NOTES" or "NOTAS" header
    notes_region_words = _find_notes_region(words, page_width, page_height)
    if not notes_region_words:
        notes_region_words = words  # Fall back to all words

    # Reconstruct text lines from words
    lines = _reconstruct_lines(notes_region_words)

    # Parse numbered notes
    notes = _parse_numbered_notes(lines)

    logger.info(f"Parsed {len(notes)} drawing notes")
    return notes


def _find_notes_region(
    words: List[ExtractedWord],
    page_width: float,
    page_height: float,
) -> List[ExtractedWord]:
    """Find the region containing drawing notes."""
    # Look for "NOTES" or "NOTAS" header
    notes_header = None
    for w in words:
        if w.text.upper() in ("NOTES", "NOTES:", "NOTAS", "NOTAS:"):
            notes_header = w
            break

    if not notes_header:
        return []

    # Collect words below and near the notes header
    header_y = notes_header.position.top
    header_x = notes_header.position.x0

    # Notes typically extend downward from the header,
    # within a reasonable horizontal range
    x_margin = page_width * 0.3  # Allow 30% width range
    notes_words = [
        w for w in words
        if (
            w.position.top >= header_y - 5
            and abs(w.position.x0 - header_x) < x_margin
        )
    ]

    return notes_words


def _reconstruct_lines(
    words: List[ExtractedWord], y_tolerance: float = 5.0
) -> List[str]:
    """Reconstruct text lines from individual words."""
    if not words:
        return []

    # Sort by Y, then X
    sorted_words = sorted(words, key=lambda w: (w.position.top, w.position.x0))

    lines = []
    current_line_words = [sorted_words[0]]
    current_y = sorted_words[0].position.top

    for word in sorted_words[1:]:
        if abs(word.position.top - current_y) <= y_tolerance:
            current_line_words.append(word)
        else:
            line_text = " ".join(w.text for w in current_line_words)
            lines.append(line_text)
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

    # Pattern for note start: "1." or "NOTE 1:" or "1 -" etc.
    note_start_pattern = re.compile(
        r'^(?:NOTE\s*)?(\d{1,2})[.\s:)\-]+\s*(.*)', re.IGNORECASE
    )

    for line in lines:
        match = note_start_pattern.match(line.strip())
        if match:
            # Save previous note if any
            if current_note_num is not None:
                note_text = " ".join(current_note_text).strip()
                notes.append(_create_note(current_note_num, note_text))

            current_note_num = int(match.group(1))
            current_note_text = [match.group(2)]
        elif current_note_num is not None:
            # Continuation of current note
            current_note_text.append(line.strip())

    # Save last note
    if current_note_num is not None:
        note_text = " ".join(current_note_text).strip()
        notes.append(_create_note(current_note_num, note_text))

    return notes


def _create_note(number: int, text: str) -> DrawingNote:
    """Create a DrawingNote and determine if it affects instruments."""
    text_upper = text.upper()
    affects = any(kw in text_upper for kw in INSTRUMENT_KEYWORDS)

    # Find which ISA types this note mentions
    affected_types = []
    if affects:
        for isa_type in ISA_TYPE_DESCRIPTIONS:
            if len(isa_type) >= 2 and isa_type in text_upper:
                affected_types.append(isa_type)

        # Check for "ALL" + type patterns
        all_pattern = re.compile(r'ALL\s+(\w+)', re.IGNORECASE)
        matches = all_pattern.findall(text)
        for m in matches:
            upper_m = m.upper()
            # Check if it's referencing types like "ALL PT & PI"
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
