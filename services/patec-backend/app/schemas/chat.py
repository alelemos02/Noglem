from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class ContextoFluxo(BaseModel):
    """Estado do fluxo conversacional (JULIA) enviado pelo frontend.

    Permite que o chat saiba em que passo o caso esta e quais dados de
    sessao existem (ex: draft de requisitos ainda nao aprovado - W1).
    """

    fase_caso: str | None = None
    step_id: str | None = None
    requisitos_draft: list[dict[str, Any]] | None = None


class ChatMessageSend(BaseModel):
    mensagem: str
    contexto: ContextoFluxo | None = None

    @field_validator("mensagem")
    @classmethod
    def validate_mensagem(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Mensagem nao pode ser vazia")
        if len(v) > 5000:
            raise ValueError("Mensagem deve ter no maximo 5000 caracteres")
        return v


class ChatMessageResponse(BaseModel):
    id: str
    papel: str
    conteudo: str
    ordem: int
    gerou_nova_tabela: bool
    criado_em: datetime

    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageResponse]
    total: int
