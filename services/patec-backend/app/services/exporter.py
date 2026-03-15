import io
import logging
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from docx import Document as DocxDocument
from docx.shared import Pt
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH

logger = logging.getLogger(__name__)

# Shared constants for status/priority labels and colors
STATUS_LABELS = {
    "A": "APROVADO",
    "B": "APROVADO COM COMENTARIOS",
    "C": "REJEITADO",
    "D": "INFORMACAO AUSENTE",
    "E": "ITEM ADICIONAL DO FORNECEDOR",
}

STATUS_HEX_COLORS = {
    "A": "#c6f6d5",
    "B": "#fefcbf",
    "C": "#fed7d7",
    "D": "#e2e8f0",
    "E": "#bee3f8",
}

STATUS_ROW_HEX_COLORS = {
    "A": "#f0fff4",
    "B": "#fffff0",
    "C": "#fff5f5",
    "D": "#f7fafc",
    "E": "#ebf8ff",
}

MAX_EXPORT_ITEMS = 5000
DEFAULT_OBSERVATION_BY_STATUS = {
    "A": "Item aderente aos requisitos tecnicos da engenharia, sem desvios identificados.",
    "B": "Item parcialmente conforme; requer ajustes para atendimento completo.",
    "C": "Item nao conforme aos requisitos tecnicos e necessita revisao do fornecedor.",
    "D": "Informacao tecnica ausente na documentacao do fornecedor.",
    "E": "Item adicional apresentado pelo fornecedor e pendente de avaliacao da engenharia.",
}


def _build_solicitacao_engenharia(item) -> str:
    parts = [item.descricao_requisito or ""]
    if item.valor_requerido:
        parts.append(f"Valor requerido: {item.valor_requerido}")
    if item.referencia_engenharia:
        parts.append(f"Ref. engenharia: {item.referencia_engenharia}")
    return "\n".join(part for part in parts if part and part.strip()).strip() or "-"


def _build_proposto_fornecedor(item) -> str:
    parts = []
    if item.valor_fornecedor:
        parts.append(f"Valor informado: {item.valor_fornecedor}")
    if item.referencia_fornecedor:
        parts.append(f"Ref. fornecedor: {item.referencia_fornecedor}")
    return "\n".join(part for part in parts if part and part.strip()).strip() or "Nao informado"


def _build_observacao(item) -> str:
    justificativa = (item.justificativa_tecnica or "").strip()
    if justificativa:
        return justificativa

    return DEFAULT_OBSERVATION_BY_STATUS.get(
        item.status,
        "Item nao aprovado. Revisar conformidade tecnica deste requisito.",
    )


