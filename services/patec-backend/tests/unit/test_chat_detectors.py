import asyncio
import uuid

import pytest

from app.api.v1.endpoints.chat import _executar_acao
from app.services.chat import (
    detectar_intencao_extracao,
    detectar_intencao_revisao_spec,
    detectar_intencao_voltar_fase,
    detectar_sem_complementares,
)


@pytest.mark.parametrize(
    "mensagem",
    [
        # Frases NEGADAS nao devem disparar o detector (C1) — antes o "nao"
        # era ignorado e a JULIA declinava a fase / abria upload contra a vontade.
        "nao quero cancelar o ciclo, esta tudo certo",
        "por favor nao precisa voltar para a analise",
        "nunca volte para a fase anterior, siga em frente",
    ],
)
def test_negacao_nao_dispara_voltar_fase(mensagem):
    assert detectar_intencao_voltar_fase(mensagem) is False


@pytest.mark.parametrize(
    "mensagem",
    [
        "quero subir uma nova revisao do documento da engenharia",
        "a especificacao mudou, tenho uma nova versao",
        "preciso revisar a especificacao",
    ],
)
def test_detecta_revisao_spec(mensagem):
    assert detectar_intencao_revisao_spec(mensagem) is True


@pytest.mark.parametrize(
    "mensagem",
    [
        "nao precisa revisar a especificacao agora",
        "por enquanto sem subir nenhum documento novo",
        "nao quero atualizar o documento da engenharia",
    ],
)
def test_negacao_nao_dispara_revisao_spec(mensagem):
    assert detectar_intencao_revisao_spec(mensagem) is False


# Contrato C5: TODO step-id emitido por frontend/.../derive-step.ts precisa ter
# descricao em _STEP_DESCRICOES, senao a JULIA recebe "n/a" no passo ativo.
# Lista canonica espelhada do derive-step (atualize os dois juntos).
_DERIVE_STEP_IDS = {
    "setup.docs_eng", "setup.docs_complementares", "setup.extrair",
    "requisitos.aprovar",
    "analise.pronta", "analise.docs_forn", "analise.rodando", "analise.erro",
    "analise.resultado",
    "ciclo.rodada_erro", "ciclo.vinculando", "ciclo.vinculacao_review",
    "ciclo.avaliando", "ciclo.decidir", "ciclo.aguardando_fornecedor",
    "verificacao.dispensada", "verificacao.aguardando_proposta",
    "verificacao.rodando", "verificacao.validar",
    "caso.fechar", "caso.fechado",
    "spec.comparando", "spec.diff_decisao", "spec.erro",
}


def test_todos_step_ids_tem_descricao():
    from app.services.chat import _STEP_DESCRICOES

    faltando = _DERIVE_STEP_IDS - set(_STEP_DESCRICOES)
    assert not faltando, f"step-ids sem descricao em _STEP_DESCRICOES: {sorted(faltando)}"


@pytest.mark.parametrize(
    "mensagem",
    [
        # A mensagem exata que originou o bug (JULIA prometia reverter e falhava).
        "quero voltar pra fase da analise, pois tem coisa errada la. "
        "Cancele o ciclo do fornecedor e volte para a analise",
        "cancela o ciclo e volta para a análise",
        "voltar atras",
        "quero reverter o caso para a fase anterior",
        "desfazer o ciclo do fornecedor",
    ],
)
def test_detecta_pedido_de_voltar_fase(mensagem):
    assert detectar_intencao_voltar_fase(mensagem) is True


@pytest.mark.parametrize(
    "mensagem",
    [
        "quero ver a analise",          # visualizar, nao voltar
        "pode reanalisar?",             # acao reanalisar (sem trocar de fase)
        "refazer a analise sem mudar a lista",
        "o item 4 deveria ser status C",  # correcao de item no lugar
        "quero enviar a proposta final do fornecedor",
        "exportar a carta",
    ],
)
def test_nao_dispara_em_pedidos_legitimos(mensagem):
    assert detectar_intencao_voltar_fase(mensagem) is False


@pytest.mark.parametrize(
    "mensagem,perfil",
    [
        ("quero 12 itens", "custom_12"),
        ("10", "custom_10"),
        ("uns 20, por favor", "custom_20"),
        ("extrai todos", "integral"),
        ("pode pegar a tabela inteira", "integral"),
        ("escolhe você os melhores", "padrao"),
        ("tanto faz, pode decidir", "padrao"),
    ],
)
def test_detecta_perfil_de_extracao(mensagem, perfil):
    assert detectar_intencao_extracao(mensagem) == perfil


@pytest.mark.parametrize(
    "mensagem",
    [
        "oi, tudo bem?",      # saudacao nao e "extrair tudo"
        "bom dia, tudo bom?",
        "uso esses métodos",  # "metodos" nao casa "todos"
        "vamos começar",
    ],
)
def test_extracao_nao_dispara_em_ruido(mensagem):
    assert detectar_intencao_extracao(mensagem) is None


@pytest.mark.parametrize(
    "mensagem",
    [
        "não tenho",
        "sem complementares",
        "só esse mesmo",
        "pode seguir",
        "já anexei, pode ir",
        "não, pode prosseguir",
    ],
)
def test_detecta_sem_complementares(mensagem):
    assert detectar_sem_complementares(mensagem) is True


@pytest.mark.parametrize(
    "mensagem",
    [
        "tenho sim, vou anexar a norma",
        "aqui está o datasheet complementar",
        "quero adicionar mais um documento",
    ],
)
def test_sem_complementares_nao_dispara_quando_ha_anexo(mensagem):
    assert detectar_sem_complementares(mensagem) is False


# ---------------------------------------------------------------------------
# extrair_requisitos: threading do escopo (recorte) ate a extracao
# ---------------------------------------------------------------------------


def _exec(acao: dict) -> dict:
    # O branch extrair_requisitos retorna cedo, sem tocar no db/usuario.
    return asyncio.run(_executar_acao(None, uuid.uuid4(), acao, None))


def test_extrair_requisitos_propaga_escopo():
    out = _exec(
        {
            "tipo": "extrair_requisitos",
            "perfil": "integral",
            "escopo": "Apenas o Capitulo 2 (SCOPE OF SUPPLY) - todos os itens da tabela",
        }
    )
    assert out["tipo"] == "extrair_requisitos"
    assert out["perfil"] == "integral"
    assert "Capitulo 2" in out["escopo"]


def test_extrair_requisitos_escopo_documento_inteiro_vira_none():
    out = _exec({"tipo": "extrair_requisitos", "perfil": "padrao", "escopo": "documento inteiro"})
    assert out["escopo"] is None


def test_extrair_requisitos_sem_escopo_vira_none():
    out = _exec({"tipo": "extrair_requisitos", "perfil": "custom_12"})
    assert out["escopo"] is None
    assert out["perfil"] == "custom_12"


def test_extrair_requisitos_perfil_invalido_cai_para_padrao():
    out = _exec({"tipo": "extrair_requisitos", "perfil": "'; DROP TABLE", "escopo": "Cap. 8"})
    assert out["perfil"] == "padrao"
    assert out["escopo"] == "Cap. 8"
