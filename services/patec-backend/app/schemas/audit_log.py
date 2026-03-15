from datetime import datetime

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    id: str
    usuario_id: str | None
    usuario_email: str | None
    acao: str
    recurso: str
    recurso_id: str | None
    detalhes: str | None
    ip_address: str | None
    criado_em: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
