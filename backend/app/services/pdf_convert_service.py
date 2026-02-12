from pdf2docx import Converter


class PdfConvertService:
    def convert(self, pdf_path: str, output_path: str) -> str:
        """
        Converte PDF para documento Word (DOCX).
        """
        cv = Converter(pdf_path)

        try:
            cv.convert(output_path)
        finally:
            cv.close()

        return output_path
