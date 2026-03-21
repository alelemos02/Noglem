"""Detect ISA instrument tags in extracted text using regex and ISA 5.1 rules."""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

import yaml

from app.services.pid.models.instrument import (
    ISA_TYPE_DESCRIPTIONS,
    ISA_VALID_TYPES,
    ExtractedWord,
    Instrument,
    LineNumber,
    Position,
)

logger = logging.getLogger(__name__)

# Regex to detect ISA alarm/condition ANNOTATION types.
# These appear as plain text labels near instruments (e.g., "TAH", "PAL"),
# NOT inside instrument bubbles/circles.  They must NOT be detected as
# standalone instruments by the balloon strategy.
# Pattern: <variable>[D]A<H|L|HH|LL>  (e.g., TAH, PDAL, LAHH, TALL)
_ALARM_ANNOTATION_RE = re.compile(r'^[A-Z]D?A[HL]{1,2}$')


def load_profile(config_path: str, profile_name: str) -> Dict:
    """Load a tag profile from YAML config."""
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    profiles = config.get("profiles", {})
    if profile_name not in profiles:
        available = list(profiles.keys())
        raise ValueError(
            f"Profile '{profile_name}' not found. Available: {available}"
        )

    profile = profiles[profile_name]
    profile["word_merge"] = config.get("word_merge", {})
    profile["spatial"] = config.get("spatial", {})
    return profile


def detect_tags(
    words: List[ExtractedWord],
    profile: Dict,
) -> Tuple[List[Instrument], List[LineNumber]]:
    """Detect instrument tags and line numbers from extracted words.

    Uses three strategies:
    1. Single-word match: tag is in one word (e.g., "PIT-0005")
    2. Horizontal fragments: tag split across adjacent words on same line
    3. Balloon detection: ISA type word + nearby number word (vertical/proximity)
    """
    instruments = []
    line_numbers = []
    seen_tags: Set[str] = set()

    tag_pattern = re.compile(profile["tag_pattern"])
    has_area = profile.get("has_area_prefix", False)

    # Strategy 1: Single-word match
    for word in words:
        text = word.text.strip()
        if len(text) < 3:
            continue

        match = tag_pattern.search(text)
        if match:
            inst = _create_instrument_from_match(match, word, has_area, seen_tags)
            if inst:
                instruments.append(inst)

        line = _detect_line_number(text, word)
        if line:
            line_numbers.append(line)

    # Strategy 2: Horizontal fragments (adjacent words on same line)
    fragment_instruments = _detect_fragmented_tags(words, profile, seen_tags)
    instruments.extend(fragment_instruments)

    # Strategy 3: Balloon detection (ISA type + nearby number)
    balloon_instruments = _detect_balloon_tags(words, profile, seen_tags)
    instruments.extend(balloon_instruments)

    logger.info(
        f"Detected {len(instruments)} instruments, "
        f"{len(line_numbers)} line numbers"
    )
    return instruments, line_numbers


def _create_instrument_from_match(
    match: re.Match,
    word: ExtractedWord,
    has_area: bool,
    seen_tags: Set[str],
) -> Optional[Instrument]:
    """Create an Instrument from a regex match, if valid."""
    groups = match.groupdict()
    isa_type = groups.get("isa_type", "")

    if isa_type not in ISA_TYPE_DESCRIPTIONS:
        return None

    # Skip alarm/condition annotations (TAH, PAL, TALL, PDAH, etc.)
    if _ALARM_ANNOTATION_RE.match(isa_type):
        return None

    full_tag = match.group(0)
    if full_tag in seen_tags:
        return None
    seen_tags.add(full_tag)

    instrument = Instrument(
        tag=full_tag,
        isa_type=isa_type,
        isa_description=ISA_TYPE_DESCRIPTIONS.get(isa_type, "Unknown"),
        position=word.position,
        page_index=word.page_index,
        area=groups.get("area", ""),
        tag_number=groups.get("number", ""),
        qualifier=groups.get("qualifier", ""),
        confidence=_calculate_confidence(full_tag, isa_type, word),
    )

    if not has_area and "equipment" in groups:
        instrument.equipment_ref = groups["equipment"]

    logger.debug(f"Detected instrument: {full_tag} ({isa_type})")
    return instrument


