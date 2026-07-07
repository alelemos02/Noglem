"""
Testes unitários das máquinas de estado do caso técnico (v2).

Cobre: transições de item (incluindo decisões humanas W4 e eventos da revisão
de spec W7), transições de fase do caso, avanço automático e resumo do ciclo.
"""
import pytest

from app.services.state_machine import (
    ABERTO,
    ACEITO,
    ANALISE,
    CICLO_FORNECEDOR,
    DESATIVADO,
    EM_REAVALIACAO,
    FECHADO,
    PENDENTE_FORNECEDOR,
    REPROVADO,
    SETUP,
    VERIFICACAO_FINAL,
    FaseInvalidaError,
    TransicaoInvalidaError,
    compute_avanco_automatico,
    compute_resumo_ciclo,
    evento_para_classificacao,
    evento_para_decisao,
    todos_aceitos,
    transicionar,
    transicionar_fase,
    validar_estado,
)


# ──────────────────────────────────────────────────────────────────────
# Transições de item válidas
# ──────────────────────────────────────────────────────────────────────

class TestTransicoesItem:
    def test_aberto_aprovado_vira_aceito(self):
        assert transicionar(ABERTO, "classificar_aprovado") == ACEITO

    def test_aberto_nao_aprovado_vira_pendente(self):
        assert transicionar(ABERTO, "classificar_nao_aprovado") == PENDENTE_FORNECEDOR

    def test_pendente_respondeu_vira_em_reavaliacao(self):
        assert transicionar(PENDENTE_FORNECEDOR, "fornecedor_respondeu") == EM_REAVALIACAO

    def test_decidir_aceitar(self):
        assert transicionar(EM_REAVALIACAO, "decidir_aceitar") == ACEITO

    def test_decidir_esclarecer_volta_ao_fornecedor(self):
        assert transicionar(EM_REAVALIACAO, "decidir_esclarecer") == PENDENTE_FORNECEDOR

    def test_decidir_rejeitar_volta_ao_fornecedor(self):
        assert transicionar(EM_REAVALIACAO, "decidir_rejeitar") == PENDENTE_FORNECEDOR

    def test_decidir_reprovar_caso(self):
        assert transicionar(EM_REAVALIACAO, "decidir_reprovar_caso") == REPROVADO

    def test_desfazer_decisao_de_aceito_volta_para_reavaliacao(self):
        assert transicionar(ACEITO, "desfazer_decisao") == EM_REAVALIACAO

    def test_desfazer_decisao_de_pendente_volta_para_reavaliacao(self):
        # ESCLARECER/REJEITAR levam o item a PENDENTE; desfazer volta à fila.
        assert transicionar(PENDENTE_FORNECEDOR, "desfazer_decisao") == EM_REAVALIACAO


class TestEventosRevisaoSpec:
    def test_aceito_reabre_por_revisao_spec(self):
        assert transicionar(ACEITO, "reabrir_revisao_spec") == ABERTO

    def test_pendente_reabre_por_revisao_spec(self):
        assert transicionar(PENDENTE_FORNECEDOR, "reabrir_revisao_spec") == ABERTO

    def test_desativado_nao_reabre(self):
        with pytest.raises(TransicaoInvalidaError):
            transicionar(DESATIVADO, "reabrir_revisao_spec")

    def test_desativar_de_qualquer_estado(self):
        for estado in (ABERTO, PENDENTE_FORNECEDOR, EM_REAVALIACAO, ACEITO):
            assert transicionar(estado, "desativar") == DESATIVADO


class TestTransicoesItemInvalidas:
    def test_escalonamento_foi_removido(self):
        with pytest.raises(TransicaoInvalidaError):
            transicionar(PENDENTE_FORNECEDOR, "escalar")

    def test_decisoes_antigas_nao_existem(self):
        with pytest.raises(TransicaoInvalidaError):
            transicionar(EM_REAVALIACAO, "aceitar")

    def test_aceito_e_terminal_para_decisoes(self):
        with pytest.raises(TransicaoInvalidaError):
            transicionar(ACEITO, "decidir_aceitar")

    def test_reprovado_e_terminal(self):
        with pytest.raises(TransicaoInvalidaError):
            transicionar(REPROVADO, "fornecedor_respondeu")

    def test_aberto_nao_decide(self):
        with pytest.raises(TransicaoInvalidaError):
            transicionar(ABERTO, "decidir_aceitar")


