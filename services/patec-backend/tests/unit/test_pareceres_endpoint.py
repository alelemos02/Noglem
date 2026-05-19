import uuid
from datetime import UTC, datetime

from app.api.v1.endpoints.pareceres import _to_response
from app.models.parecer import Parecer


def test_to_response_includes_disciplina():
    now = datetime.now(UTC)
    parecer = Parecer(
        id=uuid.uuid4(),
        numero_parecer="PYTEST-DISC-1",
        projeto="Projeto",
        fornecedor="Fornecedor",
        revisao="0",
        disciplina="eletrico",
        status_processamento="pendente",
        parecer_geral=None,
        comentario_geral=None,
        conclusao=None,
        total_itens=0,
        total_aprovados=0,
        total_aprovados_comentarios=0,
        total_rejeitados=0,
        total_info_ausente=0,
        total_itens_adicionais=0,
        criado_em=now,
        atualizado_em=now,
    )

    response = _to_response(parecer)

    assert response.disciplina == "eletrico"
