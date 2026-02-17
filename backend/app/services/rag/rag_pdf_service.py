import pdfplumber
from typing import List, Dict, Tuple
import os
import pytesseract
from pdf2image import convert_from_path

class RAGPDFService:
    def extract_text(self, file_path: str) -> Tuple[List[Dict], bool]:
        """
        Extracts text from a PDF file preserving page metadata.
        Returns a tuple: (list of dicts {'text': str, 'page_number': int}, has_ocr: bool)
        Triggers OCR if standard extraction yields insufficient text.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        extracted_data = []
        has_ocr = False
        
        # 1. Try Standard Extraction
        total_text_length = 0
        try:
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        extracted_data.append({
                            "text": text,
                            "page_number": i + 1
                        })
                        total_text_length += len(text)
        except Exception as e:
            print(f"Standard extraction failed: {e}")

        # 2. Check if OCR is needed (e.g., < 50 chars total)
        if total_text_length < 50:
            print("Insufficient text detected. Triggering OCR fallback...")
            try:
                # Convert PDF to images
                images = convert_from_path(file_path)
                extracted_data = [] # Reset
                
                for i, image in enumerate(images):
                    text = pytesseract.image_to_string(image)
                    if text.strip():
                        extracted_data.append({
                            "text": text,
                            "page_number": i + 1
                        })
                
                if extracted_data:
                    has_ocr = True
                    
            except Exception as e:
                # If OCR also fails, we re-raise or return empty
                print(f"OCR extraction failed: {e}")
                if not extracted_data: 
                     # Only raise if we really have nothing
                     raise ValueError(f"Failed to extract text from PDF (both standard and OCR): {str(e)}")

        return extracted_data, has_ocr

rag_pdf_service = RAGPDFService()
