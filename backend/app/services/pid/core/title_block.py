"""Parse title block (carimbo) from P&ID drawings."""

import logging
import re
from typing import List, Optional

from app.services.pid.models.instrument import DrawingMetadata, ExtractedWord
from app.services.pid.core.document_scale import DocumentScale, _s

logger = logging.getLogger(__name__)

# Title block is typically in the bottom-right or right strip of the drawing.
# We use relative position thresholds (percentage of page dimensions).
TITLE_BLOCK_X_THRESHOLD = 0.70  # Right 30% of page
TITLE_BLOCK_Y_THRESHOLD = 0.80  # Bottom 20% of page


def parse_title_block(
    words: List[ExtractedWord],
    page_width: float,
    page_height: float,
    page_index: int = 0,
    scale: Optional[DocumentScale] = None,
) -> DrawingMetadata:
    """Extract drawing metadata from the title block area.

    Args:
        words: All extracted words from the page.
        page_width: Page width in points.
        page_height: Page height in points.
        page_index: Index of the page being parsed.

    Returns:
        DrawingMetadata with extracted fields.
    """
    metadata = DrawingMetadata()

    # Filter words in the title block region
    tb_words = _get_title_block_words(words, page_width, page_height)
    if not tb_words:
        logger.warning(f"Page {page_index}: No words found in title block region")
        return metadata

    # Combine all title block text for regex matching
    tb_text = " ".join(w.text for w in tb_words)

    # Extract document number (various formats)
    metadata.document_number = _extract_document_number(tb_words, tb_text)

    # Extract revision
    metadata.revision = _extract_revision(tb_words, tb_text)

    # Extract title/description
    metadata.title = _extract_title(tb_words, tb_text, scale=scale)

    # Extract area
    metadata.area = _extract_area(tb_words, tb_text)

    # Extract sheet info
    metadata.sheet_number, metadata.total_sheets = _extract_sheet_info(
        tb_words, tb_text
    )

    # Extract date
    metadata.date = _extract_date(tb_text)

    # Extract scale
    metadata.scale = _extract_scale(tb_text)

    logger.info(
        f"Page {page_index} title block: "
        f"doc={metadata.document_number}, rev={metadata.revision}, "
        f"title='{metadata.title[:50]}...'" if len(metadata.title) > 50 else
        f"Page {page_index} title block: "
        f"doc={metadata.document_number}, rev={metadata.revision}, "
        f"title='{metadata.title}'"
    )

    return metadata


def _get_title_block_words(
    words: List[ExtractedWord],
    page_width: float,
    page_height: float,
) -> List[ExtractedWord]:
    """Filter words that are in the title block region."""
    x_threshold = page_width * TITLE_BLOCK_X_THRESHOLD
    y_threshold = page_height * TITLE_BLOCK_Y_THRESHOLD

    # Title block: bottom-right corner OR right strip
    tb_words = [
        w for w in words
        if (w.position.x0 >= x_threshold or w.position.top >= y_threshold)
    ]

    return tb_words


def _extract_document_number(
    words: List[ExtractedWord], text: str
) -> str:
    """Extract document number from title block."""
    # Common patterns for document numbers
    patterns = [
        # Technip: 100388513.004 or 100388513
        re.compile(r'(\d{9}(?:\.\d{3})?)'),
        # PROMON: E.DTAE001-EQ2-13301
        re.compile(r'(E\.[A-Z]+\d+-[A-Z]+\d+-\d+)'),
        # Generic: alphanumeric with dashes, at least 8 chars
        re.compile(r'([A-Z0-9]{3,}-[A-Z0-9]{2,}-\d{4,})'),
    ]

    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1)

    # Fallback: look for words near "DOCUMENT" or "NUMBER" labels
    for i, w in enumerate(words):
        if w.text.upper() in ("DOCUMENT", "DWG", "DRAWING", "NÚMERO", "NUMERO"):
            # Look at nearby words (next 3 words)
            for j in range(i + 1, min(i + 4, len(words))):
                candidate = words[j].text
                if re.match(r'^[A-Z0-9.\-]{6,}$', candidate):
                    return candidate

    return ""


