"""Service wrapper for PID Instrument Extractor pipeline."""

import logging
from pathlib import Path
from typing import Any, Dict, List

from app.services.pid.core.ingestion import discover_pdfs, load_pdf
from app.services.pid.core.text_extraction import extract_words
from app.services.pid.core.tag_detector import detect_tags, load_profile
from app.services.pid.core.title_block import parse_title_block
from app.services.pid.core.notes_parser import parse_notes
from app.services.pid.core.spatial_engine import (
    associate_instruments_to_equipment,
    detect_equipment,
)
from app.services.pid.core.loop_builder import build_loops
from app.services.pid.core.hierarchy import build_hierarchy
from app.services.pid.core.cross_sheet import reconcile_cross_sheets
from app.services.pid.core.validator import validate
from app.services.pid.export.excel_export import export_to_excel
from app.services.pid.models.instrument import ExtractionResult

logger = logging.getLogger(__name__)

# Path to the bundled config
CONFIG_PATH = str(Path(__file__).parent / "pid" / "config" / "tag_profiles.yaml")


class PidExtractService:
    """Extracts instrument tags from P&ID PDFs."""

    def extract(
        self, pdf_path: str, profile_name: str = "promon", max_distance: float = 200.0
    ) -> ExtractionResult:
        """Run the full extraction pipeline on a PDF file.

        Args:
            pdf_path: Path to the PDF file.
            profile_name: Tag profile name (promon, technip).
            max_distance: Max distance for instrument-equipment association.

        Returns:
            ExtractionResult with all extracted data.
        """
        tag_profile = load_profile(CONFIG_PATH, profile_name)

        result = ExtractionResult()
        self._process_single_pdf(pdf_path, tag_profile, max_distance, result)

        if result.instruments:
            reconcile_cross_sheets(result)
            result.loops = build_loops(result.instruments)
            build_hierarchy(result.instruments)
            validate(result)

        return result

    def extract_to_json(
        self, pdf_path: str, profile_name: str = "promon", max_distance: float = 200.0
    ) -> Dict[str, Any]:
        """Extract and return a JSON-serializable summary."""
        result = self.extract(pdf_path, profile_name, max_distance)
        return self._result_to_dict(result)

    def extract_to_excel(
        self,
        pdf_path: str,
        output_path: str,
        profile_name: str = "promon",
        max_distance: float = 200.0,
    ) -> str:
        """Extract and export to Excel."""
        result = self.extract(pdf_path, profile_name, max_distance)
        return export_to_excel(result, output_path)

    def extract_to_annotated_pdf(
        self,
        pdf_path: str,
        output_path: str,
        profile_name: str = "promon",
        max_distance: float = 200.0,
    ) -> str:
        """Extract instruments and save annotated PDF with yellow circles on each tag."""
        import fitz  # PyMuPDF

        result = self.extract(pdf_path, profile_name, max_distance)

        # Group instruments by page
        instruments_by_page: Dict[int, list] = {}
        for inst in result.instruments:
            if inst.position:
                instruments_by_page.setdefault(inst.page_index, []).append(inst)

        doc = fitz.open(pdf_path)
        yellow = (234 / 255, 179 / 255, 8 / 255)  # #EAB308

        for page_idx, page_instruments in instruments_by_page.items():
            if page_idx >= len(doc):
                continue
            page = doc[page_idx]
            # pdfplumber gives coords in the visual (rotated) space,
            # but fitz Shape draws in the un-rotated PDF space.
            # Use derotation_matrix to convert when page has rotation.
            derotation = page.derotation_matrix if page.rotation != 0 else None

            for inst in page_instruments:
                pos = inst.position
                cx = (pos.x0 + pos.x1) / 2
                cy = (pos.top + pos.bottom) / 2
                # Dynamic radius: proportional to the bounding box of the
                # detected text, so it scales automatically with any
                # document size / font size.  Uses 60% of the bbox height.
                bbox_h = pos.bottom - pos.top
                bbox_w = pos.x1 - pos.x0
                radius = max(bbox_h, bbox_w) * 0.6
                radius = max(radius, 2.0)  # minimum 2pt to stay visible

                point = fitz.Point(cx, cy)
                if derotation:
                    point = point * derotation

                shape = page.new_shape()
                shape.draw_circle(point, radius)
                shape.finish(color=yellow, fill=yellow, fill_opacity=0.6, width=1)
                shape.commit()

        doc.save(output_path)
        doc.close()
        return output_path

    def _process_single_pdf(
        self,
        pdf_path: str,
        profile: dict,
        max_distance: float,
        result: ExtractionResult,
    ) -> None:
        doc = load_pdf(pdf_path)

        if not doc.is_vectorial:
            logger.warning(f"{doc.filename}: Contains scanned pages, skipping non-text pages.")

        merge_settings = profile.get("word_merge", {})
        merge_gap_x = merge_settings.get("max_horizontal_gap", 5.0)
        merge_gap_y = merge_settings.get("max_vertical_gap", 3.0)

        for page_info in doc.pages:
            if not page_info.has_text:
                continue

            page_idx = page_info.index

            words = extract_words(
                pdf_path,
                page_indices=[page_idx],
                merge_gap_x=merge_gap_x,
                merge_gap_y=merge_gap_y,
            )

            if not words:
                continue

            metadata = parse_title_block(words, page_info.width, page_info.height, page_idx)
            metadata.sheet_number = str(page_idx + 1)
            result.metadata.append(metadata)

            notes = parse_notes(words, page_info.width, page_info.height)
            result.notes.extend(notes)

            instruments, line_numbers = detect_tags(words, profile)
            result.line_numbers.extend(line_numbers)

            for inst in instruments:
                inst.sheet_name = metadata.document_number or f"Page {page_idx + 1}"

            for note in notes:
                if note.affects_instruments:
                    for inst in instruments:
                        if not note.affected_types or inst.isa_type in note.affected_types:
                            inst.notes.append(f"Note {note.number}: {note.text[:100]}")

            equipment = detect_equipment(words, instruments)
            associate_instruments_to_equipment(instruments, equipment, max_distance)

            result.instruments.extend(instruments)
            result.equipment.extend(equipment)

            logger.debug(
                f"Page {page_idx + 1}: {len(instruments)} instruments, "
                f"{len(equipment)} equipment, {len(line_numbers)} lines"
            )

    @staticmethod
    def _result_to_dict(result: ExtractionResult) -> Dict[str, Any]:
        instruments = []
        for inst in sorted(
            result.instruments,
            key=lambda i: (i.area or "", i.isa_type, i.tag_number or "", i.qualifier),
        ):
            instruments.append({
                "tag": inst.tag,
                "isa_type": inst.isa_type,
                "description": inst.isa_description,
                "area": inst.area,
                "tag_number": inst.tag_number,
                "qualifier": inst.qualifier,
                "equipment": inst.equipment_ref,
                "loop_id": inst.loop_id,
                "line_number": inst.line_number,
                "sheet": inst.sheet_name or str(inst.page_index + 1),
                "confidence": inst.confidence,
            })

        loops = []
        for loop in sorted(result.loops, key=lambda l: l.loop_id):
            loops.append({
                "loop_id": loop.loop_id,
                "instruments": loop.instruments,
                "is_complete": loop.is_complete,
                "missing": loop.missing,
            })

        return {
            "total_instruments": len(result.instruments),
            "total_equipment": len(result.equipment),
            "total_loops": len(result.loops),
            "total_warnings": len(result.warnings),
            "total_errors": len(result.errors),
            "instruments": instruments,
            "loops": loops,
            "warnings": result.warnings,
            "errors": result.errors,
        }
