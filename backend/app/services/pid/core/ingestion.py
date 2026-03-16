"""PDF ingestion: load PDFs and detect basic properties."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List

import pdfplumber

logger = logging.getLogger(__name__)


@dataclass
class PageInfo:
    """Basic info about a PDF page."""
    index: int
    width: float
    height: float
    is_landscape: bool
    has_text: bool  # True if vectorial text found (no OCR needed)
    word_count: int


@dataclass
class PDFDocument:
    """A loaded PDF document with its pages."""
    path: Path
    pages: List[PageInfo]
    total_pages: int
    is_vectorial: bool  # True if all pages have embedded text

    @property
    def filename(self) -> str:
        return self.path.name


def load_pdf(pdf_path: str) -> PDFDocument:
    """Load a PDF and extract basic page information.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        PDFDocument with page info.

    Raises:
        FileNotFoundError: If the PDF file doesn't exist.
        ValueError: If the file is not a valid PDF.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF file: {pdf_path}")

    pages = []
    with pdfplumber.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages):
            words = page.extract_words()
            word_count = len(words)
            has_text = word_count > 0

            page_info = PageInfo(
                index=i,
                width=float(page.width),
                height=float(page.height),
                is_landscape=page.width > page.height,
                has_text=has_text,
                word_count=word_count,
            )
            pages.append(page_info)
            logger.debug(
                f"Page {i}: {page_info.width}x{page_info.height}, "
                f"{word_count} words, landscape={page_info.is_landscape}"
            )

    is_vectorial = all(p.has_text for p in pages)
    if not is_vectorial:
        scan_pages = [p.index for p in pages if not p.has_text]
        logger.warning(
            f"Pages without embedded text (may need OCR): {scan_pages}"
        )

    doc = PDFDocument(
        path=path,
        pages=pages,
        total_pages=len(pages),
        is_vectorial=is_vectorial,
    )
    logger.info(
        f"Loaded {doc.filename}: {doc.total_pages} pages, "
        f"vectorial={doc.is_vectorial}"
    )
    return doc


def discover_pdfs(folder_path: str) -> List[Path]:
    """Find all PDF files in a folder.

    Args:
        folder_path: Path to folder containing PDFs.

    Returns:
        Sorted list of PDF file paths.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder_path}")

    pdfs = sorted(folder.glob("*.pdf"))
    logger.info(f"Found {len(pdfs)} PDF files in {folder_path}")
    return pdfs
