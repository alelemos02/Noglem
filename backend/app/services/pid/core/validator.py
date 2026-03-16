"""Validate extraction results: orphans, loop completeness, duplicates, ISA consistency."""

import logging
from collections import Counter
from typing import List

from app.services.pid.models.instrument import ExtractionResult, Instrument, Loop

logger = logging.getLogger(__name__)


def validate(result: ExtractionResult) -> None:
    """Run all validation checks and populate warnings/errors.

    Modifies result in place by adding to warnings and errors lists.

    Args:
        result: Extraction result to validate.
    """
    result.warnings = []
    result.errors = []

    _check_orphan_instruments(result)
    _check_duplicate_tags(result)
    _check_loop_completeness(result)
    _check_isa_consistency(result)
    _check_low_confidence(result)

    logger.info(
        f"Validation: {len(result.warnings)} warnings, "
        f"{len(result.errors)} errors"
    )


def _check_orphan_instruments(result: ExtractionResult) -> None:
    """Flag instruments not associated with any equipment."""
    for inst in result.instruments:
        if not inst.equipment_ref and inst.isa_type not in ("PSV", "SDV", "BDV"):
            result.warnings.append(
                f"ORPHAN: {inst.tag} ({inst.isa_description}) has no equipment association "
                f"[page {inst.page_index + 1}]"
            )


def _check_duplicate_tags(result: ExtractionResult) -> None:
    """Detect duplicate tags (may be cross-references or errors)."""
    tag_counts = Counter(inst.tag for inst in result.instruments)
    for tag, count in tag_counts.items():
        if count > 1:
            pages = [
                str(inst.page_index + 1)
                for inst in result.instruments
                if inst.tag == tag
            ]
            sources = [
                inst.source
                for inst in result.instruments
                if inst.tag == tag
            ]

            if all(s == "cross-reference" for s in sources[1:]):
                result.warnings.append(
                    f"CROSS-REF: {tag} appears on pages {', '.join(pages)} "
                    f"(cross-reference detected)"
                )
            else:
                result.errors.append(
                    f"DUPLICATE: {tag} appears {count} times on pages "
                    f"{', '.join(pages)}"
                )


def _check_loop_completeness(result: ExtractionResult) -> None:
    """Check if loops have all expected instruments."""
    for loop in result.loops:
        if not loop.is_complete and loop.missing:
            result.warnings.append(
                f"INCOMPLETE LOOP: Loop {loop.loop_id} is missing: "
                f"{', '.join(loop.missing)}. "
                f"Has: {', '.join(loop.instruments)}"
            )


def _check_isa_consistency(result: ExtractionResult) -> None:
    """Check ISA type consistency rules."""
    # Rule: Transmitters should typically have a corresponding indicator or controller
    transmitters = [
        inst for inst in result.instruments
        if inst.isa_type.endswith("T") and len(inst.isa_type) >= 2
        and inst.isa_type not in ("AT",)  # Exclude ambiguous types
    ]

    for tx in transmitters:
        first_letter = tx.isa_type[0]
        expected_types = {
            f"{first_letter}I",   # Indicator
            f"{first_letter}IC",  # Indicating Controller
            f"{first_letter}C",   # Controller
            f"{first_letter}R",   # Recorder
        }

        # Check if any related instrument exists in the same loop
        if tx.loop_id:
            loop_instruments = [
                inst for inst in result.instruments
                if inst.loop_id == tx.loop_id and inst.tag != tx.tag
            ]
            loop_types = {inst.isa_type for inst in loop_instruments}
            if not loop_types & expected_types:
                result.warnings.append(
                    f"ISA CHECK: Transmitter {tx.tag} ({tx.isa_type}) "
                    f"has no indicator/controller in loop {tx.loop_id}"
                )


def _check_low_confidence(result: ExtractionResult) -> None:
    """Flag instruments with low confidence scores."""
    for inst in result.instruments:
        if inst.confidence < 0.5:
            result.warnings.append(
                f"LOW CONFIDENCE: {inst.tag} ({inst.isa_description}) "
                f"confidence={inst.confidence:.2f} [page {inst.page_index + 1}]"
            )