def export_pdf(parecer, itens, recomendacoes) -> bytes:
    """Generate a PDF report for the parecer."""
    try:
        export_itens = itens[:MAX_EXPORT_ITEMS]
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=20 * mm, rightMargin=20 * mm,
            topMargin=25 * mm, bottomMargin=20 * mm,
        )

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="SmallBody", parent=styles["Normal"], fontSize=8, leading=10))
        styles.add(ParagraphStyle(
            name="Header1", parent=styles["Heading1"], fontSize=14,
            spaceAfter=6, textColor=colors.HexColor("#1a365d"),
        ))
        styles.add(ParagraphStyle(
            name="Header2", parent=styles["Heading2"], fontSize=11,
            spaceAfter=4, textColor=colors.HexColor("#2d3748"),
        ))
        styles.add(ParagraphStyle(
            name="CenteredSmallBody", parent=styles["SmallBody"], fontSize=7, leading=9, alignment=1
        ))

        elements = []

        # Title
        elements.append(Paragraph("PARECER TECNICO DE ENGENHARIA", styles["Header1"]))
        elements.append(Spacer(1, 4 * mm))

        # Metadata table
        meta_data = [
            ["Numero:", parecer.numero_parecer, "Data:", datetime.now().strftime("%d/%m/%Y")],
            ["Projeto:", parecer.projeto, "Revisao:", parecer.revisao],
            ["Fornecedor:", parecer.fornecedor, "Parecer:", parecer.parecer_geral or "Pendente"],
        ]
        meta_table = Table(meta_data, colWidths=[25 * mm, 60 * mm, 22 * mm, 60 * mm])
        meta_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f7fafc")),
            ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#f7fafc")),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 6 * mm))

        # Executive Summary
        elements.append(Paragraph("RESUMO EXECUTIVO", styles["Header2"]))
        summary_data = [
            ["Total", "Aprovados", "Aprov. c/ Com.", "Rejeitados", "Info Ausente", "Adicionais"],
            [
                str(parecer.total_itens), str(parecer.total_aprovados),
                str(parecer.total_aprovados_comentarios), str(parecer.total_rejeitados),
                str(parecer.total_info_ausente), str(parecer.total_itens_adicionais),
            ],
        ]
        summary_table = Table(summary_data, colWidths=[28 * mm] * 6)

        summary_col_colors = [
            (1, colors.HexColor(STATUS_HEX_COLORS["A"])),
            (2, colors.HexColor(STATUS_HEX_COLORS["B"])),
            (3, colors.HexColor(STATUS_HEX_COLORS["C"])),
            (4, colors.HexColor(STATUS_HEX_COLORS["D"])),
            (5, colors.HexColor(STATUS_HEX_COLORS["E"])),
        ]
        style_cmds = [
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf2f7")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]
        for col, color in summary_col_colors:
            style_cmds.append(("BACKGROUND", (col, 1), (col, 1), color))

        summary_table.setStyle(TableStyle(style_cmds))
        elements.append(summary_table)
        elements.append(Spacer(1, 4 * mm))

        if parecer.comentario_geral:
            elements.append(Paragraph(
                f"<b>Comentario Geral:</b> {parecer.comentario_geral}", styles["SmallBody"]
            ))
            elements.append(Spacer(1, 4 * mm))

        # Items table
        if export_itens:
            elements.append(Paragraph("ITENS DO PARECER", styles["Header2"]))

            item_header = [
                "Solicitacao da Engenharia",
                "Proposto pelo Fornecedor",
                "Status",
                "Observacao",
            ]
            col_widths = [50 * mm, 42 * mm, 22 * mm, 56 * mm]

            rows = [item_header]
            for item in export_itens:
                rows.append([
                    Paragraph(_build_solicitacao_engenharia(item)[:800], styles["SmallBody"]),
                    Paragraph(_build_proposto_fornecedor(item)[:800], styles["SmallBody"]),
                    Paragraph(STATUS_LABELS.get(item.status, item.status), styles["CenteredSmallBody"]),
                    Paragraph(_build_observacao(item)[:800], styles["SmallBody"]),
                ])

            item_table = Table(rows, colWidths=col_widths, repeatRows=1)

            row_styles = [
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2d3748")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (2, 0), (2, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]

            for i, item in enumerate(export_itens, 1):
                hex_color = STATUS_ROW_HEX_COLORS.get(item.status)
                if hex_color:
                    row_styles.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor(hex_color)))

            item_table.setStyle(TableStyle(row_styles))
            elements.append(item_table)
            elements.append(Spacer(1, 6 * mm))

        # Conclusion
        if parecer.conclusao:
            elements.append(Paragraph("CONCLUSAO", styles["Header2"]))
            elements.append(Paragraph(parecer.conclusao, styles["Normal"]))
            elements.append(Spacer(1, 4 * mm))

        # Recommendations
        if recomendacoes:
            elements.append(Paragraph("RECOMENDACOES", styles["Header2"]))
            for rec in recomendacoes:
                elements.append(Paragraph(f"&bull; {rec.texto}", styles["Normal"]))
            elements.append(Spacer(1, 4 * mm))

        doc.build(elements)
        return buffer.getvalue()

    except Exception:
        logger.exception("Erro ao gerar PDF para parecer %s", parecer.numero_parecer)
        raise


