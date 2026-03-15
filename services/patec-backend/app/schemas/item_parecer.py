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
