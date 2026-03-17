"""Structure-aware text chunker for PATEC engineering documents.

Splits texto_extraido (produced by text_extractor.py) into chunks that respect:
- Page boundaries (--- Pagina N ---)
- Table blocks ([Tabela - Pagina N]) kept as atomic units
- Configurable chunk size with overlap for prose text

Designed for technical engineering documents with TAGs, specifications, and tables.
"""

import re
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class Chunk:
    conteudo: str
    page_number: int | None
    chunk_index: int
    chunk_type: str  # "text" or "table"


# Regex to split on page boundaries: "--- Pagina N ---"
PAGE_SPLIT_RE = re.compile(r"--- Pagina (\d+) ---")

# Regex to identify table blocks: "[Tabela - Pagina N]"
TABLE_BLOCK_RE = re.compile(
    r"\[Tabela - Pagina \d+\]\n(.*?)(?=\n\[Tabela - Pagina |\n--- Pagina |\Z)",
    re.DOTALL,
)

# Full table marker with content
TABLE_MARKER_RE = re.compile(
    r"(\[Tabela - Pagina \d+\]\n.*?)(?=\n\[Tabela - Pagina |\n--- Pagina |\Z)",
    re.DOTALL,
)


def chunk_text(texto_extraido: str) -> list[Chunk]:
    """Split extracted text into structured chunks.

    Args:
        texto_extraido: Full extracted text with page/table markers from text_extractor.

    Returns:
        List of Chunk objects with content, page number, index, and type.
    """
    if not texto_extraido or not texto_extraido.strip():
        return []

    chunk_size = settings.RAG_CHUNK_SIZE
    chunk_overlap = settings.RAG_CHUNK_OVERLAP
    max_table_chunk = chunk_size * 2  # tables can be larger before splitting

    chunks: list[Chunk] = []
    chunk_idx = 0

    # Split into pages
    pages = _split_into_pages(texto_extraido)

    for page_num, page_content in pages:
        # Separate tables and text within this page
        tables, text_parts = _separate_tables_and_text(page_content)

        # Process table blocks as atomic chunks
        for table_text in tables:
            if len(table_text) <= max_table_chunk:
                chunks.append(Chunk(
                    conteudo=table_text.strip(),
                    page_number=page_num,
                    chunk_index=chunk_idx,
                    chunk_type="table",
                ))
                chunk_idx += 1
            else:
                # Split very large tables at row boundaries
                table_chunks = _split_large_table(table_text, chunk_size, chunk_overlap)
                for tc in table_chunks:
                    chunks.append(Chunk(
                        conteudo=tc.strip(),
                        page_number=page_num,
                        chunk_index=chunk_idx,
                        chunk_type="table",
                    ))
                    chunk_idx += 1

        # Process prose text with recursive splitting
        combined_text = "\n".join(t.strip() for t in text_parts if t.strip())
        if combined_text:
            text_chunks = _recursive_split(combined_text, chunk_size, chunk_overlap)
            for tc in text_chunks:
                chunks.append(Chunk(
                    conteudo=tc.strip(),
                    page_number=page_num,
                    chunk_index=chunk_idx,
                    chunk_type="text",
                ))
                chunk_idx += 1

    return chunks


def _split_into_pages(text: str) -> list[tuple[int | None, str]]:
    """Split text by page markers. Returns list of (page_number, content)."""
    parts = PAGE_SPLIT_RE.split(text)

    pages: list[tuple[int | None, str]] = []

    # If text starts before any page marker, capture it as page None
    if parts[0].strip():
        pages.append((None, parts[0]))

    # parts alternates: [pre_text, page_num, content, page_num, content, ...]
    for i in range(1, len(parts), 2):
        page_num = int(parts[i])
        content = parts[i + 1] if i + 1 < len(parts) else ""
        if content.strip():
            pages.append((page_num, content))

    return pages


def _separate_tables_and_text(page_content: str) -> tuple[list[str], list[str]]:
    """Separate table blocks from prose text within a page.

    Returns:
        (tables, text_parts) - tables as complete blocks, text_parts as remaining text.
    """
    tables: list[str] = []
    text_remaining = page_content

    # Find all table blocks
    for match in TABLE_MARKER_RE.finditer(page_content):
        tables.append(match.group(1))

    # Remove table blocks from text to get prose parts
    if tables:
        text_remaining = TABLE_MARKER_RE.sub("", page_content)

    text_parts = [t for t in text_remaining.split("\n\n") if t.strip()]

    return tables, text_parts


def _recursive_split(
    text: str,
    chunk_size: int,
    overlap: int,
    separators: list[str] | None = None,
) -> list[str]:
    """Recursively split text using hierarchical separators.

    Tries to split on paragraph breaks first, then newlines, then spaces.
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    if separators is None:
        separators = ["\n\n", "\n", " "]

    if not separators:
        # Last resort: hard split by character count with overlap
        return _hard_split(text, chunk_size, overlap)

    sep = separators[0]
    remaining_seps = separators[1:]

    parts = text.split(sep)
    chunks: list[str] = []
    current = ""

    for part in parts:
        candidate = f"{current}{sep}{part}" if current else part

        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            # If the single part is too large, recurse with next separator
            if len(part) > chunk_size:
                sub_chunks = _recursive_split(part, chunk_size, overlap, remaining_seps)
                chunks.extend(sub_chunks)
                current = ""
            else:
                current = part

    if current.strip():
        chunks.append(current)

    # Add overlap between consecutive chunks
    if overlap > 0 and len(chunks) > 1:
        chunks = _add_overlap(chunks, overlap)

    return [c for c in chunks if c.strip()]


def _hard_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split text by character count as last resort."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap if overlap > 0 else end
    return chunks


def _add_overlap(chunks: list[str], overlap: int) -> list[str]:
    """Add overlap from the end of each chunk to the beginning of the next."""
    if len(chunks) <= 1:
        return chunks

    result = [chunks[0]]
    for i in range(1, len(chunks)):
        prev_tail = chunks[i - 1][-overlap:] if len(chunks[i - 1]) > overlap else chunks[i - 1]
        result.append(prev_tail + chunks[i])

    return result


def _split_large_table(table_text: str, chunk_size: int, overlap: int) -> list[str]:
    """Split a large table at row boundaries (newline-separated rows)."""
    lines = table_text.split("\n")
    # Keep the header (first line with [Tabela ...] marker) in each chunk
    header = ""
    data_lines = lines
    if lines and lines[0].startswith("[Tabela"):
        header = lines[0] + "\n"
        # Also keep column headers (typically the second line)
        if len(lines) > 1 and "|" in lines[1]:
            header += lines[1] + "\n"
            data_lines = lines[2:]
        else:
            data_lines = lines[1:]

    chunks: list[str] = []
    current = header

    for line in data_lines:
        candidate = current + line + "\n"
        if len(candidate) > chunk_size and current != header:
            chunks.append(current.strip())
            # Start new chunk with header for context
            current = header + line + "\n"
        else:
            current = candidate

    if current.strip() and current.strip() != header.strip():
        chunks.append(current.strip())

    return chunks if chunks else [table_text]
