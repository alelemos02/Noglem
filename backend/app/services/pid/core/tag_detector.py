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
from app.services.pid.core.document_scale import DocumentScale, _s

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
    profile["symbols"] = config.get("symbols", {})
    profile["balloon"] = config.get("balloon", {})
    profile["sil_isa_types"] = config.get("sil_isa_types", [])
    return profile


def detect_tags(
    words: List[ExtractedWord],
    profile: Dict,
    scale: Optional[DocumentScale] = None,
) -> Tuple[List[Instrument], List[LineNumber]]:
    """Detect instrument tags and line numbers from extracted words.

    Uses three strategies:
    1. Single-word match: tag is in one word (e.g., "PIT-0005")
    2. Horizontal fragments: tag split across adjacent words on same line
    3. Balloon detection: ISA type word + nearby number word (vertical/proximity)

    Args:
        words: Extracted words with coordinates.
        profile: Active tag profile (from load_profile).
        scale: DocumentScale for adaptive spatial thresholds. None = use base values.
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
    fragment_instruments = _detect_fragmented_tags(words, profile, seen_tags, scale)
    instruments.extend(fragment_instruments)

    # Strategy 3: Balloon detection (ISA type + nearby number)
    balloon_instruments = _detect_balloon_tags(words, profile, seen_tags, scale)
    instruments.extend(balloon_instruments)

    # Remove lower-confidence duplicates that share the same logical tag
    instruments = _deduplicate_instruments(instruments)

    # Detect package furnished traits
    _detect_furnished_modifier(instruments, words, scale)

    logger.info(
        f"Detected {len(instruments)} instruments, "
        f"{len(line_numbers)} line numbers"
    )
    return instruments, line_numbers


def _deduplicate_instruments(instruments: List[Instrument]) -> List[Instrument]:
    """Remove lower-confidence duplicates that share (isa_type, tag_number, qualifier, page).

    When the detector runs multiple strategies it can produce the same balloon
    twice — e.g., "PI-622" (balloon strategy, 85%) and "622-PI-622" (fragment
    strategy, 60%) for the same physical instrument. Keep only the highest-
    confidence representative; tie-break by preferring no area prefix (simpler tag).
    """
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for inst in instruments:
        key = (inst.isa_type, inst.tag_number, inst.qualifier, inst.page_index)
        groups[key].append(inst)

    result = []
    for group in groups.values():
        if len(group) == 1:
            result.append(group[0])
        else:
            best = max(group, key=lambda i: (i.confidence, not i.area))
            for dropped in group:
                if dropped is not best:
                    logger.debug(f"Dedup: dropped '{dropped.tag}' in favour of '{best.tag}'")
            result.append(best)
    return result


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
    scale: Optional[DocumentScale] = None,
) -> List[Instrument]:
    """Detect tags where ISA type and number are grouped vertically in a balloon.

    In P&IDs, instrument balloons can show logic like:
    - ISA type (e.g., "PI")
    - 1st part of number (e.g., "5210")
    - 2nd part of number (e.g., "005")
    stacked vertically.

    All spatial tolerances are scaled by DocumentScale when provided.
    """
    instruments = []
    has_area = profile.get("has_area_prefix", False)

    # Read balloon tolerances from profile
    bal = profile.get("balloon", {})
    # Vertical stacking: font-relative multipliers (scale-independent)
    v_align_mult  = bal.get("v_alignment_multiplier", 1.5)
    v_range_mult  = bal.get("v_range_multiplier", 6.0)
    chain_mult    = bal.get("chain_distance_multiplier", 3.0)
    # Horizontal stacking: pixel-based scaled by DocumentScale
    h_tol_x = _s(scale, bal.get("h_tolerance_x", 55.0))
    h_tol_y = _s(scale, bal.get("h_tolerance_y", 18.0))

    isa_type_words = []
    for w in words:
        text = w.text.strip()
        if text in ISA_TYPE_DESCRIPTIONS and len(text) >= 2:
            # Reject short ambiguous types unless they have a number nearby
            if text in ("AT", "PI", "AI", "SI") and not _is_likely_instrument_context(w, words, scale):
                continue
            # Reject if this ISA text is embedded inside a longer string (e.g. line tags)
            if _is_part_of_line_tag(w, words, scale):
                continue
            isa_type_words.append(w)

    for type_word in isa_type_words:
        isa_type = type_word.text.strip()

        # Font-relative thresholds: computed from the ISA type word's own text height
        word_h = max(type_word.position.bottom - type_word.position.top, 4.0)
        v_tol_x = word_h * v_align_mult   # horizontal alignment tolerance
        v_tol_y = word_h * v_range_mult   # vertical search window

        # Find all words strongly aligned vertically OR horizontally with the type word
        cx = type_word.position.center_x
        cy = type_word.position.center_y

        stacked_words = []
        for w in words:
            if w.page_index != type_word.page_index or w is type_word:
                continue

            dx = w.position.center_x - cx
            dy = w.position.center_y - cy

            # Account for Upright/Portrait (stacked along Y) and Rotated/Landscape (stacked along X)
            align_vert  = abs(dx) < v_tol_x and 0 < dy < v_tol_y   # Directly below
            align_horiz = abs(dy) < h_tol_y and abs(dx) < h_tol_x  # Beside it

            if align_vert or align_horiz:
                stacked_words.append(w)

        if not stacked_words:
            continue

        # Sort by distance to the anchor (the ISA type)
        stacked_words.sort(key=lambda w: type_word.position.distance_to(w.position))

        # Filter to only keep NUMERIC balloon parts (digits, x placeholders, dashes)
        # Reject: ISA types, pure letters, line tags, equipment names
        valid_candidates = []
        for w in stacked_words:
            text = w.text.strip()
            # Must contain at least one digit or 'x'/'X' and be short (balloon numbers are compact)
            if len(text) > 10:
                continue
            # Skip if it's another ISA type
            if text.upper() in ISA_TYPE_DESCRIPTIONS:
                continue
            # Skip lowercase single letters (CAD fragments); allow uppercase (qualifiers A/B/C)
            if re.match(r'^[a-z]$', text):
                continue
            # Accept uppercase single letter qualifiers (e.g. A, B, C, D after number)
            if re.match(r'^[A-Z]$', text):
                valid_candidates.append(w)
                continue
            # Accept: numeric patterns like '057', 'xxx1', '00X2', '0902', etc.
            # Also accept '+' which appears as a font-encoding artifact in CAD-generated PDFs
            # (e.g. "05+1" instead of "051"). The '+' is stripped when building the tag number.
            text_norm = text.replace("+", "")
            if text_norm and re.match(r'^[\dxX][\dxXA-Za-z-]*$', text_norm):
                valid_candidates.append(w)

        # Take ONLY the closest number parts (max 2) with tight chaining
        number_parts = []
        valid_stack = []
        last_word = type_word

        for w in valid_candidates:
            if len(number_parts) >= 3:
                break  # ISA + number + qualifier at most 3 parts
            dist_prev = last_word.position.distance_to(w.position)
            ref_h = max(
                last_word.position.bottom - last_word.position.top,
                w.position.bottom - w.position.top,
                4.0,
            )
            if dist_prev > ref_h * chain_mult:
                break  # Too far = different balloon

            part_text = w.text.strip().replace("+", "")

            # Single uppercase letter is a qualifier — only accept AFTER a number is found
            if re.match(r'^[A-Z]$', part_text) and not number_parts:
                continue

            # If this candidate overlaps or is immediately adjacent (edge-to-edge gap < 1pt)
            # to the previous word, it's a character-level fragment of the same number token
            # (e.g. CAD exports '0' and '5+2' separately for what should be '052').
            # Concatenate left-to-right instead of joining with '-'.
            if number_parts:
                h_gap = w.position.x0 - last_word.position.x1
                v_gap = abs(w.position.center_y - last_word.position.center_y)
                last_h = max(last_word.position.bottom - last_word.position.top, 4.0)
                if h_gap < 1.0 and v_gap < last_h * 0.5:  # same horizontal line (CAD char fragment)
                    if w.position.center_x >= last_word.position.center_x:
                        number_parts[-1] = number_parts[-1] + part_text
                    else:
                        number_parts[-1] = part_text + number_parts[-1]
                    last_word = w
                    continue

            number_parts.append(part_text)
            valid_stack.append(w)
            last_word = w

        if not number_parts:
            continue

        # Deduplicate: PDF balloons often have the same number above AND below the ISA type
        seen = []
        for p in number_parts:
            if p not in seen:
                seen.append(p)
        number_parts = seen

        # Extract trailing single-letter qualifier (e.g. A/B/C/D)
        balloon_qualifier = ""
        if number_parts and re.match(r'^[A-Z]$', number_parts[-1]):
            balloon_qualifier = number_parts.pop()

        tag_number = "-".join(number_parts)

        # Position: ISA type word + first number word only (tight around the balloon)
        box_words = [type_word]
        if valid_stack:
            box_words.append(valid_stack[0])
        x0 = min(w.position.x0 for w in box_words)
        top = min(w.position.top for w in box_words)
        x1 = max(w.position.x1 for w in box_words)
        bottom = max(w.position.bottom for w in box_words)
        pos = Position(x0=x0, top=top, x1=x1, bottom=bottom)

        # Build full tag: ISA_TYPE-NUMBER[QUALIFIER] (e.g. PDI-057, PSV-001A)
        full_tag = f"{isa_type}-{tag_number}{balloon_qualifier}"

        if full_tag in already_found:
            continue
        already_found.add(full_tag)

        instrument = Instrument(
            tag=full_tag,
            isa_type=isa_type,
            isa_description=ISA_TYPE_DESCRIPTIONS.get(isa_type, "Unknown"),
            position=pos,
            page_index=type_word.page_index,
            area="",
            tag_number=tag_number,
            qualifier=balloon_qualifier,
            confidence=0.85,
        )
        instruments.append(instrument)
        logger.debug(f"Balloon stack tag: {full_tag} from '{isa_type}' + {number_parts}")

    return instruments


def _find_area_prefix(
    type_word: ExtractedWord,
    words: List[ExtractedWord],
    scale: Optional[DocumentScale] = None,
    search_radius: Optional[float] = None,
) -> str:
    """Find an area prefix horizontally near an ISA type word."""
    if search_radius is None:
        search_radius = _s(scale, 30.0)
    y_tol = _s(scale, 15.0)

    cx = type_word.position.center_x
    cy = type_word.position.center_y
    for w in words:
        if w.page_index != type_word.page_index:
            continue
        text = w.text.strip()
        if re.match(r'^\d{3}$', text):
            # Only consider elements horizontally aligned
            if abs(w.position.center_y - cy) < y_tol and abs(w.position.center_x - cx) < search_radius:
                return text
    return ""


def _is_part_of_line_tag(
    word: ExtractedWord,
    all_words: List[ExtractedWord],
    scale: Optional[DocumentScale] = None,
) -> bool:
    """Check if an ISA type word is part of a line tag string (e.g. '6"-PR-21231-073-BA-IF').

    Line tags are long hyphenated strings containing pipe specs. If any nearby word
    on the same line looks like a line tag fragment, this ISA word is a false positive.
    """
    cx = word.position.center_x
    cy = word.position.center_y

    # Font-relative tolerances: a pipe-tag fragment adjacent to the ISA type is at most
    # a few characters away, which is proportional to text height — not to page size.
    # x_tol is kept tight (5×) so instruments drawn near-but-separate from a pipe run
    # are not misidentified as part of the line tag.
    word_h = max(word.position.bottom - word.position.top, 4.0)
    y_tol = word_h * 1.5   # same line: within 1.5 text heights vertically
    x_tol = word_h * 5.0   # adjacent in tag: within 5 text heights horizontally

    for w in all_words:
        if w.page_index != word.page_index or w is word:
            continue
        text = w.text.strip()
        # Check if nearby (same line, horizontally close)
        if abs(w.position.center_y - cy) < y_tol and abs(w.position.center_x - cx) < x_tol:
            # Line tag indicators: strings with pipe specs, IF suffixes, PR/HC/BA patterns
            if re.search(r'\d+-[A-Z]{2}-\d{4,}', text):  # e.g. "21231-073"
                return True
            if re.search(r'\d+"-', text):  # e.g. '6"-' pipe size
                return True
            if text.startswith("IF-") or text.endswith("-IF"):  # Insulation flag
                return True
            if re.match(r'^.*-[A-Z]{2}-IF$', text):  # e.g. "BA-IF", "EA-IF"
                return True
    return False


def _detect_furnished_modifier(
    instruments: List[Instrument],
    words: List[ExtractedWord],
    scale: Optional[DocumentScale] = None,
) -> None:
    """Finds words literally matching '(F)' near instruments to flag them as furnished packages.

    Each (F) marker is assigned exclusively to the NEAREST instrument within the
    search radius. This prevents a single (F) from incorrectly flagging multiple
    instruments that happen to lie within range.
    """
    if not instruments:
        return

    # Only match the parenthesised form to avoid false positives from stray "F" letters
    f_words = [w for w in words if w.text.strip().replace(" ", "").upper() == "(F)"]
    if not f_words:
        return

    radius = _s(scale, 45.0)

    # Build a page-indexed dict for fast lookup
    insts_by_page: dict = {}
    for inst in instruments:
        if inst.position:
            insts_by_page.setdefault(inst.page_index, []).append(inst)

    # For each (F) marker, flag only the closest instrument within radius
    for fw in f_words:
        page_insts = insts_by_page.get(fw.page_index, [])
        best_inst = None
        best_dist = radius

        for inst in page_insts:
            dist = inst.position.distance_to(fw.position)
            if dist < best_dist:
                best_dist = dist
                best_inst = inst

        if best_inst is not None:
            best_inst.furnished_by_package = True
            logger.debug(
                f"Detected {best_inst.tag} as Furnished by Package "
                f"('{fw.text}' at dist {best_dist:.1f})"
            )


def _is_likely_instrument_context(
    word: ExtractedWord,
    all_words: List[ExtractedWord],
    scale: Optional[DocumentScale] = None,
) -> bool:
    """Check if a short ISA-like word is likely an instrument tag, not English text.

    Heuristic: if there's a 3-5 digit number nearby, it's likely an instrument.
    """
    radius = _s(scale, 50.0)

    for w in all_words:
        if w.page_index != word.page_index:
            continue
        if w is word:
            continue
        dist = word.position.distance_to(w.position)
        if dist < radius and re.match(r'^\d{3,5}[A-Z]?$', w.text.strip()):
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
    scale: Optional[DocumentScale] = None,
) -> List[Instrument]:
    """Detect tags split across multiple adjacent words on the same line."""
    instruments = []

    sorted_words = sorted(
        words, key=lambda w: (w.page_index, w.position.top, w.position.x0)
    )
    lines = _group_words_into_lines(sorted_words, y_tolerance=_s(scale, 5.0))

    tag_pattern = re.compile(profile["tag_pattern"])
    max_gap = _s(scale, 15.0)

    for line_words in lines:
        if len(line_words) < 2:
            continue

        for start in range(len(line_words)):
            for length in range(2, min(6, len(line_words) - start + 1)):
                window = line_words[start:start + length]

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
