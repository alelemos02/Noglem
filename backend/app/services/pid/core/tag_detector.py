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

# ISA type aliases: drawing bubble abbreviation → project tag designation.
# In Petrobras/PROMON P&IDs, certain instrument types are abbreviated in the
# balloon but the official project tag uses a different (fuller) designation.
# e.g., "LT" (Level Transmitter) in the bubble = "LIT" (Level Indicating
# Transmitter) in the instrument list.
_ISA_TYPE_ALIASES: Dict[str, str] = {
    "LT": "LIT",
}

# Double-bubble instrument pairs.
# In Brazilian P&ID convention, certain instruments are drawn as two
# connected circles, each showing one function:
#   TIT  = upper circle TI (indicator) + lower circle TT (transmitter)
#   PDIT = PDI (differential indicator) + PDT (differential transmitter)
#   AIT  = upper circle AI (indicator)  + lower circle AT (transmitter)
# After balloon detection finds both halves, _merge_double_bubble_tags()
# combines them into the correct single designation.
_DOUBLE_BUBBLE_PAIRS: List[Tuple[Tuple[str, str], str]] = [
    (("TI", "TT"), "TIT"),
    (("PDI", "PDT"), "PDIT"),
    (("AI", "AT"), "AIT"),
]

# ISA types that are sometimes drawn as annotations (alarm setpoints, boundary
# labels) rather than actual instrument bubbles.  When these appear without a
# dedicated instrument number directly below/beside them they are very likely
# false positives.  We require an instrument-context check for all of them.
_CONTEXT_REQUIRED_TYPES = {"AT", "PI", "AI", "SI", "AR", "VS"}


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
    page_width: float = 0.0,
) -> Tuple[List[Instrument], List[LineNumber]]:
    """Detect instrument tags and line numbers from extracted words.

    Uses three strategies:
    1. Single-word match: tag is in one word (e.g., "PIT-0005")
    2. Horizontal fragments: tag split across adjacent words on same line
    3. Balloon detection: ISA type word + nearby number word (vertical/proximity)
    Then a post-processing pass merges double-bubble instruments
    (e.g., TI+TT → TIT, PDI+PDT → PDIT).
    """
    instruments = []
    line_numbers = []
    seen_tags: Set[str] = set()

    tag_pattern = re.compile(profile["tag_pattern"])
    has_area = profile.get("has_area_prefix", False)

    # Determine title block boundary (rightmost ~17% of page).
    # Words in the title block contain document references, revision
    # tables, etc. that produce false-positive instrument detections.
    title_block_x = page_width * 0.83 if page_width > 0 else float("inf")

    # Filter words to exclude title block region for instrument detection
    drawing_words = [w for w in words if w.position.x0 < title_block_x]

    # Extract unit code from document number present anywhere on the page.
    # Example: "DE-3646.02-21231-944-EGV-002" → unit_code = "21231".
    # This code is prepended to balloon-detected tag numbers so the output
    # matches the project's full tag designation (e.g. "LIT-21231002").
    unit_code = _extract_unit_code(words)

    # Strategy 1: Single-word match
    for word in drawing_words:
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

    # Also check full word set for line numbers (they can be anywhere)
    for word in words:
        if word.position.x0 >= title_block_x:
            text = word.text.strip()
            if len(text) >= 3:
                line = _detect_line_number(text, word)
                if line:
                    line_numbers.append(line)

    # Strategy 2: Horizontal fragments (adjacent words on same line)
    fragment_instruments = _detect_fragmented_tags(drawing_words, profile, seen_tags)
    instruments.extend(fragment_instruments)

    # Strategy 3: Balloon detection (ISA type + nearby number)
    balloon_instruments = _detect_balloon_tags(
        drawing_words, profile, seen_tags, unit_code=unit_code
    )
    instruments.extend(balloon_instruments)

    # Post-processing: merge double-bubble instruments
    # (e.g., individually detected TI-001 + TT-001 → TIT-001)
    instruments = _merge_double_bubble_tags(instruments, seen_tags)

    logger.info(
        f"Detected {len(instruments)} instruments, "
        f"{len(line_numbers)} line numbers"
    )
    return instruments, line_numbers


