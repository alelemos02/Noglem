from pydantic_settings import BaseSettings
from pydantic import model_validator


class Settings(BaseSettings):
    PROJECT_NAME: str = "PATEC - Parecer Tecnico de Engenharia"
    API_V1_PREFIX: str = "/api/v1"

    # Ambiente de execucao. Em "production" o startup faz fail-fast se segredos
    # default (SECRET_KEY, DOCUMENT_ENCRYPTION_KEY, INTERNAL_API_KEY) nao forem
    # trocados — ver validate_production_secrets().
    ENV: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://patec:patec@localhost:5432/patec"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://patec:patec@localhost:5432/patec"

    @model_validator(mode="after")
    def fix_database_urls(self):
        """Auto-convert Railway-style postgresql:// to driver-specific URLs."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://") or url.startswith("postgres://"):
            base = url.replace("postgres://", "postgresql://", 1)
            self.DATABASE_URL = base.replace("postgresql://", "postgresql+asyncpg://", 1)
            self.DATABASE_URL_SYNC = base.replace("postgresql://", "postgresql+psycopg2://", 1)
        return self

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Gemini API
    GEMINI_API_KEY: str = ""
    # Modelo INCIDENTAL barato (flash): usado só em chamadas utilitárias que não
    # decidem classificação — otimização de campos, reparo de JSON, estimativa de
    # custo, recuperação de valor do fornecedor. As tarefas que exigem raciocínio
    # (análise, extração, verifier, chat) têm cada uma seu Pro-preview abaixo.
    # NB: nomes v1beta como "gemini-3.1-pro" exigem o sufixo "-preview" (sem ele 404).
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GEMINI_MAX_RETRIES: int = 4
    GEMINI_RETRY_BASE_SECONDS: float = 2.0
    GEMINI_RETRY_MAX_SECONDS: float = 20.0

    # Self-review: optional second LLM pass to verify flagged items
    ENABLE_LLM_SELF_REVIEW: bool = False

    # Cross-item verifier: a stronger (Pro) model re-checks only the items a
    # deterministic detector flagged as suspect (e.g. a supplier value reused
    # across distinct requirements). Triggered post-cache; runs only on flagged
    # items, so the extra cost is bounded.
    ENABLE_LLM_VERIFIER: bool = True
    # NB: o nome exposto pela API generativelanguage v1beta exige o sufixo
    # "-preview" (gemini-3.1-pro sem ele retorna 404). Confirmado via ListModels.
    GEMINI_VERIFIER_MODEL: str = "gemini-3.1-pro-preview"

    # Verificador de condicoes atomicas: ultimo gate antes da gravacao. Decompoe
    # cada item A/B nas condicoes do requisito (quantidade, rack, material, TAG...)
    # e exige evidencia explicita do fornecedor por condicao; nao-confirmadas vao
    # TODAS para a acao_requerida e podem rebaixar o status (nunca melhorar).
    # Nasceu do caso "video wall": analise deu B mas esqueceu o rack 19" na acao.
    # Usa GEMINI_VERIFIER_MODEL. Desligar via env = rollback sem deploy.
    ENABLE_ATOMIC_VERIFIER: bool = True

    # Extraction (W1) defines the WHOLE scope of the parecer (one call per case),
    # so it runs on the stronger Pro model — far more faithful at enumerating
    # every row of a delimited table than the cheaper analysis model.
    GEMINI_EXTRACTION_MODEL: str = "gemini-3.1-pro-preview"

    # Análise item-a-item (classificação A/B/C/D — o CORAÇÃO do produto). Roda no
    # Pro porque é onde a capacidade de leitura vira "pegou ou não o desvio": o flash
    # carimbava "A" (atendido) em requisitos compostos sem o fornecedor confirmar
    # TODAS as condições (ex.: monitores OK, mas silêncio sobre o rack 19"), e um
    # falso-A é o erro mais caro do parecer (desvio que vira pleito na obra).
    # Custo maior é intencional e aceito. Entra na chave de cache (tasks.py) para
    # que a troca flash->Pro invalide análises antigas.
    GEMINI_ANALYSIS_MODEL: str = "gemini-3.1-pro-preview"

    # Chat (JULIA conversacional): roda no Pro para OBEDECER as instrucoes de voz
    # (prosa, nao "ficha de campos"). O flash barato ignorava a instrucao de estilo
    # (ver chat.py). Mesmo nome "-preview" ja validado pela extracao/verifier.
    GEMINI_CHAT_MODEL: str = "gemini-3.1-pro-preview"

    # RAG - Retrieval Augmented Generation
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    RAG_CHUNK_SIZE: int = 1500
    RAG_CHUNK_OVERLAP: int = 200
    RAG_TOP_K: int = 15
    CHAT_MEMORY_TOP_K: int = 8
    CHAT_MEMORY_BACKFILL_LIMIT: int = 500

    # Storage
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50
    DOCUMENT_ENCRYPTION_KEY: str = ""

    # Internal API Key (shared with Next.js proxy for secure communication)
    INTERNAL_API_KEY: str = ""

    # Donos da ferramenta (dashboard de qualidade). Lista de e-mails separada por
    # virgula. Em producao, o dashboard e restrito a estes e-mails (via Clerk, o
    # e-mail do login). Em dev o gate e aberto (ver require_owner).
    OWNER_EMAILS: str = ""

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost",
        "http://127.0.0.1",
    ]

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def is_production(self) -> bool:
        return self.ENV.strip().lower() in ("production", "prod")

    @property
    def owner_emails(self) -> set[str]:
        return {e.strip().lower() for e in self.OWNER_EMAILS.split(",") if e.strip()}

    def validate_production_secrets(self) -> None:
        """Fail-fast: recusa subir em producao com segredos default.

        Sem isto, um deploy que esqueca de trocar os segredos criptografa
        documentos com chave publicamente conhecivel (derivada do SECRET_KEY
        default) e deixa a API interna aberta. Roda no startup (nao no import).
        """
        if not self.is_production:
            return
        problemas: list[str] = []
        if self.SECRET_KEY.strip() in ("", "change-me-in-production"):
            problemas.append("SECRET_KEY nao foi trocado do valor default")
        if not self.DOCUMENT_ENCRYPTION_KEY.strip():
            problemas.append(
                "DOCUMENT_ENCRYPTION_KEY vazio (criptografia de documentos cairia "
                "em chave derivada do SECRET_KEY)"
            )
        if not self.INTERNAL_API_KEY.strip():
            problemas.append(
                "INTERNAL_API_KEY vazio (API interna ficaria sem protecao)"
            )
        if problemas:
            raise RuntimeError(
                "Configuracao de producao insegura — corrija antes de subir:\n  - "
                + "\n  - ".join(problemas)
            )

    def gemini_models(self) -> set[str]:
        """Modelos Gemini distintos configurados (para validacao no startup)."""
        return {
            m.strip()
            for m in (
                self.GEMINI_MODEL,
                self.GEMINI_ANALYSIS_MODEL,
                self.GEMINI_CHAT_MODEL,
                self.GEMINI_EXTRACTION_MODEL,
                self.GEMINI_VERIFIER_MODEL,
            )
            if m and m.strip()
        }


settings = Settings()
