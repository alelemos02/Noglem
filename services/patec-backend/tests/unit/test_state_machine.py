"""
Testes unitários da máquina de estados do ciclo iterativo de avaliação.

Cobre todas as transições válidas, todas as transições inválidas relevantes,
a conversão de classificação IA → evento, e o cálculo de status_global do parecer.
"""
import pytest

from app.services.state_machine import (
    ABERTO,
    AGUARDANDO_FORNECEDOR,
    CONCLUIDO,
    EM_ANALISE,
    EM_REAVALIACAO,
    ESCALONADO,
    PENDENTE_FORNECEDOR,
    RESOLVIDO,
    TransicaoInvalidaError,
    compute_status_global,
    evento_para_classificacao,
    transicionar,
    validar_estado,
)


# ──────────────────────────────────────────────────────────────────────
# Transições válidas
# ──────────────────────────────────────────────────────────────────────

class TestTransicoesValidas:
    def test_aberto_aprovado_vira_resolvido(self):
        assert transicionar(ABERTO, "classificar_aprovado") == RESOLVIDO

    def test_aberto_nao_aprovado_vira_pendente(self):
        assert transicionar(ABERTO, "classificar_nao_aprovado") == PENDENTE_FORNECEDOR

    def test_pendente_respondeu_vira_em_reavaliacao(self):
        assert transicionar(PENDENTE_FORNECEDOR, "fornecedor_respondeu") == EM_REAVALIACAO

    def test_pendente_escalar_vira_escalonado(self):
        assert transicionar(PENDENTE_FORNECEDOR, "escalar") == ESCALONADO

    def test_em_reavaliacao_aceitar_vira_resolvido(self):
        assert transicionar(EM_REAVALIACAO, "aceitar") == RESOLVIDO

    def test_em_reavaliacao_rejeitar_vira_pendente(self):
        assert transicionar(EM_REAVALIACAO, "rejeitar") == PENDENTE_FORNECEDOR


# ──────────────────────────────────────────────────────────────────────
# Transições inválidas — devem levantar TransicaoInvalidaError
# ──────────────────────────────────────────────────────────────────────

class TestTransicoesInvalidas:
    def test_resolvido_nao_aceita_eventos(self):
        with pytest.raises(TransicaoInvalidaError):
            transicionar(RESOLVIDO, "classificar_aprovado")

    def test_escalonado_nao_aceita_eventos(self):
        with pytest.raises(TransicaoInvalidaError):
            transicionar(ESCALONADO, "aceitar")

    def test_aberto_nao_pode_escalar(self):
        with pytest.raises(TransicaoInvalidaError):
            transicionar(ABERTO, "escalar")

    def test_aberto_nao_pode_aceitar(self):
        with pytest.raises(TransicaoInvalidaError):
            transicionar(ABERTO, "aceitar")

    def test_pendente_nao_pode_aceitar(self):
        with pytest.raises(TransicaoInvalidaError):
            transicionar(PENDENTE_FORNECEDOR, "aceitar")

    def test_em_reavaliacao_nao_pode_escalar(self):
        with pytest.raises(TransicaoInvalidaError):
            transicionar(EM_REAVALIACAO, "escalar")

    def test_evento_inexistente(self):
        with pytest.raises(TransicaoInvalidaError):
            transicionar(ABERTO, "evento_fantasma")

    def test_mensagem_de_erro_lista_eventos_validos(self):
        with pytest.raises(TransicaoInvalidaError, match="classificar_aprovado"):
            transicionar(ABERTO, "escalar")


# ──────────────────────────────────────────────────────────────────────
# Conversão classificação IA → evento
# ──────────────────────────────────────────────────────────────────────

class TestEventoParaClassificacao:
    @pytest.mark.parametrize("classif", ["B", "C", "D", "E"])
    def test_nao_aprovados_viram_nao_aprovado(self, classif):
        assert evento_para_classificacao(classif) == "classificar_nao_aprovado"

    def test_aprovado_vira_aprovado(self):
        assert evento_para_classificacao("A") == "classificar_aprovado"


# ──────────────────────────────────────────────────────────────────────
# compute_status_global
# ──────────────────────────────────────────────────────────────────────

