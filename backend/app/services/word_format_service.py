import re
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

class WordFormatService:
    def format_document(self, input_path: str, output_path: str):
        """
        Limpa e formata um documento Word (.docx) aplicando estilos padrão
        e corrigindo listas/parágrafos usando heurísticas.
        """
        doc = Document(input_path)
        
        # 1. Setup Standard Styles (Heuristic)
        # Tenta pegar o estilo 'Normal', se existir
        if 'Normal' in doc.styles:
            style = doc.styles['Normal']
            font = style.font
            font.name = 'Calibri'
            font.size = Pt(11)
        
        # Regex for detecting lists
        # Matches "1.", "1.1", "1.1.1", "a)", "a.", "- ", "• "
        numbering_regex = re.compile(r'^\s*(\d+(\.\d+)*\.?|[a-z]\)|\-)\s+')
        
        for para in doc.paragraphs:
            text = para.text.strip()
            if not text:
                continue
                
            # Remove weird double spaces
            para.text = re.sub(r'\s+', ' ', text)
            
            # 2. Check for Headings (Heuristic: All Caps + Short or Bold)
            is_bold = para.runs and para.runs[0].bold
            if (len(text) < 100 and text.isupper()) or (len(text) < 50 and is_bold):
                 para_format = para.paragraph_format
                 para_format.space_before = Pt(12)
                 para_format.space_after = Pt(6)
                 continue
    
            # 3. List Detection
            match = numbering_regex.match(text)
            if match:
                 marker = match.group(1)
                 if marker in ['-', '•']:
                     level = 0
                 else:
                     level = marker.count('.')
                     if marker.endswith('.'): level -= 1
                     if level < 0: level = 0
                 
                 para_format = para.paragraph_format
                 para_format.left_indent = Inches(0.25 + (level * 0.25))
                 para_format.first_line_indent = Inches(-0.25) # Hanging indent
            else:
                # Standard Paragraph
                para_format = para.paragraph_format
                para_format.line_spacing = 1.15
                para_format.space_after = Pt(6)
                para_format.left_indent = Inches(0)
                para_format.first_line_indent = Inches(0)
                para.alignment = WD_ALIGN_PARAGRAPH.LEFT
    
        doc.save(output_path)
