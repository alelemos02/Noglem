from datetime import datetime

from pydantic import BaseModel


class DocumentoResponse(BaseModel):
    id: str
    parecer_id: str
    tipo: str
    nome_arquivo: str
    tipo_arquivo: str
    tamanho_bytes: int | None
    criado_em: datetime

    model_config = {"from_attributes": True}
