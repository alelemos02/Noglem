"""
Testes da reavaliacao cirurgica de itens (ajuste #13) — parte pura, sem BD/rede.
"""
import pytest

from app.api.v1.endpoints.chat import _acao_valida
from app.services.reavaliacao import REAVALIA_MAX_ITENS, _calcular_atualizacoes


# ──────────────────────────────────────────────────────────────────────
# _calcular_atualizacoes — cruzamento resposta LLM × itens pedidos
# ──────────────────────────────────────────────────────────────────────

def _resposta(*itens):
    return {"itens": list(itens)}


def test_status_a_vai_para_aceito_e_limpa_acao():
    ups = _calcular_atualizacoes(
        {3: "PENDENTE_FORNECEDOR"},
        _resposta({
            "numero": 3,
            "status": "A",
            "justificativa_tecnica": "Proposta confirma 110 pontos.",
            "acao_requerida": "texto que deve ser descartado",
            "valor_fornecedor": "110 pontos",
        }),
    )
    assert len(ups) == 1
    assert ups[0]["estado"] == "ACEITO"
    assert ups[0]["acao_requerida"] is None
    assert ups[0]["valor_fornecedor"] == "110 pontos"


def test_status_b_reabre_item_aceito_para_pendente():
    ups = _calcular_atualizacoes(
        {1: "ACEITO"},
        _resposta({
            "numero": 1,
            "status": "B",
            "justificativa_tecnica": "Rack 19 pol nao confirmado.",
            "acao_requerida": "Confirmar rack 19 pol e certificacao OTDR",
        }),
    )
    assert ups[0]["estado"] == "PENDENTE_FORNECEDOR"
    assert "rack" in ups[0]["acao_requerida"].lower()


def test_status_d_de_em_reavaliacao_vai_para_pendente():
    ups = _calcular_atualizacoes(
        {2: "EM_REAVALIACAO"},
        _resposta({"numero": 2, "status": "D", "justificativa_tecnica": "Ausente."}),
    )
    assert ups[0]["estado"] == "PENDENTE_FORNECEDOR"


def test_numero_nao_pedido_e_shapes_invalidos_ignorados():
    ups = _calcular_atualizacoes(
        {1: "ACEITO"},
        _resposta(
            {"numero": 9, "status": "B"},          # nao pedido
            {"numero": "1", "status": "B"},        # numero string
            {"numero": True, "status": "B"},       # bool
            "lixo",                                 # shape errado
            {"numero": 1, "status": "X"},          # status invalido
        ),
    )
    assert ups == []


def test_duplicado_primeira_resposta_vence():
    ups = _calcular_atualizacoes(
        {1: "PENDENTE_FORNECEDOR"},
        _resposta(
            {"numero": 1, "status": "B", "justificativa_tecnica": "primeira"},
            {"numero": 1, "status": "A", "justificativa_tecnica": "segunda"},
        ),
    )
    assert len(ups) == 1
    assert ups[0]["status"] == "B"


def test_campos_vazios_viram_none():
    ups = _calcular_atualizacoes(
        {1: "PENDENTE_FORNECEDOR"},
        _resposta({
            "numero": 1,
            "status": "D",
            "justificativa_tecnica": "   ",
            "acao_requerida": None,
            "valor_fornecedor": "",
        }),
    )
    assert ups[0]["justificativa_tecnica"] is None
    assert ups[0]["acao_requerida"] is None
    assert ups[0]["valor_fornecedor"] is None


def test_cap_de_itens_documentado():
    assert REAVALIA_MAX_ITENS == 15


# ──────────────────────────────────────────────────────────────────────
# _acao_valida — shape da acao reavaliar_itens
# ──────────────────────────────────────────────────────────────────────

def test_acao_valida_reavaliar_ok():
    assert _acao_valida({"tipo": "reavaliar_itens", "numeros": [1, 2, 3]}) is True


@pytest.mark.parametrize(
    "payload",
    [
        {"tipo": "reavaliar_itens", "numeros": []},
        {"tipo": "reavaliar_itens", "numeros": ["1"]},
        {"tipo": "reavaliar_itens", "numeros": [True]},
        {"tipo": "reavaliar_itens", "numeros": [1] * 51},
        {"tipo": "reavaliar_itens"},
    ],
)
def test_acao_valida_reavaliar_rejeita(payload):
    assert _acao_valida(payload) is False
