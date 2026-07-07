from fastapi import APIRouter, Depends

from app.core.deps import require_internal_api_key
from app.api.v1.endpoints import (
    auth, pareceres, documentos, analise, itens,
    exportacoes, revisoes, estimativa, auditoria, chat, ciclo_avaliativo,
    requisitos, verificacao, revisao_spec, admin,
)

api_router = APIRouter(dependencies=[Depends(require_internal_api_key)])
api_router.include_router(auth.router)
api_router.include_router(pareceres.router)
api_router.include_router(documentos.router)
api_router.include_router(analise.router)
api_router.include_router(requisitos.router)
api_router.include_router(itens.router)
api_router.include_router(exportacoes.router)
api_router.include_router(revisoes.router)
api_router.include_router(estimativa.router)
api_router.include_router(auditoria.router)
api_router.include_router(chat.router)
api_router.include_router(ciclo_avaliativo.router)
api_router.include_router(verificacao.router)
api_router.include_router(revisao_spec.router)
api_router.include_router(admin.router)
