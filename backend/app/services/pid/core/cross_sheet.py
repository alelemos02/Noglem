"""Cross-sheet reconciliation: resolve references between P&ID sheets."""

import logging
import re
from collections import defaultdict
from typing import Dict, List, Tuple

from app.services.pid.models.instrument import ExtractionResult, Instrument

logger = logging.getLogger(__name__)

CROSS_REF_PATTERNS = [
    re.compile(r'(W\d{3})-(\d{2})\s*(\d{9}(?:\.\d{3})?)'),
    re.compile(r'(?:SEE|VER)\s+(?:SHEET|FOLHA|DRAWING|DESENHO)\s+(\S+)', re.IGNORECASE),
    re.compile(r'(?:CONT|FROM|TO|DE|PARA)\s+(?:SHEET|FOLHA)\s+(\S+)', re.IGNORECASE),
]


def reconcile_cross_sheets(result: ExtractionResult) -> None:
    """Reconcile instruments across multiple sheets.

    Modifies result in place.
    """
    if not result.instruments:
        return

    by_tag: Dict[str, List[Instrument]] = defaultdict(list)
    for inst in by_tag_group(result.instruments):
        by_tag[inst.tag].append(inst)

    duplicates_resolved = 0
    for tag, instances in by_tag.items():
        if len(instances) <= 1:
            continue

        primary = _select_primary(instances)
        primary.source = "primary"

        for inst in instances:
            if inst is not primary:
                inst.source = "cross-reference"
                duplicates_resolved += 1

    primary_instruments = [
        inst for inst in result.instruments if inst.source == "primary"
    ]
    cross_refs = [
        inst for inst in result.instruments if inst.source == "cross-reference"
    ]

    result.instruments = primary_instruments

    if duplicates_resolved > 0:
        logger.info(
            f"Cross-sheet reconciliation: resolved {duplicates_resolved} "
            f"duplicate tags ({len(cross_refs)} cross-references removed)"
        )


def by_tag_group(instruments: List[Instrument]) -> List[Instrument]:
    """Return instruments sorted for grouping by tag."""
    return sorted(instruments, key=lambda i: i.tag)


def _select_primary(instances: List[Instrument]) -> Instrument:
    """Select the primary instance from duplicates."""
    def richness_score(inst: Instrument) -> float:
        score = inst.confidence
        if inst.equipment_ref:
            score += 1.0
        if inst.loop_id:
            score += 0.5
        if inst.line_number:
            score += 0.3
        if inst.children_tags:
            score += 0.2 * len(inst.children_tags)
        return score

    return max(instances, key=richness_score)


def detect_cross_references(
    words_by_page: Dict[int, list],
) -> Dict[int, List[Tuple[str, str]]]:
    """Detect cross-sheet reference annotations in the drawing."""
    refs = {}
    for page_idx, words in words_by_page.items():
        page_text = " ".join(w.text for w in words)
        page_refs = []

        for pattern in CROSS_REF_PATTERNS:
            for match in pattern.finditer(page_text):
                groups = match.groups()
                ref_label = groups[0] if groups else match.group(0)
                doc_number = groups[-1] if len(groups) > 1 else ""
                page_refs.append((ref_label, doc_number))

        if page_refs:
            refs[page_idx] = page_refs
            logger.debug(f"Page {page_idx}: found {len(page_refs)} cross-references")

    return refs
