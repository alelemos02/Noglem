"""
Testes unitários da Fase 1 do caso técnico: extração de requisitos (blocos 8-9),
normalização da saída da LLM e hash de cache baseado em requisitos (R1).

Nenhum teste toca banco ou rede — a chamada LLM é mockada.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.services.requisitos import (
    _ANEXO_FULLTEXT_MAX,
    _anexos_citados,
    _call_extracao_llm,
    _merge_decomposicoes,
    _montar_texto_anexo_sync,
    _requisitos_citantes,
    _resolver_amarracoes_sync,
    _revisar_extracao_sync,
)
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
            data = _call_extracao_llm("texto eng", _ParecerStub(), "padrao", None, None)

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
            data = _call_extracao_llm("texto", _ParecerStub(), "padrao", None, None)

        assert data["requisitos"][0]["prioridade"] == "MEDIA"

    def test_campos_ausentes_recebem_defaults(self):
        resposta = """
        {"requisitos": [{"numero": 1, "descricao_requisito": "Y", "prioridade": "BAIXA"}],
         "total_itens": 1, "resumo": ""}
        """
        with _mock_llm_response(resposta):
            data = _call_extracao_llm("texto", _ParecerStub(), "padrao", None, None)

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
            data = _call_extracao_llm("texto", _ParecerStub(), "padrao", None, None)

        assert len(data["requisitos"]) == 1

    def test_feedback_remove_limite_de_perfil(self):
        resposta = '{"requisitos": [], "total_itens": 0, "resumo": ""}'
        with _mock_llm_response(resposta) as mocked:
            _call_extracao_llm(
                "texto", _ParecerStub(), "simples", None, "incluir tudo de eletrica"
            )

        user_content = mocked.call_args[0][1]
        assert "RESTRICAO DE VOLUME" not in user_content
        assert "incluir tudo de eletrica" in user_content

    def test_sem_feedback_aplica_limite_de_perfil(self):
        resposta = '{"requisitos": [], "total_itens": 0, "resumo": ""}'
        with _mock_llm_response(resposta) as mocked:
            _call_extracao_llm("texto", _ParecerStub(), "simples", None, None)

        user_content = mocked.call_args[0][1]
        assert "NO MAXIMO 10" in user_content

    def test_escopo_nao_remove_limite_de_perfil(self):
        # Bug histórico: escopo com "todos" derrubava o teto (incidente 90+ itens).
        # Escopo restringe o recorte; só feedback/integral liberam o teto.
        resposta = '{"requisitos": [], "total_itens": 0, "resumo": ""}'
        with _mock_llm_response(resposta) as mocked:
            _call_extracao_llm(
                "texto",
                _ParecerStub(),
                "simples",
                "todos os itens da tabela do capitulo 2",
                None,
            )

        user_content = mocked.call_args[0][1]
        assert "NO MAXIMO 10" in user_content
        assert "RECORTE DE ESCOPO" in user_content
        assert "todos os itens da tabela do capitulo 2" in user_content

    @staticmethod
    def _resposta_com_n_itens(n: int) -> str:
        import json as _json

        return _json.dumps(
            {
                "requisitos": [
                    {"numero": i + 1, "descricao_requisito": f"Req {i + 1}",
                     "prioridade": "ALTA"}
                    for i in range(n)
                ],
                "total_itens": n,
                "resumo": "Base.",
            }
        )

    def test_trava_dura_corta_excedente_e_anota_resumo(self):
        # O prompt pede "NO MAXIMO N", mas isso e um pedido — a garantia e o corte
        # em codigo. custom_5 com 8 itens devolvidos → exatamente 5, renumerados.
        with _mock_llm_response(self._resposta_com_n_itens(8)):
            data = _call_extracao_llm("texto", _ParecerStub(), "custom_5", None, None)

        assert data["total_itens"] == 5
        assert [r["numero"] for r in data["requisitos"]] == [1, 2, 3, 4, 5]
        assert "Modelo retornou 8 itens" in data["resumo"]
        assert "5 mais relevantes" in data["resumo"]

    def test_trava_dura_nao_corta_no_perfil_integral(self):
        with _mock_llm_response(self._resposta_com_n_itens(30)):
            data = _call_extracao_llm("texto", _ParecerStub(), "integral", None, None)

        assert data["total_itens"] == 30
        assert "mais relevantes" not in data["resumo"]

    def test_trava_dura_nao_corta_com_feedback_lista_completa(self):
        with _mock_llm_response(self._resposta_com_n_itens(30)):
            data = _call_extracao_llm(
                "texto", _ParecerStub(), "simples", None, "quero a lista completa"
            )

        assert data["total_itens"] == 30

    def test_trava_dura_corta_mesmo_com_escopo_contendo_todos(self):
        # Escopo nao libera o teto (M2) e o corte em codigo o garante (M1).
        with _mock_llm_response(self._resposta_com_n_itens(30)):
            data = _call_extracao_llm(
                "texto", _ParecerStub(), "custom_10",
                "todos os itens da tabela do capitulo 2", None,
            )

        assert data["total_itens"] == 10

    def test_forcar_quer_tudo_false_ignora_todos_no_feedback(self):
        # Rodada de correção do revisor: o texto do revisor pode conter "todos"
        # e NÃO pode liberar o teto — a decisão é congelada no feedback original.
        with _mock_llm_response(self._resposta_com_n_itens(30)):
            data = _call_extracao_llm(
                "texto",
                _ParecerStub(),
                "custom_10",
                None,
                "REVISAO AUTOMATICA: o desdobramento omitiu todos os itens do cap 2",
                forcar_quer_tudo=False,
            )

        assert data["total_itens"] == 10

    def test_dentro_do_teto_nao_anota_resumo(self):
        with _mock_llm_response(self._resposta_com_n_itens(3)):
            data = _call_extracao_llm("texto", _ParecerStub(), "custom_5", None, None)

        assert data["total_itens"] == 3
        assert data["resumo"] == "Base."

    def test_escopo_e_feedback_sao_secoes_separadas(self):
        resposta = '{"requisitos": [], "total_itens": 0, "resumo": ""}'
        with _mock_llm_response(resposta) as mocked:
            _call_extracao_llm(
                "texto", _ParecerStub(), "padrao", "so o capitulo 8", "remova o item 3"
            )

        user_content = mocked.call_args[0][1]
        assert "RECORTE DE ESCOPO" in user_content
        assert "so o capitulo 8" in user_content
        assert "FEEDBACK DO USUARIO" in user_content
        assert "remova o item 3" in user_content


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


# ──────────────────────────────────────────────────────────────────────
# Ajuste #12 — passe de amarracoes (decomposicao por documento anexo)
# ──────────────────────────────────────────────────────────────────────

def _req(numero, descricao="Req", **extras):
    base = {
        "numero": numero,
        "categoria": "Processo",
        "descricao_requisito": descricao,
        "valor_requerido": None,
        "prioridade": "ALTA",
        "norma_referencia": None,
        "referencia_engenharia": f"Cap. {numero}",
    }
    return {**base, **extras}


class TestMergeDecomposicoes:
    def test_substitui_na_posicao_e_renumera(self):
        base = [_req(1), _req(2, "Sistema CFTV conforme TK-8"), _req(3)]
        decs = [{
            "numero_original": 2,
            "anexo": "TK-8.pdf",
            "sub_requisitos": [
                {"descricao_requisito": "Camera fixa — Area A: 12 un", "prioridade": "ALTA"},
                {"descricao_requisito": "Camera PTZ — Area B: 4 un", "prioridade": "MEDIA"},
            ],
        }]
        out = _merge_decomposicoes(base, decs)
        assert [r["numero"] for r in out] == [1, 2, 3, 4]
        assert out[1]["descricao_requisito"].startswith("Camera fixa")
        assert out[2]["descricao_requisito"].startswith("Camera PTZ")
        assert out[3]["descricao_requisito"] == "Req"  # o antigo item 3 virou 4

    def test_numero_original_inexistente_ignorado(self):
        base = [_req(1)]
        decs = [{"numero_original": 9, "sub_requisitos": [{"descricao_requisito": "X"}]}]
        out = _merge_decomposicoes(base, decs)
        assert len(out) == 1
        assert out[0]["descricao_requisito"] == "Req"

    def test_subs_vazios_mantem_original(self):
        base = [_req(1), _req(2)]
        decs = [{"numero_original": 2, "sub_requisitos": []}]
        assert len(_merge_decomposicoes(base, decs)) == 2

    def test_acima_do_cap_mantem_original(self):
        base = [_req(1)]
        decs = [{
            "numero_original": 1,
            "sub_requisitos": [{"descricao_requisito": f"S{i}"} for i in range(81)],
        }]
        out = _merge_decomposicoes(base, decs)
        assert len(out) == 1
        assert out[0]["descricao_requisito"] == "Req"

    def test_sub_sem_descricao_descartado(self):
        base = [_req(1)]
        decs = [{
            "numero_original": 1,
            "sub_requisitos": [
                {"descricao_requisito": "Valido"},
                {"descricao_requisito": "   "},
                {"valor_requerido": "orfao"},
            ],
        }]
        out = _merge_decomposicoes(base, decs)
        assert len(out) == 1
        assert out[0]["descricao_requisito"] == "Valido"

    def test_heranca_prioridade_categoria_e_referencia(self):
        base = [_req(1, prioridade="BAIXA", categoria="Eletrico")]
        decs = [{
            "numero_original": 1,
            "sub_requisitos": [{"descricao_requisito": "Sub", "prioridade": "INVALIDA"}],
        }]
        out = _merge_decomposicoes(base, decs)
        assert out[0]["prioridade"] == "BAIXA"
        assert out[0]["categoria"] == "Eletrico"
        assert out[0]["referencia_engenharia"] == "Cap. 1"

    def test_decomposicao_duplicada_primeira_vence(self):
        base = [_req(1)]
        decs = [
            {"numero_original": 1, "sub_requisitos": [{"descricao_requisito": "Primeira"}]},
            {"numero_original": 1, "sub_requisitos": [{"descricao_requisito": "Segunda"}]},
        ]
        out = _merge_decomposicoes(base, decs)
        assert [r["descricao_requisito"] for r in out] == ["Primeira"]


class TestResolverAmarracoes:
    _ANEXOS = [("TK-8.pdf", "texto do anexo com a tabela de pontos")]

    def _base_data(self):
        return {
            "requisitos": [_req(1, "Sistema CFTV conforme TK-8")],
            "total_itens": 1,
            "resumo": "Resumo base.",
        }

    def test_json_invalido_mantem_base(self):
        data = self._base_data()
        with _mock_llm_response("isto nao e json"):
            out = _resolver_amarracoes_sync(data, self._ANEXOS, _ParecerStub())
        assert out["total_itens"] == 1
        assert out["requisitos"][0]["descricao_requisito"] == "Sistema CFTV conforme TK-8"

    def test_excecao_da_llm_mantem_base(self):
        data = self._base_data()
        with patch("app.services.requisitos.call_llm", side_effect=RuntimeError("boom")):
            out = _resolver_amarracoes_sync(data, self._ANEXOS, _ParecerStub())
        assert out["total_itens"] == 1

    def test_caminho_feliz_decompoe_e_atualiza_total(self):
        data = self._base_data()
        resposta = """
        {"decomposicoes": [{"numero_original": 1, "anexo": "TK-8.pdf",
          "sub_requisitos": [
            {"descricao_requisito": "Camera fixa — Area A: 12 un", "valor_requerido": "12 un",
             "prioridade": "ALTA", "referencia_engenharia": "MR item 1.1 + TK-8 pag. 29"},
            {"descricao_requisito": "Camera PTZ — Area B: 4 un", "valor_requerido": "4 un",
             "prioridade": "MEDIA", "referencia_engenharia": "MR item 1.1 + TK-8 pag. 29"}
          ]}],
         "referencias_nao_anexadas": []}
        """
        with _mock_llm_response(resposta):
            out = _resolver_amarracoes_sync(data, self._ANEXOS, _ParecerStub())
        assert out["total_itens"] == 2
        assert [r["numero"] for r in out["requisitos"]] == [1, 2]
        assert "pag. 29" in out["requisitos"][0]["referencia_engenharia"]

    def test_referencias_nao_anexadas_vao_para_resumo(self):
        data = self._base_data()
        resposta = '{"decomposicoes": [], "referencias_nao_anexadas": ["TK-9"]}'
        with _mock_llm_response(resposta):
            out = _resolver_amarracoes_sync(data, self._ANEXOS, _ParecerStub())
        assert "TK-9" in out["resumo"]
        assert "não anexado" in out["resumo"]


class TestAnexosCitados:
    def test_stem_do_nome_seleciona_o_anexo(self):
        reqs = [_req(1, "Sistema de CFTV conforme TK-8", valor_requerido="conforme TK-8")]
        anexos = [("TK-8 - CFTV.pdf", "a"), ("TK-9 Telefonia.pdf", "b")]
        citados = _anexos_citados(reqs, anexos)
        assert [nome for nome, _ in citados] == ["TK-8 - CFTV.pdf"]

    def test_keyword_generica_inclui_todos(self):
        reqs = [_req(1, "Painel montado de acordo com o criterio de projeto")]
        anexos = [("XPT-100.pdf", "a"), ("ZWK-200.pdf", "b")]
        assert _anexos_citados(reqs, anexos) == anexos

    def test_sem_referencia_retorna_vazio(self):
        reqs = [_req(1, "Transmissor de pressao 0-100 bar", valor_requerido="0-100 bar")]
        anexos = [("XPT-555.pdf", "a")]
        assert _anexos_citados(reqs, anexos) == []


class TestRequisitosCitantes:
    def test_stem_do_nome_seleciona_os_citantes(self):
        reqs = [
            _req(1, "Sistema de CFTV conforme TK-8", valor_requerido="conforme TK-8"),
            _req(2, "Transmissor de pressao 0-100 bar"),
        ]
        citantes = _requisitos_citantes(reqs, "TK-8 - CFTV.pdf")
        assert [r["numero"] for r in citantes] == [1]

    def test_fallback_keyword_generica(self):
        # Nome sem stem presente nos requisitos ("ZWK"/"XYZ" não aparecem) →
        # cai no fallback por palavra-chave genérica ("de acordo com").
        reqs = [
            _req(1, "Painel montado de acordo com o criterio de projeto"),
            _req(2, "Transmissor de pressao tipo capacitivo"),
        ]
        citantes = _requisitos_citantes(reqs, "ZWK-XYZ.pdf")
        assert [r["numero"] for r in citantes] == [1]

    def test_stem_numerico_e_match_frouxo_por_design(self):
        # "XPT-100" casa com "0-100 bar" pelo stem "100" — falso positivo barato
        # (só adiciona queries de retrieval), mesmo critério do _anexos_citados.
        reqs = [_req(2, "Transmissor de pressao 0-100 bar")]
        citantes = _requisitos_citantes(reqs, "XPT-100.pdf")
        assert [r["numero"] for r in citantes] == [2]


def _chunk(id_, page, index, tipo="text", conteudo="conteudo"):
    return SimpleNamespace(
        id=id_, page_number=page, chunk_index=index, chunk_type=tipo, conteudo=conteudo
    )


class TestMontarTextoAnexo:
    _REQS = [_req(1, "Sistema de CFTV conforme TK-8", valor_requerido="conforme TK-8")]

    def test_anexo_pequeno_vai_inteiro_sem_tocar_o_banco(self):
        texto, aviso = _montar_texto_anexo_sync(
            None, "pid", "TK-8.pdf", "texto curto", None, self._REQS
        )
        assert texto == "texto curto"
        assert aviso is None

    def test_anexo_grande_sem_doc_id_cai_no_corte_com_aviso(self):
        grande = "x" * (_ANEXO_FULLTEXT_MAX + 10)
        texto, aviso = _montar_texto_anexo_sync(
            None, "pid", "TK-8.pdf", grande, None, self._REQS
        )
        assert len(texto) == _ANEXO_FULLTEXT_MAX
        assert aviso and "muito extenso" in aviso

    def test_anexo_grande_usa_retrieval_dedupe_e_ordena_por_pagina(self):
        grande = "x" * (_ANEXO_FULLTEXT_MAX + 10)
        db = MagicMock()
        db.execute.return_value.scalar.return_value = 3  # chunks já indexados
        # Mesmo chunk (id=1) devolvido duas vezes → dedupe; ordenação por página
        chunks = [
            _chunk(2, page=29, index=5, tipo="table", conteudo="tabela de cameras"),
            _chunk(1, page=3, index=1, conteudo="secao inicial"),
            _chunk(1, page=3, index=1, conteudo="secao inicial"),
        ]
        with patch(
            "app.services.requisitos.retrieve_relevant_chunks_sync",
            return_value=chunks,
        ):
            texto, aviso = _montar_texto_anexo_sync(
                db, "pid", "TK-8.pdf", grande, "doc-id", self._REQS
            )
        assert aviso is None
        assert "busca semantica" in texto
        # Ordem de documento: página 3 antes da 29; marcadores presentes
        assert texto.index("[Pagina 3]") < texto.index("[Pagina 29]")
        assert "(TABELA)" in texto
        assert texto.count("secao inicial") == 1  # dedupe por id

    def test_retrieval_vazio_cai_no_corte_com_aviso(self):
        grande = "y" * (_ANEXO_FULLTEXT_MAX + 10)
        db = MagicMock()
        db.execute.return_value.scalar.return_value = 3
        with patch(
            "app.services.requisitos.retrieve_relevant_chunks_sync", return_value=[]
        ):
            texto, aviso = _montar_texto_anexo_sync(
                db, "pid", "TK-8.pdf", grande, "doc-id", self._REQS
            )
        assert len(texto) == _ANEXO_FULLTEXT_MAX
        assert aviso and "muito extenso" in aviso

    def test_sem_chunks_indexa_inline(self):
        grande = "z" * (_ANEXO_FULLTEXT_MAX + 10)
        db = MagicMock()
        db.execute.return_value.scalar.return_value = 0  # corrida de indexação
        with patch(
            "app.services.indexer.index_document_sync", return_value=5
        ) as mock_index, patch(
            "app.services.requisitos.retrieve_relevant_chunks_sync",
            return_value=[_chunk(1, page=2, index=0)],
        ):
            texto, aviso = _montar_texto_anexo_sync(
                db, "pid", "TK-8.pdf", grande, "doc-id", self._REQS
            )
        mock_index.assert_called_once_with("doc-id")
        assert aviso is None
        assert "[Pagina 2]" in texto


class TestRevisarExtracao:
    _DATA = {
        "requisitos": [_req(1, "Faixa 0-100 bar")],
        "total_itens": 1,
        "resumo": "Base.",
    }

    def _revisar(self):
        return _revisar_extracao_sync(
            "texto eng", self._DATA, [], _ParecerStub(), "padrao", None, None
        )

    def test_sem_api_key_devolve_none(self):
        with patch.object(settings, "OPENAI_API_KEY", ""):
            assert self._revisar() is None

    def test_flag_off_devolve_none(self):
        with patch.object(settings, "OPENAI_API_KEY", "sk-test"), patch.object(
            settings, "ENABLE_EXTRACTION_REVIEWER", False
        ):
            assert self._revisar() is None

    def test_veredito_valido_normalizado(self):
        resposta = """
        {"aprovado": false, "problemas": [
          {"numero": 1, "tipo": "fidelidade", "detalhe": "Item sem origem no doc",
           "correcao_sugerida": "Remover o item 1"},
          {"numero": null, "tipo": "contagem", "detalhe": "   "},
          "nao-e-dict"
        ]}
        """
        with patch.object(settings, "OPENAI_API_KEY", "sk-test"), patch(
            "app.services.requisitos.call_openai", return_value=resposta
        ):
            veredito = self._revisar()

        assert veredito is not None
        assert veredito["aprovado"] is False
        # Problema sem detalhe e entrada nao-dict sao descartados
        assert len(veredito["problemas"]) == 1
        assert veredito["problemas"][0]["tipo"] == "fidelidade"

    def test_json_invalido_devolve_none(self):
        with patch.object(settings, "OPENAI_API_KEY", "sk-test"), patch(
            "app.services.requisitos.call_openai", return_value="nao e json"
        ):
            assert self._revisar() is None

    def test_excecao_da_api_devolve_none(self):
        with patch.object(settings, "OPENAI_API_KEY", "sk-test"), patch(
            "app.services.requisitos.call_openai", side_effect=RuntimeError("boom")
        ):
            assert self._revisar() is None


def test_limit_instruction_menciona_amarracoes():
    resposta = '{"requisitos": [], "total_itens": 0, "resumo": ""}'
    with _mock_llm_response(resposta) as mock_llm:
        _call_extracao_llm("texto eng", _ParecerStub(), "padrao", None, None)
    user_content = mock_llm.call_args.args[1]
    assert "amarrados a documentos anexos" in user_content.lower()
