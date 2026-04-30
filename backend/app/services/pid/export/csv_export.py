"""Export extraction results to CSV."""

import csv
import logging
from pathlib import Path

from app.services.pid.models.instrument import ExtractionResult

logger = logging.getLogger(__name__)


def export_to_csv(result: ExtractionResult, output_path: str) -> str:
    """Export instrument list to a CSV file.

    Args:
        result: Extraction result to export.
        output_path: Path for the output .csv file.

    Returns:
        Absolute path to the created file.
    """
    path = Path(output_path)

    headers = [
        "Tag Number",
        "ISA Type",
        "Description",
        "Symbol",
        "Classification",
        "Physical?",
        "Furnished by Package?",
        "Area",
        "Tag Number (Num)",
        "Qualifier",
        "Loop ID",
        "Sheet",
        "Source PDF",
        "Confidence",
        "Notes",
    ]

    sorted_instruments = sorted(
        result.instruments,
        key=lambda i: (i.area or "", i.isa_type, i.tag_number or "", i.qualifier),
    )

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for inst in sorted_instruments:
            writer.writerow([
                inst.tag,
                inst.isa_type,
                inst.isa_description,
                inst.symbol,
                inst.classification,
                "Yes" if inst.is_physical else "No",
                "Yes" if getattr(inst, "furnished_by_package", False) else "No",
                inst.area,
                inst.tag_number,
                inst.qualifier,
                inst.loop_id,
                inst.sheet_name or str(inst.page_index + 1),
                Path(getattr(inst, "source_pdf", "")).name if getattr(inst, "source_pdf", "") else "",
                f"{inst.confidence:.0%}",
                "; ".join(inst.notes) if inst.notes else "",
            ])

    logger.info(f"CSV exported to {path.absolute()}")
    return str(path.absolute())