def _extract_revision(words: List[ExtractedWord], text: str) -> str:
    """Extract revision from title block."""
    patterns = [
        re.compile(r'(?:REV|REVISION)[.\s:]*([A-Z0-9]{1,4})', re.IGNORECASE),
        re.compile(r'\b(R\d{3,4})\b'),  # R0000 format
        re.compile(r'Rev\.?\s*(\d+)', re.IGNORECASE),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return ""


def _extract_title(
    words: List[ExtractedWord],
    text: str,
    scale: Optional[DocumentScale] = None,
) -> str:
    """Extract drawing title/description from title block."""
    # Look for common title keywords
    title_keywords = [
        "FLUXOGRAMA", "DIAGRAMA", "P&ID", "PID", "PIPING",
        "INSTRUMENT", "PROCESS", "SISTEMA", "SYSTEM",
    ]

    line_tol = _s(scale, 10.0)   # Vertical tolerance for same-line grouping
    title_tol = _s(scale, 15.0)  # Vertical tolerance for title fallback

    # Find words near title keywords and collect surrounding text
    title_parts = []
    for i, w in enumerate(words):
        upper = w.text.upper()
        if any(kw in upper for kw in title_keywords):
            # Collect this word and nearby words at similar Y position
            y_ref = w.position.top
            nearby = [
                ww for ww in words
                if abs(ww.position.top - y_ref) < line_tol
            ]
            nearby.sort(key=lambda ww: ww.position.x0)
            title_parts = [ww.text for ww in nearby]
            break

    if title_parts:
        return " ".join(title_parts)

    # Fallback: look for text near "TITLE" or "TÍTULO"
    for i, w in enumerate(words):
        if w.text.upper() in ("TITLE", "TÍTULO", "TITULO"):
            y_ref = w.position.top
            nearby = [
                ww for ww in words
                if abs(ww.position.top - y_ref) < title_tol and ww.position.x0 > w.position.x1
            ]
            if nearby:
                nearby.sort(key=lambda ww: ww.position.x0)
                return " ".join(ww.text for ww in nearby)

    return ""


def _extract_area(words: List[ExtractedWord], text: str) -> str:
    """Extract area/PBS identifier from title block."""
    patterns = [
        re.compile(r'(?:ÁREA|AREA|PBS)[:\s]*(\d{3,5})', re.IGNORECASE),
        re.compile(r'(?:AREA)[:\s]*([A-Z0-9]{3,})', re.IGNORECASE),
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return ""


def _extract_sheet_info(
    words: List[ExtractedWord], text: str
) -> tuple:
    """Extract sheet number and total sheets."""
    patterns = [
        re.compile(r'(\d{1,3})\s*/\s*(\d{1,3})'),  # "04/20" or "4 / 20"
        re.compile(r'(\d{1,3})\s*(?:OF|DE)\s*(\d{1,3})', re.IGNORECASE),
        re.compile(r'(?:SHEET|FOLHA|FL\.?)\s*(\d{1,3})', re.IGNORECASE),
    ]

    for pattern in patterns:
        match = pattern.search(text)
        if match:
            groups = match.groups()
            if len(groups) >= 2:
                return groups[0], groups[1]
            return groups[0], ""

    return "", ""


def _extract_date(text: str) -> str:
    """Extract date from title block."""
    patterns = [
        re.compile(r'(\d{2}[./]\d{2}[./]\d{4})'),  # DD/MM/YYYY or DD.MM.YYYY
        re.compile(r'(\d{2}/\d{4})'),  # MM/YYYY
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return ""


def _extract_scale(text: str) -> str:
    """Extract drawing scale from title block."""
    patterns = [
        re.compile(r'(?:SCALE|ESCALA)[:\s]*([\d:]+|S/?E|NTS)', re.IGNORECASE),
        re.compile(r'(\d+:\d+)'),  # 1:100 format
    ]
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return ""