def _detect_balloon_tags(
    words: List[ExtractedWord],
    profile: Dict,
    already_found: Set[str],
) -> List[Instrument]:
    """Detect tags where ISA type and number are in separate words (balloon layout).

    In P&IDs, instrument balloons show:
    - The ISA type (e.g., "PIT") inside the balloon
    - The tag number (e.g., "0025") below or beside it

    This strategy:
    1. Find words that exactly match known ISA types
    2. Look for numeric words nearby (within ~30px radius)
    3. Combine them into a tag
    """
    instruments = []
    has_area = profile.get("has_area_prefix", False)

    # Index: all words that are pure ISA types (inside instrument bubbles)
    isa_type_words = []
    for w in words:
        text = w.text.strip()
        if text in ISA_TYPE_DESCRIPTIONS and len(text) >= 2:
            # Skip alarm/condition annotations (TAH, PAL, TALL, PDAH, etc.)
            # These appear as plain text near instruments, not inside bubbles.
            if _ALARM_ANNOTATION_RE.match(text):
                continue
            # Exclude common short words that happen to be ISA types
            # "AT" could be English "at", "PI" could be math pi
            # Only include if it looks like it's in a drawing context
            if text in ("AT", "PI", "AI", "SI") and not _is_likely_instrument_context(w, words):
                continue
            isa_type_words.append(w)

    # Index: all words that look like tag numbers
    number_words = []
    for w in words:
        text = w.text.strip()
        # Tag numbers: 3-5 digits, optionally followed by a letter qualifier
        if re.match(r'^\d{3,5}[A-Z]?$', text):
            number_words.append(w)

    # Match ISA type words with nearby number words
    for type_word in isa_type_words:
        isa_type = type_word.text.strip()
        best_number = None
        best_dist = float("inf")

        for num_word in number_words:
            if num_word.page_index != type_word.page_index:
                continue

            dist = type_word.position.distance_to(num_word.position)
            # Look within 35px radius (typical balloon size)
            if dist < 35.0 and dist < best_dist:
                best_dist = dist
                best_number = num_word

        if best_number is None:
            continue

        number_text = best_number.text.strip()
        # Extract number and qualifier
        num_match = re.match(r'^(\d{3,5})([A-Z]?)$', number_text)
        if not num_match:
            continue

        tag_number = num_match.group(1)
        qualifier = num_match.group(2)

        # Look for area prefix nearby (for PROMON format)
        area = ""
        if has_area:
            area = _find_area_prefix(type_word, words)

        # Build full tag
        if area:
            full_tag = f"{area}-{isa_type}-{tag_number}{qualifier}"
        else:
            full_tag = f"{isa_type}-{tag_number}{qualifier}"

        if full_tag in already_found:
            continue
        already_found.add(full_tag)

        # Position spans both words
        pos = Position(
            x0=min(type_word.position.x0, best_number.position.x0),
            top=min(type_word.position.top, best_number.position.top),
            x1=max(type_word.position.x1, best_number.position.x1),
            bottom=max(type_word.position.bottom, best_number.position.bottom),
        )

        instrument = Instrument(
            tag=full_tag,
            isa_type=isa_type,
            isa_description=ISA_TYPE_DESCRIPTIONS.get(isa_type, "Unknown"),
            position=pos,
            page_index=type_word.page_index,
            area=area,
            tag_number=tag_number,
            qualifier=qualifier,
            confidence=0.75,  # Good confidence for balloon detection
        )
        instruments.append(instrument)
        logger.debug(
            f"Balloon tag: {full_tag} from '{isa_type}' + '{number_text}' "
            f"(dist={best_dist:.1f})"
        )

    return instruments


def _find_area_prefix(
    type_word: ExtractedWord,
    words: List[ExtractedWord],
    search_radius: float = 100.0,
) -> str:
    """Find an area prefix (3-digit number) near an ISA type word.

    In PROMON format, the area (e.g., "122") may appear:
    - In the title block (applies to all tags on the page)
    - Near the instrument balloon
    """
    # Look for 3-digit numbers near the type word
    for w in words:
        if w.page_index != type_word.page_index:
            continue
        text = w.text.strip()
        if re.match(r'^\d{3}$', text):
            dist = type_word.position.distance_to(w.position)
            if dist < search_radius:
                return text
    return ""


def _is_likely_instrument_context(
    word: ExtractedWord,
    all_words: List[ExtractedWord],
) -> bool:
    """Check if a short ISA-like word is likely an instrument tag, not English text.

    Heuristic: if there's a 3-5 digit number nearby, it's likely an instrument.
    """
    for w in all_words:
        if w.page_index != word.page_index:
            continue
        if w is word:
            continue
        dist = word.position.distance_to(w.position)
        if dist < 50.0 and re.match(r'^\d{3,5}[A-Z]?$', w.text.strip()):
            return True
    return False


