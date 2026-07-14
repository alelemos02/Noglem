import asyncio
import uuid

import pytest

from app.api.v1.endpoints.chat import _acao_valida, _executar_acao
from app.services.chat import (
    detectar_intencao_extracao,
    detectar_intencao_revisao_spec,
    detectar_intencao_voltar_fase,
    detectar_promessa_aplicacao_itens,
    detectar_sem_complementares,
    extrair_paginas_citadas,
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


# ──────────────────────────────────────────────────────────────────────
# Ajuste #10 — detector de "promessa de aplicacao sem <acao>"
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "resposta",
    [
        "Apliquei a correção no item 4 como você pediu.",
        "Estou aplicando a atualização na tabela do caso.",
        "Pronto, atualizei o status do item 2 para C.",
        "A tabela do caso foi atualizada com a nova justificativa.",
        "Vou aplicar agora a mudança no item 7.",
        # Caso real da transcricao que originou o ajuste #10
        "Estou alterando agora mesmo a descrição e o valor requerido dos itens.",
    ],
)
def test_detecta_promessa_aplicacao(resposta):
    assert detectar_promessa_aplicacao_itens(resposta) is True


@pytest.mark.parametrize(
    "resposta",
    [
        # Pergunta nao e promessa
        "Quer que eu aplique essa mudança no item 4?",
        "Posso atualizar o item 2 para status C?",
        "Devo corrigir a justificativa do item 3?",
        # Condicional aguardando confirmacao
        "Se você confirmar, eu aplico a alteração na tabela.",
        "Quando você confirmar, atualizo o item 5.",
        # Negacao
        "Não apliquei nenhuma mudança na tabela ainda.",
        "Ainda não atualizei o item 4 — preciso da sua confirmação.",
        # Referencia a aplicacao de turno anterior
        "Como apliquei anteriormente no item 4, o status já está em C.",
        "Na resposta anterior atualizei o item 2 conforme combinado.",
        # Verbo sem alvo de tabela/item
        "Apliquei meus conhecimentos nessa avaliação.",
    ],
)
def test_promessa_nao_dispara(resposta):
    assert detectar_promessa_aplicacao_itens(resposta) is False


# ──────────────────────────────────────────────────────────────────────
# Ajuste #11 — extracao de paginas citadas (guarda anti-alucinacao)
# ──────────────────────────────────────────────────────────────────────

def test_extrair_paginas_citadas_basico():
    assert extrair_paginas_citadas("veja a página 10 e a pag. 29 do TK-8") == {10, 29}


def test_extrair_paginas_citadas_sem_citacao():
    assert extrair_paginas_citadas("nenhuma referência de local aqui") == set()


def test_extrair_paginas_citadas_nao_captura_numero_solto():
    # "110 pontos" apos a pagina NAO vira pagina citada (evita acusacao em falso)
    assert extrair_paginas_citadas("tabela da página 29 e 110 pontos de CFTV") == {29}


# ──────────────────────────────────────────────────────────────────────
# Ajuste #10 — _acao_valida estendido para atualizar_itens
# ──────────────────────────────────────────────────────────────────────

def test_acao_valida_patch_de_itens_ok():
    assert _acao_valida(
        {"tipo": "atualizar_itens", "itens": [{"numero": 4, "status": "B"}]}
    ) is True


@pytest.mark.parametrize(
    "payload",
    [
        {"tipo": "atualizar_itens", "itens": []},
        {"tipo": "atualizar_itens", "itens": [{"status": "B"}]},
        {"tipo": "atualizar_itens", "itens": [{"numero": "4", "status": "B"}]},
        {"tipo": "atualizar_itens", "itens": [{"numero": True}]},
        {"tipo": "atualizar_itens", "itens": [{"numero": 1}] * 51},
        {"tipo": None, "motivo": "sem_alteracao_nesta_resposta"},
        {"tipo": None},
        None,
    ],
)
def test_acao_valida_rejeita_shapes_invalidos(payload):
    assert _acao_valida(payload) is False


def test_acao_valida_atualizar_requisitos_inalterada():
    # O shape historico (lista, mesmo vazia) segue aceito — usado pelo repair
    assert _acao_valida({"tipo": "atualizar_requisitos", "requisitos": []}) is True
