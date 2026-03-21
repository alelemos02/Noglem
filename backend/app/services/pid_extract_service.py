"""Service wrapper for PID Instrument Extractor pipeline."""

import logging
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image, ImageDraw
from pdf2image import convert_from_path

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
        """Extract instruments and save annotated PDF with yellow circles.

        Uses image-based rendering (pdf2image + Pillow) to guarantee correct
        circle placement regardless of page rotation or coordinate quirks.
        Each page is rasterised, annotated, and assembled into a new PDF.
        """
        import fitz  # PyMuPDF – used only to assemble the output PDF

        result = self.extract(pdf_path, profile_name, max_distance)

        # Group instruments by page
        instruments_by_page: Dict[int, list] = {}
        for inst in result.instruments:
            if inst.position:
                instruments_by_page.setdefault(inst.page_index, []).append(inst)

        dpi = 150
        scale = dpi / 72.0
        # Semi-transparent yellow  (#EAB308 @ 60 %)
        fill_color = (234, 179, 8, 153)
        outline_color = (200, 150, 0, 220)

        source_doc = load_pdf(pdf_path)
        output_doc = fitz.open()

        for page_info in source_doc.pages:
            idx = page_info.index

            # Render page to image (handles rotation automatically)
            page_images = convert_from_path(
                pdf_path, dpi=dpi,
                first_page=idx + 1, last_page=idx + 1,
            )
            if not page_images:
                continue

            img = page_images[0].convert("RGBA")
            page_instruments = instruments_by_page.get(idx, [])

            if page_instruments:
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(overlay)

                for inst in page_instruments:
                    pos = inst.position
                    cx = (pos.x0 + pos.x1) / 2 * scale
                    cy = (pos.top + pos.bottom) / 2 * scale
                    # Radius from text height – scales with document/font size
                    bbox_h = (pos.bottom - pos.top) * scale
                    radius = bbox_h * 0.45
                    radius = max(radius, 3.0)   # minimum visible
                    radius = min(radius, 20.0)  # cap to avoid huge circles

                    draw.ellipse(
                        [cx - radius, cy - radius, cx + radius, cy + radius],
                        fill=fill_color,
                        outline=outline_color,
                        width=2,
                    )

                img = Image.alpha_composite(img, overlay)

            # Convert to RGB JPEG bytes and add as a PDF page
            img_rgb = img.convert("RGB")
            buf = BytesIO()
            img_rgb.save(buf, format="JPEG", quality=85)
            img_bytes = buf.getvalue()
            buf.close()

            # Page size in PDF points (same visual dimensions as original)
            w_pt = img_rgb.width * 72.0 / dpi
            h_pt = img_rgb.height * 72.0 / dpi
            page = output_doc.new_page(width=w_pt, height=h_pt)
            page.insert_image(page.rect, stream=img_bytes)

            # Free memory
            del img, img_rgb, page_images

        output_doc.save(output_path)
        output_doc.close()
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