def export_xlsx(parecer, itens, recomendacoes) -> bytes:
    """Generate an XLSX report for the parecer."""
    try:
        export_itens = itens[:MAX_EXPORT_ITEMS]
        wb = Workbook()

        header_font = Font(bold=True, color="FFFFFF", size=10)
        header_fill = PatternFill(start_color="2D3748", end_color="2D3748", fill_type="solid")
        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin"),
        )

        status_fills = {
            code: PatternFill(
                start_color=hex_color.lstrip("#"),
                end_color=hex_color.lstrip("#"),
                fill_type="solid",
            )
            for code, hex_color in STATUS_HEX_COLORS.items()
        }

        # Sheet 1: Resumo
        ws = wb.active
        ws.title = "Resumo"
        ws.column_dimensions["A"].width = 25
        ws.column_dimensions["B"].width = 50

        info = [
            ("PARECER TECNICO DE ENGENHARIA", ""),
            ("", ""),
            ("Numero do Parecer", parecer.numero_parecer),
            ("Projeto", parecer.projeto),
            ("Fornecedor", parecer.fornecedor),
            ("Revisao", parecer.revisao),
            ("Data", datetime.now().strftime("%d/%m/%Y")),
            ("Parecer Geral", parecer.parecer_geral or "Pendente"),
            ("", ""),
            ("RESUMO EXECUTIVO", ""),
            ("Total de Itens", parecer.total_itens),
            ("Aprovados (A)", parecer.total_aprovados),
            ("Aprovados com Comentarios (B)", parecer.total_aprovados_comentarios),
            ("Rejeitados (C)", parecer.total_rejeitados),
            ("Informacao Ausente (D)", parecer.total_info_ausente),
            ("Itens Adicionais (E)", parecer.total_itens_adicionais),
        ]
        for row_idx, (label, value) in enumerate(info, 1):
            ws.cell(row=row_idx, column=1, value=label).font = Font(bold=True) if label else Font()
            ws.cell(row=row_idx, column=2, value=value)

        ws.cell(row=1, column=1).font = Font(bold=True, size=14)

        if parecer.comentario_geral:
            ws.append([""])
            ws.append(["Comentario Geral", parecer.comentario_geral])

        if parecer.conclusao:
            ws.append([""])
            ws.append(["Conclusao", parecer.conclusao])

        # Sheet 2: Itens
        ws2 = wb.create_sheet("Itens")
        headers = [
            "Solicitacao da Engenharia",
            "Proposto pelo Fornecedor",
            "Status",
            "Observacao",
        ]
        for col, h in enumerate(headers, 1):
            cell = ws2.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center", wrap_text=True)

        col_widths = [60, 55, 24, 75]
        for i, w in enumerate(col_widths, 1):
            ws2.column_dimensions[get_column_letter(i)].width = w

        for item in export_itens:
            row = [
                _build_solicitacao_engenharia(item),
                _build_proposto_fornecedor(item),
                STATUS_LABELS.get(item.status, item.status),
                _build_observacao(item),
            ]
            ws2.append(row)
            row_idx = ws2.max_row
            fill = status_fills.get(item.status)
            if fill:
                for col in range(1, len(headers) + 1):
                    ws2.cell(row=row_idx, column=col).fill = fill
                    ws2.cell(row=row_idx, column=col).border = thin_border
                    ws2.cell(row=row_idx, column=col).alignment = Alignment(
                        wrap_text=True, vertical="top"
                    )

        # Sheet 3: Recomendacoes
        ws3 = wb.create_sheet("Recomendacoes")
        for col, h in enumerate(["#", "Recomendacao"], 1):
            cell = ws3.cell(row=1, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = thin_border
        ws3.column_dimensions["A"].width = 5
        ws3.column_dimensions["B"].width = 80

        for rec in recomendacoes:
            ws3.append([rec.ordem, rec.texto])

        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    except Exception:
        logger.exception("Erro ao gerar XLSX para parecer %s", parecer.numero_parecer)
        raise


def export_docx(parecer, itens, recomendacoes) -> bytes:
    """Generate a DOCX report for the parecer."""
    try:
        return _build_docx(parecer, itens, recomendacoes)
    except Exception:
        logger.exception("Erro ao gerar DOCX para parecer %s", parecer.numero_parecer)
        raise


def _build_docx(parecer, itens, recomendacoes) -> bytes:
    export_itens = itens[:MAX_EXPORT_ITEMS]
    doc = DocxDocument()

    # Style adjustments
    style = doc.styles["Normal"]
    style.font.size = Pt(10)
    style.font.name = "Calibri"

    # Title
    title = doc.add_heading("PARECER TECNICO DE ENGENHARIA", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Metadata
    doc.add_heading("Informacoes do Parecer", level=1)
    meta_table = doc.add_table(rows=4, cols=4)
    meta_table.style = "Table Grid"
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER

    meta_data = [
        ("Numero:", parecer.numero_parecer, "Data:", datetime.now().strftime("%d/%m/%Y")),
        ("Projeto:", parecer.projeto, "Revisao:", parecer.revisao),
        ("Fornecedor:", parecer.fornecedor, "Parecer:", parecer.parecer_geral or "Pendente"),
        ("Total Itens:", str(parecer.total_itens), "Status:", parecer.status_processamento),
    ]
    for i, (l1, v1, l2, v2) in enumerate(meta_data):
        row = meta_table.rows[i]
        row.cells[0].text = l1
        row.cells[0].paragraphs[0].runs[0].bold = True if row.cells[0].paragraphs[0].runs else False
        row.cells[1].text = v1
        row.cells[2].text = l2
        row.cells[3].text = v2
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_after = Pt(2)
                paragraph.paragraph_format.space_before = Pt(2)

    # Bold labels
    for i in range(4):
        for col in [0, 2]:
            for run in meta_table.rows[i].cells[col].paragraphs[0].runs:
                run.bold = True

    doc.add_paragraph()

    # Executive Summary
    doc.add_heading("Resumo Executivo", level=1)
    summary_table = doc.add_table(rows=2, cols=6)
    summary_table.style = "Table Grid"
    summary_table.alignment = WD_TABLE_ALIGNMENT.CENTER

    headers = ["Total", "Aprovados", "Aprov. c/ Com.", "Rejeitados", "Info Ausente", "Adicionais"]
    values = [
        parecer.total_itens, parecer.total_aprovados, parecer.total_aprovados_comentarios,
        parecer.total_rejeitados, parecer.total_info_ausente, parecer.total_itens_adicionais,
    ]
    for i, h in enumerate(headers):
        cell = summary_table.rows[0].cells[i]
        cell.text = h
        for run in cell.paragraphs[0].runs:
            run.bold = True
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for i, v in enumerate(values):
        cell = summary_table.rows[1].cells[i]
        cell.text = str(v)
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    if parecer.comentario_geral:
        doc.add_paragraph()
        p = doc.add_paragraph()
        p.add_run("Comentario Geral: ").bold = True
        p.add_run(parecer.comentario_geral)

    doc.add_paragraph()

    # Items
    if export_itens:
        doc.add_heading("Itens do Parecer", level=1)

        items_table = doc.add_table(rows=1, cols=4)
        items_table.style = "Table Grid"
        items_table.alignment = WD_TABLE_ALIGNMENT.CENTER

        headers = [
            "Solicitacao da Engenharia",
            "Proposto pelo Fornecedor",
            "Status",
            "Observacao",
        ]
        for idx, title in enumerate(headers):
            cell = items_table.rows[0].cells[idx]
            cell.text = title
            for run in cell.paragraphs[0].runs:
                run.bold = True

        for item in export_itens:
            row = items_table.add_row().cells
            row[0].text = _build_solicitacao_engenharia(item)
            row[1].text = _build_proposto_fornecedor(item)
            row[2].text = STATUS_LABELS.get(item.status, item.status)
            row[3].text = _build_observacao(item)

    # Conclusion
    if parecer.conclusao:
        doc.add_heading("Conclusao", level=1)
        doc.add_paragraph(parecer.conclusao)

    # Recommendations
    if recomendacoes:
        doc.add_heading("Recomendacoes", level=1)
        for rec in recomendacoes:
            doc.add_paragraph(rec.texto, style="List Bullet")

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
