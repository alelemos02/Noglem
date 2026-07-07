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
    # Aviso quando a extracao rendeu pouco/nenhum texto (imagem sem OCR, PDF
    # escaneado, arquivo vazio). None quando o documento foi lido normalmente.
    aviso_extracao: str | None = None

    model_config = {"from_attributes": True}
