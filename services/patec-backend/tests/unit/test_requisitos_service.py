"""
Testes unitários da Fase 1 do caso técnico: extração de requisitos (blocos 8-9),
normalização da saída da LLM e hash de cache baseado em requisitos (R1).

Nenhum teste toca banco ou rede — a chamada LLM é mockada.
"""
from unittest.mock import patch

import pytest

from app.services.requisitos import _call_extracao_llm
from app.services.tasks import PROMPT_VERSION, _compute_docs_hash


class _ParecerStub:
    id = "00000000-0000-0000-0000-000000000001"
    projeto = "Projeto Teste"
    numero_parecer = "PT-001"


def _mock_llm_response(payload: str):
    return patch("app.services.requisitos.call_llm", return_value=payload)


# ──────────────────────────────────────────────────────────────────────
# Normalização da saída da LLM na extração
# ──────────────────────────────────────────────────────────────────────

class TestExtracaoNormalizacao:
    def test_saida_valida_normalizada(self):
        resposta = """
        {
          "requisitos": [
            {"numero": 7, "categoria": "Processo", "descricao_requisito": "Faixa 0-100 bar",
             "valor_requerido": "0-100 bar", "prioridade": "ALTA",
             "norma_referencia": null, "referencia_engenharia": "ET-001 p.3"}
          ],
          "total_itens": 1,
          "resumo": "Foco em processo."
        }
        """
        with _mock_llm_response(resposta):
            data = _call_extracao_llm("texto eng", _ParecerStub(), "padrao", None)

        assert data["total_itens"] == 1
        # Renumera sequencialmente a partir de 1, ignorando numeração da LLM
        assert data["requisitos"][0]["numero"] == 1
        assert data["requisitos"][0]["valor_requerido"] == "0-100 bar"
        assert data["resumo"] == "Foco em processo."

    def test_prioridade_invalida_vira_media(self):
        resposta = """
        {"requisitos": [{"numero": 1, "descricao_requisito": "X", "prioridade": "URGENTE"}],
         "total_itens": 1, "resumo": ""}
        """
        with _mock_llm_response(resposta):
            data = _call_extracao_llm("texto", _ParecerStub(), "padrao", None)

        assert data["requisitos"][0]["prioridade"] == "MEDIA"

    def test_campos_ausentes_recebem_defaults(self):
        resposta = """
        {"requisitos": [{"numero": 1, "descricao_requisito": "Y", "prioridade": "BAIXA"}],
         "total_itens": 1, "resumo": ""}
        """
        with _mock_llm_response(resposta):
            data = _call_extracao_llm("texto", _ParecerStub(), "padrao", None)

        item = data["requisitos"][0]
        assert item["valor_requerido"] is None
        assert item["norma_referencia"] is None
        assert item["referencia_engenharia"] == ""
        assert item["categoria"] is None

    def test_compat_chave_legada_itens_candidatos(self):
        resposta = """
        {"itens_candidatos": [{"numero": 1, "descricao_requisito": "Z", "prioridade": "ALTA"}],
         "total_itens": 1, "resumo": "legado"}
        """
        with _mock_llm_response(resposta):
            data = _call_extracao_llm("texto", _ParecerStub(), "padrao", None)

        assert len(data["requisitos"]) == 1

    def test_feedback_remove_limite_de_perfil(self):
        resposta = '{"requisitos": [], "total_itens": 0, "resumo": ""}'
        with _mock_llm_response(resposta) as mocked:
            _call_extracao_llm("texto", _ParecerStub(), "simples", "incluir tudo de eletrica")

        user_content = mocked.call_args[0][1]
        assert "RESTRICAO DE VOLUME" not in user_content
        assert "incluir tudo de eletrica" in user_content

    def test_sem_feedback_aplica_limite_de_perfil(self):
        resposta = '{"requisitos": [], "total_itens": 0, "resumo": ""}'
        with _mock_llm_response(resposta) as mocked:
            _call_extracao_llm("texto", _ParecerStub(), "simples", None)

        user_content = mocked.call_args[0][1]
        assert "NO MAXIMO 10" in user_content


# ──────────────────────────────────────────────────────────────────────
# Hash de cache (R1: requisitos fazem parte do escopo, perfil não)
# ──────────────────────────────────────────────────────────────────────

class TestComputeDocsHash:
    REQS = [{"numero": 1, "descricao_requisito": "Faixa 0-100 bar"}]

    def _hash(self, **overrides):
        params = dict(
            requisitos_payload=self.REQS,
            eng_text="eng",
            forn_text="forn",
            disciplina="instrumentacao",
            idioma_relatorio="pt",
            anexos_text="",
        )
        params.update(overrides)
        return _compute_docs_hash(**params)

    def test_deterministico(self):
        assert self._hash() == self._hash()

    def test_muda_com_requisitos(self):
        outro = [{"numero": 1, "descricao_requisito": "Faixa 0-200 bar"}]
        assert self._hash() != self._hash(requisitos_payload=outro)

    def test_muda_com_fornecedor(self):
        assert self._hash() != self._hash(forn_text="outro texto")

    def test_muda_com_disciplina_e_idioma(self):
        assert self._hash() != self._hash(disciplina="eletrico")
        assert self._hash() != self._hash(idioma_relatorio="en")

    def test_versao_do_prompt_no_hash(self, monkeypatch):
        # Bumpar a versao do prompt invalida o cache (entra no hash)
        assert isinstance(PROMPT_VERSION, str) and PROMPT_VERSION
        baseline = self._hash()
        monkeypatch.setattr("app.services.tasks.PROMPT_VERSION", "VERSAO_DIFERENTE")
        assert self._hash() != baseline


# ──────────────────────────────────────────────────────────────────────
# llm_client: parsing e reparo de JSON
# ──────────────────────────────────────────────────────────────────────

class TestLlmClientExtractJson:
    def test_json_simples(self):
        from app.services.llm_client import extract_json

        assert extract_json('{"a": 1}') == {"a": 1}

    def test_json_em_bloco_markdown(self):
        from app.services.llm_client import extract_json

        assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_json_truncado_reparado(self):
        from app.services.llm_client import extract_json

        result = extract_json('{"itens": [{"numero": 1, "status": "A"}, {"numero": 2')
        assert result["itens"][0]["numero"] == 1

    def test_json_invalido_levanta(self):
        import json

        from app.services.llm_client import extract_json

        with pytest.raises(json.JSONDecodeError):
            extract_json("nao e json")
