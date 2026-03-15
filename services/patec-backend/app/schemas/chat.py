from datetime import datetime

from pydantic import BaseModel, field_validator


class ChatMessageSend(BaseModel):
    mensagem: str
    regenerar: bool = False

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
