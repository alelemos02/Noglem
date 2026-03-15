from pydantic import BaseModel, EmailStr


class UserRegister(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    papel: str = "analista"


class UserLogin(BaseModel):
    email: EmailStr
    senha: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    nome: str
    email: str
    papel: str
    ativo: bool

    model_config = {"from_attributes": True}
