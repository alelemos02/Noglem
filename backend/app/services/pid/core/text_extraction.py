"""Extract words with coordinates from PDF pages, handling fragmented text."""

import logging
from typing import List, Optional

import pdfplumber

from app.services.pid.models.instrument import ExtractedWord, Position

logger = logging.getLogger(__name__)


def extract_words(
    pdf_path: str,
    page_indices: Optional[List[int]] = None,
    merge_gap_x: float = 5.0,
    merge_gap_y: float = 3.0,
) -> List[ExtractedWord]:
    """Extract words with positions from PDF pages.

    Args:
        pdf_path: Path to PDF file.
        page_indices: Specific pages to extract (None = all pages).
        merge_gap_x: Max horizontal gap to merge adjacent words.
        merge_gap_y: Max vertical gap to consider words on same line.

    Returns:
        List of ExtractedWord with positions.
    """
    all_words = []

    with pdfplumber.open(pdf_path) as pdf:
        indices = page_indices if page_indices is not None else range(len(pdf.pages))

        for page_idx in indices:
            if page_idx >= len(pdf.pages):
                logger.warning(f"Page index {page_idx} out of range, skipping")
                continue

            page = pdf.pages[page_idx]
            raw_words = page.extract_words(
                keep_blank_chars=False,
                x_tolerance=2,
                y_tolerance=2,
            )

            page_words = []
            for w in raw_words:
                text = w.get("text", "").strip()
                if not text:
                    continue

                word = ExtractedWord(
                    text=text,
                    position=Position(
                        x0=float(w["x0"]),
                        top=float(w["top"]),
                        x1=float(w["x1"]),
                        bottom=float(w["bottom"]),
                    ),
                    page_index=page_idx,
                )
                page_words.append(word)

            # Merge adjacent words that are likely part of the same tag
            merged = _merge_adjacent_words(page_words, merge_gap_x, merge_gap_y)
            all_words.extend(merged)

            logger.debug(
                f"Page {page_idx}: {len(raw_words)} raw words -> "
                f"{len(merged)} after merge"
            )

    logger.info(f"Extracted {len(all_words)} words from {pdf_path}")
    return all_words


def _merge_adjacent_words(
    words: List[ExtractedWord],
    max_gap_x: float,
    max_gap_y: float,
) -> List[ExtractedWord]:
    """Merge words that are horizontally adjacent (likely fragments of one tag).

    Words are merged only if:
    - They are on the same line (vertical overlap within tolerance)
    - Horizontal gap is less than max_gap_x
    - The combined text looks like it could be a tag (contains alphanumeric + dashes)

    Args:
        words: Words to process.
        max_gap_x: Maximum horizontal gap to merge.
        max_gap_y: Maximum vertical difference for same line.

    Returns:
        List with adjacent words merged where appropriate.
    """
    if not words:
        return []

    # Sort by vertical position (top), then horizontal (x0)
    sorted_words = sorted(words, key=lambda w: (w.position.top, w.position.x0))

    result = []
    i = 0

    while i < len(sorted_words):
        current = sorted_words[i]
        merged_text = current.text
        merged_x1 = current.position.x1
        merged_bottom = current.position.bottom
        was_merged = False

        # Look ahead for adjacent words on same line
        j = i + 1
        while j < len(sorted_words):
            next_word = sorted_words[j]

            # Check if on same line (vertical overlap)
            vertical_diff = abs(next_word.position.top - current.position.top)
            if vertical_diff > max_gap_y:
                break  # Past this line, stop looking

            # Check horizontal gap
            gap = next_word.position.x0 - merged_x1
            if gap < 0 or gap > max_gap_x:
                j += 1
                continue

            # Merge
            merged_text += next_word.text
            merged_x1 = next_word.position.x1
            merged_bottom = max(merged_bottom, next_word.position.bottom)
            was_merged = True
            j += 1

        merged_word = ExtractedWord(
            text=merged_text,
            position=Position(
                x0=current.position.x0,
                top=current.position.top,
                x1=merged_x1,
                bottom=merged_bottom,
            ),
            page_index=current.page_index,
            merged=was_merged,
        )
        result.append(merged_word)

        # Also keep original unmerged words so tag detector can try both
        if was_merged:
            for k in range(i, j):
                result.append(sorted_words[k])

        i = j if was_merged else i + 1

    return result


def extract_words_by_zone(
    pdf_path: str,
    page_index: int,
    zones: int = 4,
    merge_gap_x: float = 5.0,
    merge_gap_y: float = 3.0,
) -> dict:
    """Extract words organized by spatial zones (quadrants).

    Divides the page into zones x zones grid and returns words per zone.
    Useful for reducing false associations in spatial analysis.

    Args:
        pdf_path: Path to PDF file.
        page_index: Page to process.
        zones: Number of divisions per axis (4 = 4x4 = 16 zones).

    Returns:
        Dict mapping (row, col) zone tuple to list of ExtractedWord.
    """
    words = extract_words(
        pdf_path,
        page_indices=[page_index],
        merge_gap_x=merge_gap_x,
        merge_gap_y=merge_gap_y,
    )

    if not words:
        return {}

    # Get page dimensions
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_index]
        page_width = float(page.width)
        page_height = float(page.height)

    zone_width = page_width / zones
    zone_height = page_height / zones

    zone_map = {}
    for word in words:
        col = min(int(word.position.center_x / zone_width), zones - 1)
        row = min(int(word.position.center_y / zone_height), zones - 1)
        key = (row, col)
        if key not in zone_map:
            zone_map[key] = []
        zone_map[key].append(word)

    return zone_map
