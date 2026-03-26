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

    # Detect package furnished traits
    _detect_furnished_modifier(instruments, words)

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
    """Detect tags where ISA type and number are grouped vertically in a balloon."""
    instruments = []
    has_area = profile.get("has_area_prefix", False)

    isa_type_words = []
    for w in words:
        text = w.text.strip()
        if text in ISA_TYPE_DESCRIPTIONS and len(text) >= 2:
            if text in ("AT", "PI", "AI", "SI") and not _is_likely_instrument_context(w, words):
                continue
            isa_type_words.append(w)

    for type_word in isa_type_words:
        isa_type = type_word.text.strip()

        cx = type_word.position.center_x
        cy = type_word.position.center_y

        stacked_words = []
        for w in words:
            if w.page_index != type_word.page_index or w is type_word:
                continue

            dx = w.position.center_x - cx
            dy = w.position.center_y - cy

            align_vert = abs(dx) < 18.0 and 0 < dy < 55.0
            align_horiz = abs(dy) < 18.0 and abs(dx) < 55.0

            if align_vert or align_horiz:
                stacked_words.append(w)

        if not stacked_words:
            continue

        stacked_words.sort(key=lambda w: type_word.position.distance_to(w.position))

        number_parts = []
        valid_stack = []
        last_word = type_word

        for w in stacked_words:
            text = w.text.strip()

            dist_prev = last_word.position.distance_to(w.position)
            if dist_prev > 25.0:
                break

            if re.match(r'^[\w-]+$', text):
                number_parts.append(text)
                valid_stack.append(w)
                last_word = w

        if not number_parts:
            continue

        tag_number = "-".join(number_parts)

        x0 = min([type_word.position.x0] + [w.position.x0 for w in valid_stack])
        top = min([type_word.position.top] + [w.position.top for w in valid_stack])
        x1 = max([type_word.position.x1] + [w.position.x1 for w in valid_stack])
        bottom = max([type_word.position.bottom] + [w.position.bottom for w in valid_stack])
        pos = Position(x0=x0, top=top, x1=x1, bottom=bottom)

        area = ""
        if has_area:
            area = _find_area_prefix(type_word, words)

        if area:
            full_tag = f"{area}-{isa_type}-{tag_number}"
        else:
            full_tag = f"{isa_type}-{tag_number}"

        if full_tag in already_found:
            continue
        already_found.add(full_tag)

        instrument = Instrument(
            tag=full_tag,
            isa_type=isa_type,
            isa_description=ISA_TYPE_DESCRIPTIONS.get(isa_type, "Unknown"),
            position=pos,
            page_index=type_word.page_index,
            area=area,
            tag_number=tag_number,
            qualifier="",
            confidence=0.85,
        )
        instruments.append(instrument)
        logger.debug(f"Balloon stack tag: {full_tag} from '{isa_type}' + {number_parts}")

    return instruments


def _find_area_prefix(
    type_word: ExtractedWord,
    words: List[ExtractedWord],
    search_radius: float = 30.0,
) -> str:
    """Find an area prefix horizontally near an ISA type word."""
    cx = type_word.position.center_x
    cy = type_word.position.center_y
    for w in words:
        if w.page_index != type_word.page_index:
            continue
        text = w.text.strip()
        if re.match(r'^\d{3}$', text):
            if abs(w.position.center_y - cy) < 15.0 and abs(w.position.center_x - cx) < search_radius:
                return text
    return ""


def _detect_furnished_modifier(instruments: List[Instrument], words: List[ExtractedWord]) -> None:
    """Finds words literally matching 'F' or '(F)' near instruments to flag them as furnished packages."""
    if not instruments:
        return

    f_words = [w for w in words if w.text.strip().replace(" ", "").upper() in ("F", "(F)")]
    if not f_words:
        return

    for inst in instruments:
        if not inst.position:
            continue

        for fw in f_words:
            if fw.page_index != inst.page_index:
                continue
            dist = inst.position.distance_to(fw.position)
            if dist < 45.0:
                inst.furnished_by_package = True
                logger.debug(f"Detected {inst.tag} as Furnished by Package ('{fw.text}' at dist {dist:.1f})")
                break


def _is_likely_instrument_context(
    word: ExtractedWord,
    all_words: List[ExtractedWord],
) -> bool:
    """Check if a short ISA-like word is likely an instrument tag, not English text."""
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
