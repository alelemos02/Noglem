"""
Testes unitários da revisão de especificação (R4) — normalização do diff e
derivação dos cenários A/B/C.
"""
from app.services.spec_diff import normalizar_diff

NUMEROS = {1, 2, 3}


class TestNormalizarDiff:
    def test_cenario_a_nada_mudou(self):
        diff = normalizar_diff({"inalterados": [1, 2, 3]}, NUMEROS)
        assert diff["cenario"] == "A"
        assert diff["inalterados"] == [1, 2, 3]
        assert diff["alterados"] == []
        assert diff["novos"] == []
        assert diff["removidos"] == []

    def test_cenario_b_so_novos(self):
        data = {
            "novos": [
                {"descricao_requisito": "Novo requisito de aterramento", "prioridade": "ALTA"}
            ],
        }
        diff = normalizar_diff(data, NUMEROS)
        assert diff["cenario"] == "B"
        assert len(diff["novos"]) == 1
        assert diff["inalterados"] == [1, 2, 3]

    def test_cenario_c_alterados(self):
        data = {
            "alterados": [
                {
                    "numero": 2,
                    "campos_alterados": {
                        "valor_requerido": {"antes": "0-100 bar", "depois": "0-160 bar"}
                    },
                    "justificativa": "Faixa ampliada.",
                }
            ],
        }
        diff = normalizar_diff(data, NUMEROS)
        assert diff["cenario"] == "C"
        assert diff["alterados"][0]["numero"] == 2
        assert diff["inalterados"] == [1, 3]

    def test_cenario_c_removidos(self):
        diff = normalizar_diff({"removidos": [3]}, NUMEROS)
        assert diff["cenario"] == "C"
        assert diff["removidos"] == [3]
        assert diff["inalterados"] == [1, 2]

    def test_numero_invalido_descartado(self):
        data = {
            "alterados": [
                {"numero": 99, "campos_alterados": {"valor_requerido": {"antes": "x", "depois": "y"}}}
            ],
            "removidos": [42],
        }
        diff = normalizar_diff(data, NUMEROS)
        assert diff["cenario"] == "A"

    def test_campo_desconhecido_descartado(self):
        data = {
            "alterados": [
                {"numero": 1, "campos_alterados": {"campo_inventado": {"antes": "a", "depois": "b"}}}
            ],
        }
        diff = normalizar_diff(data, NUMEROS)
        # Sem campos válidos, o alterado cai fora → cenário A
        assert diff["cenario"] == "A"

    def test_alterado_tem_precedencia_sobre_removido(self):
        data = {
            "alterados": [
                {"numero": 1, "campos_alterados": {"valor_requerido": {"antes": "a", "depois": "b"}}}
            ],
            "removidos": [1],
        }
        diff = normalizar_diff(data, NUMEROS)
        assert diff["removidos"] == []
        assert len(diff["alterados"]) == 1

    def test_novo_sem_descricao_descartado_e_prioridade_normalizada(self):
        data = {
            "novos": [
                {"descricao_requisito": "", "prioridade": "ALTA"},
                {"descricao_requisito": "Valido", "prioridade": "URGENTE"},
            ],
        }
        diff = normalizar_diff(data, NUMEROS)
        assert len(diff["novos"]) == 1
        assert diff["novos"][0]["prioridade"] == "MEDIA"

    def test_cenario_da_llm_e_ignorado_e_rederivado(self):
        # LLM disse "A", mas há um item alterado — o cenário local prevalece
        data = {
            "cenario": "A",
            "alterados": [
                {"numero": 1, "campos_alterados": {"valor_requerido": {"antes": "a", "depois": "b"}}}
            ],
        }
        diff = normalizar_diff(data, NUMEROS)
        assert diff["cenario"] == "C"
