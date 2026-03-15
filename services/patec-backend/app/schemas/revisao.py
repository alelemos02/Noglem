from datetime import datetime

from pydantic import BaseModel


class RevisaoCreate(BaseModel):
    motivo: str | None = None


class RevisaoResponse(BaseModel):
    id: str
    parecer_id: str
    numero_revisao: int
    motivo: str | None
    criado_por: str | None
    parecer_geral: str | None
    comentario_geral: str | None
    conclusao: str | None
    total_itens: int
    total_aprovados: int
    total_aprovados_comentarios: int
    total_rejeitados: int
    total_info_ausente: int
    total_itens_adicionais: int
    criado_em: datetime

    model_config = {"from_attributes": True}


class RevisaoListResponse(BaseModel):
    items: list[RevisaoResponse]
    total: int


class RevisaoCompareResponse(BaseModel):
    revisao_a: RevisaoResponse
    revisao_b: RevisaoResponse
    diferencas: dict