class TestMapeamentos:
    def test_classificacao_a_aprova(self):
        assert evento_para_classificacao("A") == "classificar_aprovado"

    @pytest.mark.parametrize("status", ["B", "C", "D", "E"])
    def test_classificacoes_nao_aprovadas(self, status):
        assert evento_para_classificacao(status) == "classificar_nao_aprovado"

    @pytest.mark.parametrize(
        ("decisao", "evento"),
        [
            ("ACEITAR", "decidir_aceitar"),
            ("ESCLARECER", "decidir_esclarecer"),
            ("REJEITAR", "decidir_rejeitar"),
            ("REPROVAR_CASO", "decidir_reprovar_caso"),
        ],
    )
    def test_decisao_para_evento(self, decisao, evento):
        assert evento_para_decisao(decisao) == evento

    def test_decisao_invalida(self):
        with pytest.raises(ValueError):
            evento_para_decisao("ATENDE")  # vocabulário antigo

    def test_validar_estado_aceita_novos(self):
        for estado in (ABERTO, ACEITO, REPROVADO, DESATIVADO):
            validar_estado(estado)

    def test_validar_estado_rejeita_antigos(self):
        with pytest.raises(ValueError):
            validar_estado("RESOLVIDO")
        with pytest.raises(ValueError):
            validar_estado("ESCALONADO")


# ──────────────────────────────────────────────────────────────────────
# Fases do caso
# ──────────────────────────────────────────────────────────────────────

class TestFasesCaso:
    def test_fluxo_feliz(self):
        fase = transicionar_fase(SETUP, "extrair_requisitos")
        assert fase == "REQUISITOS"
        fase = transicionar_fase(fase, "aprovar_requisitos")
        assert fase == ANALISE
        fase = transicionar_fase(fase, "iniciar_ciclo")
        assert fase == CICLO_FORNECEDOR
        fase = transicionar_fase(fase, "todos_itens_aceitos")
        assert fase == VERIFICACAO_FINAL
        fase = transicionar_fase(fase, "fechar")
        assert fase == FECHADO

    def test_w1_direto_do_setup(self):
        assert transicionar_fase(SETUP, "aprovar_requisitos") == ANALISE

    def test_reaprovacao_pre_analise(self):
        assert transicionar_fase(ANALISE, "aprovar_requisitos") == ANALISE

    def test_reprovar_caso_fecha_do_ciclo(self):
        assert transicionar_fase(CICLO_FORNECEDOR, "reprovar_caso") == FECHADO

    def test_fechar_caso_travado_no_ciclo(self):
        assert transicionar_fase(CICLO_FORNECEDOR, "fechar") == FECHADO

    def test_revisao_spec_regride_para_ciclo(self):
        assert transicionar_fase(VERIFICACAO_FINAL, "revisao_spec") == CICLO_FORNECEDOR
        assert transicionar_fase(ANALISE, "revisao_spec") == CICLO_FORNECEDOR

    def test_caso_fechado_e_terminal(self):
        with pytest.raises(FaseInvalidaError):
            transicionar_fase(FECHADO, "iniciar_ciclo")

    def test_nao_pula_fases(self):
        with pytest.raises(FaseInvalidaError):
            transicionar_fase(SETUP, "iniciar_ciclo")


# ──────────────────────────────────────────────────────────────────────
# Avanço automático e resumo
# ──────────────────────────────────────────────────────────────────────

class TestAvancoAutomatico:
    def test_todos_aceitos_avanca(self):
        estados = [ACEITO, ACEITO, ACEITO]
        assert compute_avanco_automatico(CICLO_FORNECEDOR, estados) == VERIFICACAO_FINAL

    def test_desativados_nao_bloqueiam(self):
        estados = [ACEITO, DESATIVADO, ACEITO]
        assert compute_avanco_automatico(CICLO_FORNECEDOR, estados) == VERIFICACAO_FINAL

    def test_pendente_bloqueia(self):
        estados = [ACEITO, PENDENTE_FORNECEDOR]
        assert compute_avanco_automatico(CICLO_FORNECEDOR, estados) is None

    def test_so_avanca_do_ciclo(self):
        assert compute_avanco_automatico(ANALISE, [ACEITO]) is None

    def test_sem_itens_nao_avanca(self):
        assert compute_avanco_automatico(CICLO_FORNECEDOR, []) is None
        assert compute_avanco_automatico(CICLO_FORNECEDOR, [DESATIVADO]) is None

    def test_todos_aceitos_helper(self):
        assert todos_aceitos([ACEITO, ACEITO])
        assert todos_aceitos([ACEITO, DESATIVADO])
        assert not todos_aceitos([ACEITO, EM_REAVALIACAO])
        assert not todos_aceitos([])


class TestResumoCiclo:
    def test_contagens(self):
        estados = [ACEITO, PENDENTE_FORNECEDOR, EM_REAVALIACAO, DESATIVADO, REPROVADO, ABERTO]
        resumo = compute_resumo_ciclo(estados)
        assert resumo["total_itens"] == 5  # desativado fora
        assert resumo["aceitos"] == 1
        assert resumo["aguardando_fornecedor"] == 1
        assert resumo["em_reavaliacao"] == 1
        assert resumo["reprovados"] == 1
        assert resumo["abertos"] == 1
        assert resumo["desativados"] == 1
        assert resumo["todos_aceitos"] is False

    def test_todos_aceitos_no_resumo(self):
        assert compute_resumo_ciclo([ACEITO, ACEITO])["todos_aceitos"] is True
