"""Service wrapper for PID Instrument Extractor pipeline."""

import logging
from pathlib import Path
from typing import Any, Dict

import fitz  # PyMuPDF
import pdfplumber

from app.services.pid.core.ingestion import load_pdf
from app.services.pid.core.text_extraction import extract_words
from app.services.pid.core.tag_detector import detect_tags, load_profile
from app.services.pid.core.title_block import parse_title_block
from app.services.pid.core.notes_parser import parse_notes
from app.services.pid.core.spatial_engine import (
    associate_instruments_to_equipment,
    detect_equipment,
)
from app.services.pid.core.symbol_detector import classify_instruments
from app.services.pid.core.loop_builder import build_loops
from app.services.pid.core.hierarchy import build_hierarchy
from app.services.pid.core.cross_sheet import reconcile_cross_sheets
from app.services.pid.core.validator import validate
from app.services.pid.export.excel_export import export_to_excel
from app.services.pid.export.pdf_export import export_highlighted_pdf
from app.services.pid.models.instrument import ExtractionResult

logger = logging.getLogger(__name__)

CONFIG_PATH = str(Path(__file__).parent / "pid" / "config" / "tag_profiles.yaml")


class PidExtractService:
    """Extracts instrument tags from P&ID PDFs."""

    def extract(
        self,
        pdf_path: str,
        profile_name: str = "promon",
        max_distance: float = 200.0,
        use_llm: bool = False,
    ) -> ExtractionResult:
        """Run the full extraction pipeline on a PDF file."""
        tag_profile = load_profile(CONFIG_PATH, profile_name)

        result = ExtractionResult()
        self._process_single_pdf(pdf_path, tag_profile, max_distance, result)

        if result.instruments:
            reconcile_cross_sheets(result)
            result.loops = build_loops(result.instruments)
            build_hierarchy(result.instruments, page_scales=result.page_scales)
            validate(result)

            if use_llm:
                from app.services.pid.core.llm_validator import validate_with_llm
                validate_with_llm(result)

        return result

    def extract_to_json(
        self,
        pdf_path: str,
        profile_name: str = "promon",
        max_distance: float = 200.0,
        use_llm: bool = False,
    ) -> Dict[str, Any]:
        """Extract and return a JSON-serializable summary."""
        result = self.extract(pdf_path, profile_name, max_distance, use_llm=use_llm)
        return self._result_to_dict(result)

    def extract_to_excel(
        self,
        pdf_path: str,
        output_path: str,
        profile_name: str = "promon",
        max_distance: float = 200.0,
        use_llm: bool = False,
    ) -> str:
        """Extract and export to Excel."""
        result = self.extract(pdf_path, profile_name, max_distance, use_llm=use_llm)
        return export_to_excel(result, output_path)

    def extract_to_annotated_pdf(
        self,
        pdf_path: str,
        output_path: str,
        profile_name: str = "promon",
        max_distance: float = 200.0,
        use_llm: bool = False,
    ) -> str:
        """Extract instruments and save annotated vector PDF.

        Color coding: yellow=field, red=DCS, blue=furnished, orange=low confidence.
        """
        result = self.extract(pdf_path, profile_name, max_distance, use_llm=use_llm)
        return export_highlighted_pdf(pdf_path, output_path, result)

    def _process_single_pdf(
        self,
        pdf_path: str,
        profile: dict,
        max_distance: float,
        result: ExtractionResult,
    ) -> None:
        pdf_file = Path(pdf_path)
        doc = load_pdf(str(pdf_file))

        if not any(page.has_text for page in doc.pages):
            logger.warning("%s: PDF sem texto vetorial. OCR ainda não está habilitado.", doc.filename)
            return

        merge_settings = profile.get("word_merge", {})
        source_pdf = str(pdf_file.resolve())

        for page_info in doc.pages:
            if not page_info.has_text:
                logger.warning("%s página %s sem texto vetorial; ignorada", doc.filename, page_info.index + 1)
                continue

            page_idx = page_info.index

            # Scale context derived from actual page dimensions
            scale = page_info.document_scale
            result.page_scales[(source_pdf, page_idx)] = scale

            words = extract_words(
                str(pdf_file),
                page_indices=[page_idx],
                merge_gap_x=scale.px(merge_settings.get("max_horizontal_gap", 5.0)),
                merge_gap_y=scale.px(merge_settings.get("max_vertical_gap", 3.0)),
            )

            if not words:
                continue

            metadata = parse_title_block(words, page_info.width, page_info.height, page_idx, scale=scale)
            metadata.sheet_number = metadata.sheet_number or str(page_idx + 1)
            result.metadata.append(metadata)

            notes = parse_notes(words, page_info.width, page_info.height, scale=scale)
            result.notes.extend(notes)

            instruments, line_numbers = detect_tags(words, profile, scale=scale)

            for inst in instruments:
                inst.sheet_name = metadata.document_number or f"{pdf_file.stem} p.{page_idx + 1}"
                inst.source_pdf = source_pdf

            for line in line_numbers:
                result.line_numbers.append(line)

            for note in notes:
                if note.affects_instruments:
                    for inst in instruments:
                        if not note.affected_types or inst.isa_type in note.affected_types:
                            inst.notes.append(f"Note {note.number}: {note.text[:100]}")

            equipment = detect_equipment(words, instruments, scale=scale, profile=profile)
            for eq in equipment:
                eq.source_pdf = source_pdf

            spatial_cfg = profile.get("spatial", {})
            effective_max_distance = scale.px(spatial_cfg.get("tag_equipment_max_distance", max_distance))
            associate_instruments_to_equipment(instruments, equipment, effective_max_distance)

            fitz_rects = self._extract_rectangles_with_fitz(pdf_file, page_idx)
            with pdfplumber.open(str(pdf_file)) as pdf_sym:
                sym_page = pdf_sym.pages[page_idx]
                page_rects = (sym_page.rects or []) + fitz_rects
                scale.auto_calibrate(page_rects)
                classify_instruments(
                    instruments,
                    sym_page.edges or [],
                    page_rects=page_rects,
                    page_lines=sym_page.lines or [],
                    scale=scale,
                    profile=profile,
                )

            result.instruments.extend(instruments)
            result.equipment.extend(equipment)

            logger.debug(
                f"Page {page_idx + 1}: {len(instruments)} instruments, "
                f"{len(equipment)} equipment, {len(line_numbers)} lines"
            )

    @staticmethod
    def _extract_rectangles_with_fitz(pdf_path: Path, page_idx: int) -> list[dict]:
        rects: list[dict] = []
        try:
            doc = fitz.open(str(pdf_path))
            page = doc[page_idx]
            for drawing in page.get_drawings():
                items = drawing.get("items", [])
                if not items or not any(item[0] in ("re", "qu") for item in items):
                    continue
                rect = drawing["rect"]
                width = rect.x1 - rect.x0
                height = rect.y1 - rect.y0
                if width > 0.5 and height > 0.5 and 0.6 < width / height < 1.7:
                    rects.append({"x0": rect.x0, "top": rect.y0, "x1": rect.x1, "bottom": rect.y1})
            doc.close()
        except Exception as exc:
            logger.debug("fitz rectangle extraction skipped: %s", exc)
        return rects

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
                "symbol": inst.symbol,
                "classification": inst.classification,
                "is_physical": inst.is_physical,
                "furnished_by_package": inst.furnished_by_package,
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

        line_numbers = []
        for ln in result.line_numbers:
            line_numbers.append({
                "full_tag": ln.full_tag,
                "diameter": ln.diameter,
                "spec_class": ln.spec_class,
                "line_id": ln.line_id,
                "service_code": ln.service_code,
            })

        notes = []
        for note in result.notes:
            notes.append({
                "number": note.number,
                "text": note.text,
                "affects_instruments": note.affects_instruments,
            })

        metadata = []
        for meta in result.metadata:
            metadata.append({
                "document_number": meta.document_number,
                "revision": meta.revision,
                "title": meta.title,
                "area": meta.area,
                "sheet_number": meta.sheet_number,
                "date": meta.date,
            })

        return {
            "total_instruments": len(result.instruments),
            "total_equipment": len(result.equipment),
            "total_loops": len(result.loops),
            "total_line_numbers": len(result.line_numbers),
            "total_warnings": len(result.warnings),
            "total_errors": len(result.errors),
            "instruments": instruments,
            "loops": loops,
            "line_numbers": line_numbers,
            "notes": notes,
            "metadata": metadata,
            "warnings": result.warnings,
            "errors": result.errors,
        }
