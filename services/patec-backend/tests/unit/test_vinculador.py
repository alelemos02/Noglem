"""
Testes unitários da vinculação automática (bloco 23, W3) — LLM mockada.
"""
import json
from unittest.mock import patch

from app.services.vinculador import vincular_proposta_revisada, vincular_respostas_llm

ITENS = [
    {"numero": 1, "descricao_requisito": "Faixa 0-100 bar", "valor_requerido": "0-100 bar", "pendencia": "Confirmar faixa"},
    {"numero": 2, "descricao_requisito": "Certificacao Ex", "valor_requerido": "Ex ia IIC", "pendencia": "Enviar certificado"},
    {"numero": 3, "descricao_requisito": "Material 316L", "valor_requerido": "316L", "pendencia": None},
]


def _mock(payload: dict):
    return patch(
        "app.services.vinculador.call_llm",
        return_value=json.dumps(payload, ensure_ascii=False),
    )


class TestVincularRespostasLlm:
    def test_saida_valida(self):
        payload = {
            "vinculos": [
                {"item_numero": 1, "trecho": "A faixa sera 0-100 bar.", "confianca": "ALTA"},
                {"item_numero": 2, "trecho": "Certificado Ex em anexo.", "confianca": "MEDIA"},
            ],
            "trechos_sem_item": ["Prazo de entrega: 12 semanas"],
            "itens_sem_resposta": [3],
        }
        with _mock(payload):
            r = vincular_respostas_llm("texto da resposta", ITENS, "RESPOSTA_ITENS")

        assert len(r["vinculos"]) == 2
        assert r["vinculos"][0]["confianca"] == "ALTA"
        assert r["itens_sem_resposta"] == [3]
        assert r["trechos_sem_item"] == ["Prazo de entrega: 12 semanas"]

    def test_item_numero_invalido_descartado(self):
        payload = {
            "vinculos": [
                {"item_numero": 99, "trecho": "x", "confianca": "ALTA"},
                {"item_numero": "1", "trecho": "y", "confianca": "ALTA"},
                {"item_numero": 2, "trecho": "ok", "confianca": "ALTA"},
            ],
        }
        with _mock(payload):
            r = vincular_respostas_llm("texto", ITENS, "EMAIL_AVULSO")

        assert [v["item_numero"] for v in r["vinculos"]] == [2]
        # Itens 1 e 3 ficam sem resposta (99 e "1" foram descartados)
        assert r["itens_sem_resposta"] == [1, 3]

    def test_vinculo_duplicado_descartado(self):
        payload = {
            "vinculos": [
                {"item_numero": 1, "trecho": "primeiro", "confianca": "ALTA"},
                {"item_numero": 1, "trecho": "segundo", "confianca": "BAIXA"},
            ],
        }
        with _mock(payload):
            r = vincular_respostas_llm("texto", ITENS, "RESPOSTA_ITENS")

        assert len(r["vinculos"]) == 1
        assert r["vinculos"][0]["trecho"] == "primeiro"

    def test_confianca_invalida_vira_baixa(self):
        payload = {"vinculos": [{"item_numero": 1, "trecho": "x", "confianca": "CERTEZA"}]}
        with _mock(payload):
            r = vincular_respostas_llm("texto", ITENS, "RESPOSTA_ITENS")

        assert r["vinculos"][0]["confianca"] == "BAIXA"

    def test_itens_sem_resposta_derivado_quando_ausente(self):
        payload = {"vinculos": [{"item_numero": 2, "trecho": "x", "confianca": "ALTA"}]}
        with _mock(payload):
            r = vincular_respostas_llm("texto", ITENS, "RESPOSTA_ITENS")

        assert r["itens_sem_resposta"] == [1, 3]


class TestVincularPropostaRevisada:
    def test_um_vinculo_por_item_sem_llm(self):
        r = vincular_proposta_revisada(ITENS)
        assert len(r["vinculos"]) == 3
        assert all(v["trecho"] is None for v in r["vinculos"])
        assert all(v["confianca"] == "ALTA" for v in r["vinculos"])
        assert r["itens_sem_resposta"] == []
