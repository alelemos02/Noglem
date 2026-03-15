import io
import zipfile
from dataclasses import dataclass

from openpyxl import load_workbook

from app.services.exporter import _build_observacao, export_docx, export_pdf, export_xlsx


@dataclass
class DummyParecer:
    numero_parecer: str = "PYTEST-EXP-1"
    projeto: str = "Projeto Teste"
    fornecedor: str = "Fornecedor X"
    revisao: str = "A"
    parecer_geral: str | None = "APROVADO"
    status_processamento: str = "concluido"
    comentario_geral: str | None = "Comentario geral"
    conclusao: str | None = "Conclusao final"
    total_itens: int = 1
    total_aprovados: int = 1
    total_aprovados_comentarios: int = 0
    total_rejeitados: int = 0
    total_info_ausente: int = 0
    total_itens_adicionais: int = 0


@dataclass
class DummyItem:
    numero: int = 1
    categoria: str | None = "Tecnica"
    descricao_requisito: str = "Descricao requisito"
    referencia_engenharia: str | None = "Ref Eng"
    referencia_fornecedor: str | None = "Ref Forn"
    valor_requerido: str | None = "10bar"
    valor_fornecedor: str | None = "10bar"
    status: str = "A"
    justificativa_tecnica: str = "Justificativa"
    acao_requerida: str | None = "Nenhuma"
    prioridade: str | None = "BAIXA"
    norma_referencia: str | None = "NBR 1"


@dataclass
class DummyRecomendacao:
    ordem: int = 1
    texto: str = "Recomendacao teste"


def test_export_pdf_returns_pdf_bytes():
    payload = export_pdf(DummyParecer(), [DummyItem()], [DummyRecomendacao()])
    assert payload.startswith(b"%PDF")
    assert len(payload) > 1000


def test_export_xlsx_has_expected_sheets():
    payload = export_xlsx(DummyParecer(), [DummyItem()], [DummyRecomendacao()])
    wb = load_workbook(io.BytesIO(payload), data_only=True)
    assert wb.sheetnames == ["Resumo", "Itens", "Recomendacoes"]
    wb.close()


def test_export_docx_generates_document_xml():
    payload = export_docx(DummyParecer(), [DummyItem()], [DummyRecomendacao()])
    with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
        assert "word/document.xml" in archive.namelist()


def test_build_observacao_for_status_a_uses_default_when_empty():
    item = DummyItem(status="A", justificativa_tecnica="")
    observacao = _build_observacao(item)
    assert "aderente aos requisitos tecnicos" in observacao
