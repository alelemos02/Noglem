import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_VALID_PRIORIDADES = {"ALTA", "MEDIA", "BAIXA"}


class RequisitoBase(BaseModel):
    numero: int
    categoria: str | None = None
    descricao_requisito: str
    referencia_engenharia: str | None = None
    valor_requerido: str | None = None
    prioridade: str | None = "MEDIA"
    norma_referencia: str | None = None

    @field_validator("prioridade")
    @classmethod
    def validate_prioridade(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in _VALID_PRIORIDADES:
            raise ValueError("prioridade invalida. Use: ALTA, MEDIA ou BAIXA")
        return v


class ExtracaoRequest(BaseModel):
    perfil_analise: str = "padrao"
    # Recorte do documento pedido pelo usuario ("so o capitulo 2", "a tabela de
    # escopo"). Restringe a extracao; NUNCA levanta o teto de itens do perfil.
    escopo: str | None = None
    # Ajustes pedidos pelo usuario sobre uma lista ja extraida ("inclua X",
    # "quero a lista completa"). E o unico campo que pode liberar o teto.
    feedback: str | None = None


class ExtracaoAsyncResponse(BaseModel):
    """Resposta 202 do POST /extrair — a extracao roda em background (Celery);
    acompanhe pelo GET /extracao/progresso (stage completed/error encerra)."""

    task_id: str
    message: str


class ExtracaoProgressoResponse(BaseModel):
    percent: int | None = None
    message: str | None = None
    stage: str | None = None
    # Epoch (s) do ultimo set_progress — o worker mantem fresco via heartbeat;
    # permite ao frontend detectar progresso "morto" (worker caiu sem terminal).
    updated_at: float | None = None


class AprovarRequisitosRequest(BaseModel):
    requisitos: list[RequisitoBase] = Field(min_length=1)


class RequisitoUpdate(BaseModel):
    categoria: str | None = None
    descricao_requisito: str | None = None
    referencia_engenharia: str | None = None
    valor_requerido: str | None = None
    prioridade: str | None = None
    norma_referencia: str | None = None

    @field_validator("prioridade")
    @classmethod
    def validate_prioridade(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in _VALID_PRIORIDADES:
            raise ValueError("prioridade invalida. Use: ALTA, MEDIA ou BAIXA")
        return v


class RequisitoResponse(RequisitoBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    parecer_id: uuid.UUID
    versao: int
    ativo: bool
    aprovado_em: datetime | None = None
    criado_em: datetime


class RequisitosAprovadosResponse(BaseModel):
    requisitos: list[RequisitoResponse]
    total_itens: int
    fase_caso: str
