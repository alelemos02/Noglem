from datetime import datetime

from pydantic import BaseModel


class ItemParecerResponse(BaseModel):
    id: str
    parecer_id: str
    numero: int
    categoria: str | None
    descricao_requisito: str
    referencia_engenharia: str | None
    referencia_fornecedor: str | None
    valor_requerido: str | None
    valor_fornecedor: str | None
    status: str
    justificativa_tecnica: str
    acao_requerida: str | None
    prioridade: str | None
    norma_referencia: str | None
    editado_manualmente: bool
    estado: str = "ABERTO"
    verificacao_flag: str | None = None
    verificacao_nota: str | None = None
    # Flags internos de QA (badge na UI) — nunca vao para o parecer exportado.
    flag_consistencia: str | None = None
    nota_revisao: str | None = None
    criado_em: datetime
    atualizado_em: datetime

    model_config = {"from_attributes": True}


class ItemParecerUpdate(BaseModel):
    status: str | None = None
    justificativa_tecnica: str | None = None
    acao_requerida: str | None = None
    prioridade: str | None = None
    categoria: str | None = None
    descricao_requisito: str | None = None
    valor_requerido: str | None = None
    valor_fornecedor: str | None = None
    norma_referencia: str | None = None


class RecomendacaoResponse(BaseModel):
    id: str
    parecer_id: str
    texto: str
    ordem: int

    model_config = {"from_attributes": True}


class RastreabilidadeLinha(BaseModel):
    requisito_numero: int
    requisito_descricao: str
    requisito_valor: str | None = None
    requisito_prioridade: str | None = None
    referencia_engenharia: str | None = None
    item_numero: int | None = None
    item_status: str | None = None
    # "coberto" (item real da analise) | "revisar" (placeholder da reconciliacao
    # ou requisito sem item — precisa de analise manual)
    cobertura: str


class RastreabilidadeResponse(BaseModel):
    total_requisitos: int
    cobertos: int
    a_revisar: int
    linhas: list[RastreabilidadeLinha]
