import pdfplumber
import pandas as pd
from typing import Dict, List, Any


class PdfExtractService:
    def extract_tables(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extrai todas as tabelas de um PDF.
        """
        tables_data = []
        total_pages = 0

        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)

            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()

                for table_idx, table in enumerate(tables):
                    if not table or len(table) < 2:
                        continue

                    # Primeira linha como headers
                    headers = [str(cell) if cell else "" for cell in table[0]]

                    # Resto como rows
                    rows = []
                    for row in table[1:]:
                        cleaned_row = [str(cell) if cell else "" for cell in row]
                        rows.append(cleaned_row)

                    tables_data.append(
                        {
                            "page": page_num,
                            "table_index": table_idx,
                            "headers": headers,
                            "rows": rows,
                        }
                    )

        return {
            "total_pages": total_pages,
            "tables_found": len(tables_data),
            "tables": tables_data,
        }

    def extract_to_excel(self, pdf_path: str, output_path: str) -> str:
        """
        Extrai tabelas e salva como arquivo Excel.
        """
        result = self.extract_tables(pdf_path)

        if not result["tables"]:
            raise ValueError("Nenhuma tabela encontrada no PDF")

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for i, table_data in enumerate(result["tables"]):
                # Criar DataFrame
                df = pd.DataFrame(table_data["rows"], columns=table_data["headers"])

                # Nome da sheet (máximo 31 caracteres)
                sheet_name = f"Pag{table_data['page']}_Tab{table_data['table_index'] + 1}"
                sheet_name = sheet_name[:31]

                # Salvar no Excel
                df.to_excel(writer, sheet_name=sheet_name, index=False)

        return output_path