class TestComputeStatusGlobal:
    def test_sem_itens_retorna_em_analise(self):
        assert compute_status_global([]) == EM_ANALISE

    def test_todos_abertos_retorna_em_analise(self):
        assert compute_status_global([ABERTO, ABERTO]) == EM_ANALISE

    def test_todos_resolvidos_retorna_concluido(self):
        assert compute_status_global([RESOLVIDO, RESOLVIDO]) == CONCLUIDO

    def test_todos_escalonados_retorna_concluido(self):
        assert compute_status_global([ESCALONADO, ESCALONADO]) == CONCLUIDO

    def test_mix_resolvido_e_escalonado_retorna_concluido(self):
        assert compute_status_global([RESOLVIDO, ESCALONADO, RESOLVIDO]) == CONCLUIDO

    def test_qualquer_em_reavaliacao_retorna_em_reavaliacao(self):
        resultado = compute_status_global([RESOLVIDO, EM_REAVALIACAO, PENDENTE_FORNECEDOR])
        assert resultado == EM_REAVALIACAO

    def test_em_reavaliacao_tem_prioridade_sobre_pendente(self):
        resultado = compute_status_global([PENDENTE_FORNECEDOR, EM_REAVALIACAO])
        assert resultado == EM_REAVALIACAO

    def test_pendente_sem_reavaliacao_retorna_aguardando(self):
        resultado = compute_status_global([RESOLVIDO, PENDENTE_FORNECEDOR])
        assert resultado == AGUARDANDO_FORNECEDOR

    def test_so_pendente_retorna_aguardando(self):
        assert compute_status_global([PENDENTE_FORNECEDOR]) == AGUARDANDO_FORNECEDOR

    def test_mix_aberto_e_resolvido_retorna_em_analise(self):
        assert compute_status_global([ABERTO, RESOLVIDO]) == EM_ANALISE


# ──────────────────────────────────────────────────────────────────────
# Ciclo completo — simula uma rodada de ponta a ponta
# ──────────────────────────────────────────────────────────────────────

class TestCicloCompleto:
    def test_ciclo_item_rejeitado_resolve_na_segunda_rodada(self):
        estado = ABERTO

        # Análise inicial: rejeitado
        estado = transicionar(estado, "classificar_nao_aprovado")
        assert estado == PENDENTE_FORNECEDOR

        # Fornecedor responde
        estado = transicionar(estado, "fornecedor_respondeu")
        assert estado == EM_REAVALIACAO

        # Engenheiro aceita a resposta
        estado = transicionar(estado, "aceitar")
        assert estado == RESOLVIDO

    def test_ciclo_item_rejeita_duas_vezes_e_escala(self):
        estado = ABERTO
        estado = transicionar(estado, "classificar_nao_aprovado")
        estado = transicionar(estado, "fornecedor_respondeu")
        estado = transicionar(estado, "rejeitar")
        assert estado == PENDENTE_FORNECEDOR

        # Segunda rodada: fornecedor tenta de novo, ainda rejeitado
        estado = transicionar(estado, "fornecedor_respondeu")
        estado = transicionar(estado, "rejeitar")
        assert estado == PENDENTE_FORNECEDOR

        # Decisão de escalar
        estado = transicionar(estado, "escalar")
        assert estado == ESCALONADO

    def test_parecer_concluido_so_quando_todos_encerrados(self):
        estados = [RESOLVIDO, PENDENTE_FORNECEDOR, ESCALONADO]
        assert compute_status_global(estados) == AGUARDANDO_FORNECEDOR

        # Resolve o pendente
        estados[1] = RESOLVIDO
        assert compute_status_global(estados) == CONCLUIDO


# ──────────────────────────────────────────────────────────────────────
# validar_estado
# ──────────────────────────────────────────────────────────────────────

class TestValidarEstado:
    @pytest.mark.parametrize(
        "estado",
        [ABERTO, PENDENTE_FORNECEDOR, EM_REAVALIACAO, RESOLVIDO, ESCALONADO],
    )
    def test_estados_validos_nao_levantam(self, estado):
        validar_estado(estado)  # não deve levantar

    def test_estado_invalido_levanta_value_error(self):
        with pytest.raises(ValueError, match="Estado desconhecido"):
            validar_estado("INEXISTENTE")
