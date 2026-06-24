import { PDFDocument } from "pdf-lib";

export type PdfChunk = {
  /** A valid standalone PDF containing a contiguous subset of the original pages. */
  blob: Blob;
  /** 1-based page number, in the original document, of this chunk's first page. */
  startPage: number;
  /** Number of pages in this chunk. */
  pageCount: number;
};

/** Thrown when a single page alone exceeds the upload limit and cannot be split further. */
export class PageTooLargeError extends Error {
  readonly page: number;
  readonly sizeMb: string;
  constructor(page: number, sizeMb: string) {
    super(
      `A página ${page} sozinha tem ${sizeMb} MB e ultrapassa o limite de upload. ` +
        `Comprima o PDF (reduza a resolução das imagens) antes de extrair.`
    );
    this.name = "PageTooLargeError";
    this.page = page;
    this.sizeMb = sizeMb;
  }
}

// Aim below the hard limit to leave room for multipart/form-data overhead.
const SAFETY_MARGIN = 0.85;

/** Wraps bytes in a PDF Blob backed by a plain ArrayBuffer (satisfies BlobPart typing). */
function toPdfBlob(bytes: Uint8Array): Blob {
  const buffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buffer).set(bytes);
  return new Blob([buffer], { type: "application/pdf" });
}

async function buildSubDoc(
  src: PDFDocument,
  start: number,
  count: number
): Promise<Uint8Array> {
  const out = await PDFDocument.create();
  const indices = Array.from({ length: count }, (_, i) => start + i);
  const pages = await out.copyPages(src, indices);
  pages.forEach((page) => out.addPage(page));
  return out.save();
}

/**
 * Splits a PDF into the fewest contiguous page-chunks whose serialized size each
 * stays under `maxBytes`. The split runs entirely in the browser so the original
 * (oversized) file never has to be uploaded.
 *
 * Throws {@link PageTooLargeError} if a single page can't fit under the limit.
 */
export async function splitPdfBySize(
  file: File,
  maxBytes: number
): Promise<PdfChunk[]> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const src = await PDFDocument.load(bytes, { ignoreEncryption: true });
  const total = src.getPageCount();
  const target = Math.floor(maxBytes * SAFETY_MARGIN);

  const chunks: PdfChunk[] = [];
  let start = 0; // 0-based index of the next page to place

  while (start < total) {
    // Binary-search the largest run of pages from `start` that fits in `target`.
    // Size is monotonic in page count, so this is well-defined.
    let lo = 1;
    let hi = total - start;
    let best = 0;
    let bestBytes: Uint8Array | null = null;

    while (lo <= hi) {
      const mid = Math.floor((lo + hi) / 2);
      const candidate = await buildSubDoc(src, start, mid);
      if (candidate.length <= target) {
        best = mid;
        bestBytes = candidate;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }

    if (best === 0) {
      // Not even one page fits under the (margin-reduced) target. Accept a single
      // page if it still fits under the real limit; otherwise it's unsplittable.
      const single = await buildSubDoc(src, start, 1);
      if (single.length <= maxBytes) {
        chunks.push({
          blob: toPdfBlob(single),
          startPage: start + 1,
          pageCount: 1,
        });
        start += 1;
        continue;
      }
      throw new PageTooLargeError(
        start + 1,
        (single.length / 1024 / 1024).toFixed(2)
      );
    }

    chunks.push({
      blob: toPdfBlob(bestBytes!),
      startPage: start + 1,
      pageCount: best,
    });
    start += best;
  }

  return chunks;
}