def _calculate_confidence(tag: str, isa_type: str, word: ExtractedWord) -> float:
    """Calculate confidence score for a detected tag."""
    score = 0.5
    if isa_type in ISA_TYPE_DESCRIPTIONS:
        score += 0.3
    if re.search(r'\d{3,5}', tag):
        score += 0.1
    if word.merged:
        score -= 0.2
    return min(max(score, 0.0), 1.0)


# Line number regex patterns
_LINE_NUMBER_PATTERNS = [
    re.compile(
        r'(?P<diameter>\d+(?:/\d+)?)"?-'
        r'(?P<spec>[A-Z]\d[A-Z]{3,6})-'
        r'(?P<line>L\d{3,5})-'
        r'(?P<service>[A-Z]{2,4})'
    ),
    re.compile(
        r'(?P<spec>[A-Z]\d[A-Z]{3,6})-'
        r'(?P<diameter>\d+(?:/\d+)?)"?-'
        r'(?P<line>L\d{3,5})-'
        r'(?P<service>[A-Z]{2,4})'
    ),
]


def _detect_line_number(
    text: str, word: ExtractedWord
) -> Optional[LineNumber]:
    """Try to detect a line number from text."""
    for pattern in _LINE_NUMBER_PATTERNS:
        match = pattern.search(text)
        if match:
            groups = match.groupdict()
            return LineNumber(
                full_tag=match.group(0),
                diameter=groups.get("diameter", ""),
                spec_class=groups.get("spec", ""),
                line_id=groups.get("line", ""),
                service_code=groups.get("service", ""),
                position=word.position,
                page_index=word.page_index,
            )
    return None


def _detect_fragmented_tags(
    words: List[ExtractedWord],
    profile: Dict,
    already_found: Set[str],
) -> List[Instrument]:
    """Detect tags split across multiple adjacent words on the same line."""
    instruments = []

    sorted_words = sorted(
        words, key=lambda w: (w.page_index, w.position.top, w.position.x0)
    )
    lines = _group_words_into_lines(sorted_words, y_tolerance=5.0)

    tag_pattern = re.compile(profile["tag_pattern"])

    for line_words in lines:
        if len(line_words) < 2:
            continue

        for start in range(len(line_words)):
            for length in range(2, min(6, len(line_words) - start + 1)):
                window = line_words[start:start + length]

                max_gap = 15.0
                is_adjacent = True
                for k in range(len(window) - 1):
                    gap = window[k + 1].position.x0 - window[k].position.x1
                    if gap > max_gap:
                        is_adjacent = False
                        break

                if not is_adjacent:
                    continue

                combined = "".join(w.text for w in window)
                combined_dash = "-".join(w.text for w in window)

                for candidate in [combined, combined_dash]:
                    match = tag_pattern.search(candidate)
                    if match:
                        full_tag = match.group(0)
                        if full_tag in already_found:
                            continue

                        groups = match.groupdict()
                        isa_type = groups.get("isa_type", "")
                        if isa_type not in ISA_TYPE_DESCRIPTIONS:
                            continue

                        already_found.add(full_tag)

                        pos = Position(
                            x0=window[0].position.x0,
                            top=min(w.position.top for w in window),
                            x1=window[-1].position.x1,
                            bottom=max(w.position.bottom for w in window),
                        )

                        instrument = Instrument(
                            tag=full_tag,
                            isa_type=isa_type,
                            isa_description=ISA_TYPE_DESCRIPTIONS.get(
                                isa_type, "Unknown"
                            ),
                            position=pos,
                            page_index=window[0].page_index,
                            area=groups.get("area", ""),
                            tag_number=groups.get("number", ""),
                            qualifier=groups.get("qualifier", ""),
                            confidence=0.6,
                        )
                        instruments.append(instrument)
                        logger.debug(
                            f"Fragmented tag: {full_tag} "
                            f"from {[w.text for w in window]}"
                        )

    return instruments


def _group_words_into_lines(
    words: List[ExtractedWord], y_tolerance: float = 5.0
) -> List[List[ExtractedWord]]:
    """Group words into lines based on vertical position."""
    if not words:
        return []

    lines = []
    current_line = [words[0]]
    current_y = words[0].position.top

    for word in words[1:]:
        if (
            word.page_index == current_line[0].page_index
            and abs(word.position.top - current_y) <= y_tolerance
        ):
            current_line.append(word)
        else:
            lines.append(sorted(current_line, key=lambda w: w.position.x0))
            current_line = [word]
            current_y = word.position.top

    if current_line:
        lines.append(sorted(current_line, key=lambda w: w.position.x0))

    return lines