# ---------------------------------------------------------------------------
# Unit code extraction
# ---------------------------------------------------------------------------

def _extract_unit_code(words: List[ExtractedWord]) -> str:
    """Extract 5-digit plant unit code from the document number.

    Looks for patterns like "DE-3646.02-21231-944-EGV-002" and returns
    the 5-digit segment (here "21231").  Returns "" if not found.
    """
    for w in words:
        m = re.search(r'DE-\d+\.\d{2}-(\d{5})-', w.text)
        if m:
            return m.group(1)
    return ""


# ---------------------------------------------------------------------------
# Instrument creation helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Balloon detection
# ---------------------------------------------------------------------------

def _detect_balloon_tags(
    words: List[ExtractedWord],
    profile: Dict,
    already_found: Set[str],
    unit_code: str = "",
) -> List[Instrument]:
    """Detect tags where ISA type and number are in separate words (balloon layout).

    In P&IDs, instrument balloons show:
    - The ISA type (e.g., "TIT") inside the balloon
    - The tag number (e.g., "009") below or beside it

    In some P&IDs, valve symbols include a '+' graphic character that bleeds
    into the number text (e.g., "00+8" instead of "008").  This function
    handles that by stripping '+' from candidate number words.

    For PSV instruments, an optional qualifier letter (A–D) may appear as a
    separate word just below the number.

    When a unit_code is provided (e.g., "21231"), it is prepended to the
    3-digit sequential number to form the full project tag number, matching
    the project's tagging convention (e.g., "LIT-21231002").

    This strategy:
    1. Find words that exactly match known ISA types
    2. Look for numeric words nearby (within ~45px radius), including
       '+'-contaminated variants (e.g., "00+8")
    3. Optionally pick up a single-letter qualifier (A–D) close to the number
    4. Combine them into a full tag
    """
    instruments = []
    has_area = profile.get("has_area_prefix", False)

    # Index: all words that are pure ISA types (inside instrument bubbles)
    isa_type_words = []
    for w in words:
        text = w.text.strip()
        if text in ISA_TYPE_DESCRIPTIONS and len(text) >= 2:
            # Skip alarm/condition annotations (TAH, PAL, TALL, PDAH, etc.)
            if _ALARM_ANNOTATION_RE.match(text):
                continue
            # Some short words are ambiguous (they could be ISA types OR
            # area/annotation labels).  Require instrument context for them.
            if text in _CONTEXT_REQUIRED_TYPES and not _is_likely_instrument_context(w, words):
                continue
            isa_type_words.append(w)

    # Index: all words that look like tag numbers (3 digits, possibly
    # contaminated with a '+' from valve graphics).
    # Original 3-digit: "008", "012"
    # Plus-contaminated: "00+8", "01+2"  (strip '+' → "008", "012")
    number_words = []
    for w in words:
        text = w.text.strip()
        clean = text.replace("+", "")
        if re.match(r'^\d{3}[A-Z]?$', clean):
            number_words.append(w)

    # Some ISA types are known to appear as annotations INSIDE other
    # instrument bubbles (e.g., "PV" = process variable display inside a
    # controller).  Require them to be very close to their number word to
    # avoid false positives.  15px is the typical in-bubble label distance;
    # a standalone valve balloon always has its number within 15px.
    # XV is also capped at 15px: legitimate XV bubbles always have their
    # number directly below (~10px), while cross-references or label text
    # like "XV-003" can place an XV word much farther from nearby numbers.
    _STRICT_DISTANCE_TYPES: Dict[str, float] = {"PV": 15.0, "XV": 15.0}

    # First pass: find the best number for each ISA type word, collect
    # (isa_type_word, best_number_word, distance) candidates.
    candidates = []
    for type_word in isa_type_words:
        raw_isa = type_word.text.strip()
        aliased = _ISA_TYPE_ALIASES.get(raw_isa, raw_isa)
        max_dist = _STRICT_DISTANCE_TYPES.get(aliased, 45.0)

        best_number = None
        best_dist = float("inf")

        for num_word in number_words:
            if num_word.page_index != type_word.page_index:
                continue

            dist = type_word.position.distance_to(num_word.position)
            if dist < max_dist and dist < best_dist:
                best_dist = dist
                best_number = num_word

        if best_number is not None:
            candidates.append((type_word, best_number, best_dist))

    for type_word, best_number, best_dist in candidates:
        isa_type = type_word.text.strip()

        # Apply ISA type alias mapping (e.g., drawing uses "LT" but the
        # project instrument list uses "LIT").
        isa_type = _ISA_TYPE_ALIASES.get(isa_type, isa_type)

        # Verify alias target is a known ISA type
        if isa_type not in ISA_TYPE_DESCRIPTIONS:
            continue

        number_text = best_number.text.strip().replace("+", "")
        num_match = re.match(r'^(\d{3,5})([A-Z]?)$', number_text)
        if not num_match:
            continue

        tag_number = num_match.group(1)
        qualifier = num_match.group(2)

        # For instrument types that can have multiple instances with A/B/C/D
        # identifiers, look for a single qualifier letter near the number word.
        # These appear as a separate text element adjacent to the number in
        # the P&ID balloon (e.g., PSV-001A/B, PIT-017A/B, TIT-017A/B).
        _QUALIFIER_TYPES = {"PSV", "SDV", "BDV", "PIT", "TI", "TT", "TSHH"}
        if not qualifier and isa_type in _QUALIFIER_TYPES:
            qualifier = _find_qualifier_letter(best_number, words, max_dist=25.0)

        # Build the full tag number, prepending the unit code when available.
        # This converts the 3-digit sequential number (e.g., "009") into the
        # full project number (e.g., "21231009").
        full_number = f"{unit_code}{tag_number}" if unit_code else tag_number

        # Build tag WITHOUT area prefix — balloon detection cannot
        # reliably determine the area from nearby text.  Area is only
        # correct when it comes from the full tag regex (Strategy 1).
        full_tag = f"{isa_type}-{full_number}{qualifier}"

        # Skip if this ISA-type + number was already found (possibly
        # with an area prefix by Strategy 1, e.g. "052-TI-062").
        tag_suffix = f"-{isa_type}-{full_number}{qualifier}"
        # Also check suffix without unit code for backward compat
        tag_suffix_short = f"-{isa_type}-{tag_number}{qualifier}"
        if full_tag in already_found or any(
            t.endswith(tag_suffix) or t.endswith(tag_suffix_short)
            for t in already_found
        ):
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
            area="",
            tag_number=tag_number,
            qualifier=qualifier,
            confidence=0.75,  # Good confidence for balloon detection
        )
        instruments.append(instrument)
        logger.debug(
            f"Balloon tag: {full_tag} from '{type_word.text.strip()}' + '{number_text}' "
            f"(dist={best_dist:.1f})"
        )

    return instruments


