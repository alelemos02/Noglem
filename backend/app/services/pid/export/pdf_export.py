"""Export highlighted PDFs with bounding boxes for verified instruments using PyMuPDF (fitz) for vector quality."""

import logging
from pathlib import Path
import fitz  # PyMuPDF

from app.services.pid.models.instrument import ExtractionResult

logger = logging.getLogger(__name__)


def export_highlighted_pdf(
    input_pdf_path: str,
    output_pdf_path: str,
    result: ExtractionResult,
) -> str:
    """Generate a vector copy of the PDF with highlighted instruments and equipment.

    This retains the original vector quality and adds vector rectangles.

    Args:
        input_pdf_path: Original PDF.
        output_pdf_path: Path to save marked PDF.
        result: The extraction result containing positions.

    Returns:
        Absolute path to the created marked PDF.
    """
    path = Path(output_pdf_path)
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    try:
        doc = fitz.open(input_pdf_path)
    except Exception as e:
        logger.error(f"Failed to open {input_pdf_path} for highlighting: {e}")
        return ""

    _annotate_document(doc, input_pdf_path, result)

    doc.save(str(path))
    doc.close()

    absolute_path = str(path.absolute())
    logger.info(f"Marked Vector PDF exported to {absolute_path}")
    return absolute_path


def export_highlighted_pdf_bundle(
    input_pdf_paths: list[str],
    output_pdf_path: str,
    result: ExtractionResult,
) -> str:
    """Generate one marked PDF containing all input PDFs in order."""
    path = Path(output_pdf_path)
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    output_doc = fitz.open()
    try:
        for input_pdf_path in input_pdf_paths:
            try:
                doc = fitz.open(input_pdf_path)
            except Exception as e:
                logger.error(f"Failed to open {input_pdf_path} for highlighting: {e}")
                continue

            _annotate_document(doc, input_pdf_path, result)
            output_doc.insert_pdf(doc)
            doc.close()

        if len(output_doc) == 0:
            logger.error("No PDF pages available for bundled highlighted export")
            output_doc.close()
            return ""

        output_doc.save(str(path))
    finally:
        try:
            output_doc.close()
        except Exception:
            pass

    absolute_path = str(path.absolute())
    logger.info(f"Bundled marked Vector PDF exported to {absolute_path}")
    return absolute_path


def _annotate_document(doc: fitz.Document, input_pdf_path: str, result: ExtractionResult) -> None:
    input_source = str(Path(input_pdf_path).resolve())

    # Group instruments by page. When a batch has many PDFs, keep only
    # detections from this specific source file to avoid page-index collisions.
    instruments_by_page = {}
    for inst in result.instruments:
        if inst.position is None:
            continue
        if getattr(inst, "source_pdf", "") and inst.source_pdf != input_source:
            continue
        page_idx = inst.page_index
        if page_idx not in instruments_by_page:
            instruments_by_page[page_idx] = []
        instruments_by_page[page_idx].append(inst)

    # Group equipment by page
    equipment_by_page = {}
    for eq in result.equipment:
        if eq.position is None:
            continue
        if getattr(eq, "source_pdf", "") and eq.source_pdf != input_source:
            continue
        page_idx = eq.page_index
        if page_idx not in equipment_by_page:
            equipment_by_page[page_idx] = []
        equipment_by_page[page_idx].append(eq)

    # Draw annotations
    for page_idx in range(len(doc)):
        page = doc[page_idx]

        # Equipments (Blue)
        for eq in equipment_by_page.get(page_idx, []):
            margin = 5
            rect = fitz.Rect(
                eq.position.x0 - margin,
                eq.position.top - margin,
                eq.position.x1 + margin,
                eq.position.bottom + margin,
            )
            if page.rotation != 0:
                rect = rect * page.derotation_matrix

            annot = page.add_rect_annot(rect)
            annot.set_colors(stroke=(0.0, 0.0, 1.0), fill=None)
            annot.set_border(width=1.5, dashes=[3, 3])
            annot.update()

        # Instruments (Yellow for Field, Red for DCS/Control Room, Orange for low confidence)
        # Skip near-zero confidence: likely non-instrument symbols (diamonds, etc.)
        for inst in instruments_by_page.get(page_idx, []):
            if inst.confidence < 0.15:
                continue
            inst_h = max(inst.position.bottom - inst.position.top, 2.0)
            margin = max(min(inst_h * 1.2, 12.0), 4.0)
            rect = fitz.Rect(
                inst.position.x0 - margin,
                inst.position.top - margin,
                inst.position.x1 + margin,
                inst.position.bottom + margin,
            )
            if page.rotation != 0:
                rect = rect * page.derotation_matrix

            if getattr(inst, "furnished_by_package", False):
                stroke_color = (0.0, 0.0, 1.0)
                fill_color = (0.6, 0.8, 1.0)
            elif inst.is_physical:
                stroke_color = (1.0, 0.85, 0.0)
                fill_color = (1.0, 1.0, 0.0)
            else:
                stroke_color = (1.0, 0.0, 0.0)
                fill_color = (1.0, 0.6, 0.6)

            if inst.confidence < 0.5:
                stroke_color = (1.0, 0.5, 0.0)
                fill_color = (1.0, 0.8, 0.5)

            annot = page.add_rect_annot(rect)
            annot.set_colors(stroke=stroke_color, fill=fill_color)
            annot.set_opacity(0.35)
            annot.set_border(width=1.5)
            annot.update()
