from datetime import datetime

from pydantic import BaseModel, field_validator


class ParecerCreate(BaseModel):
    numero_parecer: str
    projeto: str
    fornecedor: str
    revisao: str = "0"
    comentario_geral: str | None = None

    @field_validator("numero_parecer")
    @classmethod
    def validate_numero_parecer(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Numero do parecer e obrigatorio")
        if len(v) > 50:
            raise ValueError("Numero do parecer deve ter no maximo 50 caracteres")
        return v

    @field_validator("projeto")
    @classmethod
    def validate_projeto(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Nome do projeto e obrigatorio")
        if len(v) > 200:
            raise ValueError("Nome do projeto deve ter no maximo 200 caracteres")
        return v

    @field_validator("fornecedor")
    @classmethod
    def validate_fornecedor(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Nome do fornecedor e obrigatorio")
        if len(v) > 200:
            raise ValueError("Nome do fornecedor deve ter no maximo 200 caracteres")
        return v

    @field_validator("revisao")
    @classmethod
    def validate_revisao(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 10:
            raise ValueError("Revisao deve ter no maximo 10 caracteres")
        return v


class ParecerUpdate(BaseModel):
    projeto: str | None = None
    fornecedor: str | None = None
    revisao: str | None = None
    comentario_geral: str | None = None
    conclusao: str | None = None
    parecer_geral: str | None = None

    @field_validator("projeto")
    @classmethod
    def validate_projeto(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Nome do projeto nao pode ser vazio")
            if len(v) > 200:
                raise ValueError("Nome do projeto deve ter no maximo 200 caracteres")
        return v

    @field_validator("fornecedor")
    @classmethod
    def validate_fornecedor(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("Nome do fornecedor nao pode ser vazio")
            if len(v) > 200:
                raise ValueError("Nome do fornecedor deve ter no maximo 200 caracteres")
        return v

    @field_validator("revisao")
    @classmethod
    def validate_revisao(cls, v: str | None) -> str | None:
        if v is not None and len(v.strip()) > 10:
            raise ValueError("Revisao deve ter no maximo 10 caracteres")
        return v.strip() if v else v


class ParecerResponse(BaseModel):
    id: str
    numero_parecer: str
    projeto: str
    fornecedor: str
    revisao: str
    status_processamento: str
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
    atualizado_em: datetime

    model_config = {"from_attributes": True}


class ParecerListResponse(BaseModel):
    items: list[ParecerResponse]
    total: int
    page: int
    page_size: int