def _find_qualifier_letter(
    number_word: ExtractedWord,
    words: List[ExtractedWord],
    max_dist: float = 25.0,
) -> str:
    """Find a single uppercase qualifier letter (A–D) near a number word.

    Used to detect PSV suffixes like A, B, C, D that appear as separate
    text elements below the instrument number in the P&ID balloon.
    """
    best_letter = ""
    best_dist = float("inf")
    for w in words:
        if w.page_index != number_word.page_index:
            continue
        text = w.text.strip()
        if not re.match(r'^[A-D]$', text):
            continue
        dist = number_word.position.distance_to(w.position)
        if dist < max_dist and dist < best_dist:
            best_dist = dist
            best_letter = text
    return best_letter


# ---------------------------------------------------------------------------
# Double-bubble merging
# ---------------------------------------------------------------------------

def _merge_double_bubble_tags(
    instruments: List[Instrument],
    seen_tags: Set[str],
) -> List[Instrument]:
    """Merge double-bubble instruments into their combined designation.

    In Brazilian Petrobras P&ID convention certain instruments are drawn as
    two connected circles, each showing one aspect of the function:

        TIT (Temperature Indicating Transmitter)
            upper circle → TI   (indicator)
            lower circle → TT   (transmitter)

        PDIT (Pressure Differential Indicating Transmitter)
            left circle  → PDI  (differential indicator)
            right circle → PDT  (differential transmitter)

    When both halves are detected separately (with the same tag number and
    on the same page, within ~120px of each other), this function replaces
    them with a single instrument of the correct combined type.

    Instruments that have no matching partner are left unchanged.
    """
    merged: List[Instrument] = []
    skip_indices: Set[int] = set()

    # Build a fast lookup: (isa_type, page_index, tag_number) → list of indices
    type_index: Dict[Tuple[str, int, str], List[int]] = {}
    for idx, inst in enumerate(instruments):
        key = (inst.isa_type, inst.page_index, inst.tag_number)
        type_index.setdefault(key, []).append(idx)

    for i, inst_a in enumerate(instruments):
        if i in skip_indices:
            continue

        paired = False
        for (type_a, type_b), combined_type in _DOUBLE_BUBBLE_PAIRS:
            if inst_a.isa_type not in (type_a, type_b):
                continue

            # Determine which type we're looking for as the partner
            partner_type = type_b if inst_a.isa_type == type_a else type_a

            partner_key = (partner_type, inst_a.page_index, inst_a.tag_number)
            partner_indices = type_index.get(partner_key, [])

            # Find the nearest un-skipped partner with matching qualifier.
            # Qualifier matching: if BOTH instruments specify a qualifier
            # (e.g., TI-017B + TT-017B), only pair them when qualifiers match.
            # This handles multi-instance instruments like TIT-017A / TIT-017B
            # where the TI and TT halves may be far apart on the drawing
            # (up to 250px) but must carry the same qualifier letter.
            best_partner_idx = None
            best_dist = float("inf")
            for j in partner_indices:
                if j in skip_indices or j == i:
                    continue
                partner = instruments[j]
                # Reject mismatched qualifiers (e.g., TI-017B ≠ TT-017A)
                if (inst_a.qualifier and partner.qualifier
                        and inst_a.qualifier != partner.qualifier):
                    continue
                dist = inst_a.position.distance_to(partner.position)
                if dist < 250.0 and dist < best_dist:
                    best_dist = dist
                    best_partner_idx = j

            if best_partner_idx is None:
                continue

            partner = instruments[best_partner_idx]

            # Use inst_a's tag components; prefer non-empty qualifier
            qualifier = inst_a.qualifier or partner.qualifier
            tag_number = inst_a.tag_number

            # Reconstruct full tag from inst_a (already has unit code if applicable)
            # e.g., inst_a.tag = "TI-21231009" → split on "-" to get base
            # The combined tag replaces the ISA type prefix only.
            # inst_a.tag format: "{isa_type}-{full_number}{qualifier}"
            # We just replace isa_type with combined_type.
            existing_number_part = inst_a.tag[len(inst_a.isa_type) + 1:]  # after "TI-"
            new_full_tag = f"{combined_type}-{existing_number_part}"

            if new_full_tag in seen_tags:
                skip_indices.add(best_partner_idx)
                paired = True
                break
            seen_tags.add(new_full_tag)
            seen_tags.discard(inst_a.tag)
            seen_tags.discard(partner.tag)

            skip_indices.add(best_partner_idx)
            paired = True

            combined_instrument = Instrument(
                tag=new_full_tag,
                isa_type=combined_type,
                isa_description=ISA_TYPE_DESCRIPTIONS.get(combined_type, "Unknown"),
                position=inst_a.position,
                page_index=inst_a.page_index,
                area=inst_a.area,
                tag_number=tag_number,
                qualifier=qualifier,
                confidence=max(inst_a.confidence, partner.confidence),
            )
            merged.append(combined_instrument)
            logger.debug(
                f"Merged double-bubble: {inst_a.tag} + {partner.tag} → {new_full_tag}"
            )
            break  # handled this instrument

        if not paired:
            merged.append(inst_a)

    return merged


# ---------------------------------------------------------------------------
# Context detection helper
# ---------------------------------------------------------------------------

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
    Accepts '+'-contaminated numbers (e.g., "00+8") as valid nearby numbers.
    """
    for w in all_words:
        if w.page_index != word.page_index:
            continue
        if w is word:
            continue
        dist = word.position.distance_to(w.position)
        clean = w.text.strip().replace("+", "")
        if dist < 50.0 and re.match(r'^\d{3,5}[A-Z]?$', clean):
            return True
    return False


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Line number detection
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Fragmented tag detection
# ---------------------------------------------------------------------------

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
