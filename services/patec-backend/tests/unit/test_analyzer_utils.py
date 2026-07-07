from app.core.config import settings
from app.services import analyzer
from app.services.prompts.analise import (
    DISCIPLINAS_SUPORTADAS,
    SYSTEM_PROMPT_INSTRUMENTACAO,
    get_system_prompt,
)
from app.services.analyzer import (
    _call_gemini,
    _extract_json,
    _extract_keywords,
    _is_blank,
    _keyword_found_in_text,
    _normalize_text,
    _repair_item_keys,
    _split_text_into_chunks,
    _validate_parecer_json,
    flag_items_for_verification,
    recover_missing_supplier_values,
    reconciliar_escopo_fechado,
    validate_reference_grounding,
    validate_value_consistency,
    verify_flagged_items,
)


def _reqs(n):
    return [
        {
            "numero": i,
            "categoria": "Processo",
            "descricao_requisito": f"Requisito {i}",
            "valor_requerido": f"valor {i}",
            "prioridade": "MEDIA",
            "norma_referencia": None,
            "referencia_engenharia": f"Item {i}",
        }
        for i in range(1, n + 1)
    ]


def test_reconciliacao_injeta_placeholder_para_requisito_faltante():
    # 3 requisitos aprovados, mas a LLM devolveu itens só para 1 e 3
    data = {"parecer_tecnico": {"itens": [
        {"numero": 1, "requisito_numero": 1, "status": "A",
         "descricao_requisito": "R1", "valor_fornecedor": "x"},
        {"numero": 2, "requisito_numero": 3, "status": "C",
         "descricao_requisito": "R3", "valor_fornecedor": "y"},
    ]}}
    out, summary = reconciliar_escopo_fechado(data, _reqs(3))
    itens = out["parecer_tecnico"]["itens"]
    # todos os 3 requisitos agora cobertos
    assert len(itens) == 3
    assert summary["itens_faltantes"] == 1
    assert summary["numeros_faltantes"] == [2]
    # o requisito 2 entrou como placeholder D vinculado ao requisito
    placeholder = next(i for i in itens if i["requisito_numero"] == 2)
    assert placeholder["status"] == "D"
    assert placeholder["valor_fornecedor"] == "Nao informado."


def test_reconciliacao_sinaliza_duplicados_e_ignora_status_E():
    data = {"parecer_tecnico": {"itens": [
        {"numero": 1, "requisito_numero": 1, "status": "A", "descricao_requisito": "R1"},
        {"numero": 2, "requisito_numero": 1, "status": "B", "descricao_requisito": "R1 dup"},
        {"numero": 3, "requisito_numero": None, "status": "E",
         "descricao_requisito": "extra do fornecedor"},
    ]}}
    out, summary = reconciliar_escopo_fechado(data, _reqs(1))
    assert summary["requisitos_duplicados"] == [1]
    assert summary["itens_faltantes"] == 0
    # o item E (requisito_numero=None) permanece intacto
    assert any(i["status"] == "E" for i in out["parecer_tecnico"]["itens"])


def test_extract_json_recupera_array_truncado_sem_crashar():
    # Resposta cortada por MAX_TOKENS no meio do 3o item — o parser deve
    # recuperar um JSON valido (reparo ou last-resort), nunca estourar excecao.
    truncada = (
        '{"parecer_tecnico": {"itens": ['
        '{"numero": 1, "status": "A", "valor_fornecedor": "x"},'
        '{"numero": 2, "status": "C", "valor_fornecedor": "y"},'
        '{"numero": 3, "status": "D", "descricao_requisito": "cortado no me'
    )
    data = _extract_json(truncada)
    itens = data.get("parecer_tecnico", data).get("itens", [])
    # pelo menos os itens completos sobrevivem, e o resultado e parseavel
    assert len(itens) >= 2
    assert itens[0]["numero"] == 1


def test_disciplinas_suportadas_tem_persona_propria():
    # As 5 disciplinas suportadas alinham com o seletor do frontend
    assert DISCIPLINAS_SUPORTADAS == {
        "instrumentacao", "eletrico", "mecanico", "processos", "civil"
    }
    # cada uma retorna um prompt distinto (nao caiu no fallback silencioso)
    prompts = {d: get_system_prompt(d) for d in DISCIPLINAS_SUPORTADAS}
    assert len(set(prompts.values())) == len(DISCIPLINAS_SUPORTADAS)


def test_disciplina_desconhecida_cai_no_fallback_instrumentacao():
    assert get_system_prompt("disciplina_que_nao_existe") == SYSTEM_PROMPT_INSTRUMENTACAO


def test_reconciliacao_sem_faltantes_nao_altera_contagem():
    data = {"parecer_tecnico": {"itens": [
        {"numero": 1, "requisito_numero": 1, "status": "A", "descricao_requisito": "R1"},
        {"numero": 2, "requisito_numero": 2, "status": "B", "descricao_requisito": "R2"},
    ]}}
    out, summary = reconciliar_escopo_fechado(data, _reqs(2))
    assert summary["itens_faltantes"] == 0
    assert summary["requisitos_duplicados"] == []
    assert len(out["parecer_tecnico"]["itens"]) == 2


def test_extract_json_with_markdown_block():
    raw = """```json
{"parecer_tecnico":{"itens":[]}}
```"""
    parsed = _extract_json(raw)
    assert "parecer_tecnico" in parsed


def test_split_text_into_chunks_respects_limit():
    text = "A\n\nB\n\nC\n\nD"
    chunks = _split_text_into_chunks(text, max_chars=3)
    assert len(chunks) >= 2
    assert all(chunk.strip() for chunk in chunks)


def test_validate_parecer_json_recalculates_totals():
    data = {
        "parecer_tecnico": {
            "resumo_executivo": {},
            "itens": [
                {"status": "A", "prioridade": "BAIXA"},
                {"status": "C", "prioridade": "ALTA"},
                {"status": "D"},
            ],
        }
    }
    out = _validate_parecer_json(data)
    resumo = out["parecer_tecnico"]["resumo_executivo"]
    assert resumo["total_itens"] == 3
    assert resumo["aprovados"] == 1
    assert resumo["rejeitados"] == 1
    assert resumo["informacao_ausente"] == 1
    assert resumo["parecer_geral"] == "REJEITADO"


def test_repair_item_keys_recovers_corrupted_supplier_key():
    # The exact corruption observed in production: the LLM emitted "valor_necedor"
    # instead of "valor_fornecedor", silently dropping the supplier value.
    item = {
        "numero": 3,
        "status": "B",
        "valor_necedor": "1 conjunto, Torre Dell T5860XL, 4 monitores 55\".",
    }
    _repair_item_keys(item)
    assert item.get("valor_fornecedor") == "1 conjunto, Torre Dell T5860XL, 4 monitores 55\"."
    assert "valor_necedor" not in item


def test_repair_item_keys_does_not_clobber_valid_value():
    # A stray/extra key must never overwrite a canonical key that is already filled.
    item = {"valor_fornecedor": "valor correto", "valor_necedor": "valor errado"}
    _repair_item_keys(item)
    assert item["valor_fornecedor"] == "valor correto"


def test_repair_item_keys_ignores_unrelated_keys():
    item = {"status": "B", "observacao_extra": "nota", "valor_fornecedor": "x"}
    _repair_item_keys(item)
    assert item["observacao_extra"] == "nota"  # too dissimilar to remap
    assert item["valor_fornecedor"] == "x"


def test_validate_parecer_json_repairs_keys_in_loop():
    data = {
        "parecer_tecnico": {
            "resumo_executivo": {},
            "itens": [
                {"status": "B", "prioridade": "MEDIA", "valor_necedor": "ofertado X"},
            ],
        }
    }
    out = _validate_parecer_json(data)
    item = out["parecer_tecnico"]["itens"][0]
    assert item["valor_fornecedor"] == "ofertado X"


def test_recover_missing_supplier_values_fills_blank_without_llm():
    # Status D with no supplier value: deterministic guard fills the blank and the
    # status does not imply an offer, so no LLM call is attempted (empty supplier text).
    data = {
        "parecer_tecnico": {
            "itens": [
                {"numero": 1, "status": "A", "valor_fornecedor": "ok"},
                {"numero": 2, "status": "D", "valor_fornecedor": None},
            ]
        }
    }
    out, summary = recover_missing_supplier_values(data, texto_fornecedor="")
    itens = out["parecer_tecnico"]["itens"]
    assert itens[0]["valor_fornecedor"] == "ok"
    assert itens[1]["valor_fornecedor"] == "Nao informado."
    assert summary["items_flagged"] == 0  # D does not imply an offer


def test_is_blank_treats_dashes_as_empty():
    assert _is_blank(None)
    assert _is_blank("")
    assert _is_blank("  —  ")
    assert _is_blank("-")
    assert _is_blank("N/A")
    assert not _is_blank("Torre Dell T5860XL")


def test_validate_parecer_json_populates_observation_and_action_defaults():
    data = {
        "parecer_tecnico": {
            "resumo_executivo": {},
            "itens": [
                {"status": "A", "prioridade": "BAIXA", "justificativa_tecnica": ""},
                {"status": "B", "prioridade": "MEDIA", "justificativa_tecnica": "", "acao_requerida": ""},
            ],
        }
    }

    out = _validate_parecer_json(data)
    itens = out["parecer_tecnico"]["itens"]

    assert "aderente aos requisitos tecnicos" in itens[0]["justificativa_tecnica"]
    assert itens[0]["acao_requerida"] is None
    assert "parcialmente conforme" in itens[1]["justificativa_tecnica"]
    assert itens[1]["acao_requerida"] is not None
    assert itens[1]["acao_requerida"].strip() != ""


def test_reference_grounding_flags_missing_references():
    result = {
        "parecer_tecnico": {
            "resumo_executivo": {},
            "itens": [
                {
                    "descricao_requisito": "req 1",
                    "status": "A",
                    "referencia_engenharia": "Pressao maxima 10bar",
                    "referencia_fornecedor": "Atende 10bar",
                    "justificativa_tecnica": "texto",
                },
                {
                    "descricao_requisito": "req 2",
                    "status": "A",
                    "referencia_engenharia": "inexistente engenharia",
                    "referencia_fornecedor": "inexistente fornecedor",
                    "justificativa_tecnica": "texto",
                },
            ],
        }
    }
    validated, summary = validate_reference_grounding(
        data=result,
        texto_engenharia="Documento fala: Pressao maxima 10bar",
        texto_fornecedor="Documento fornecedor: Atende 10bar",
    )

    assert summary["items_checked"] == 2
    assert summary["items_flagged"] == 1
    assert summary["eng_reference_misses"] == 1
    assert summary["forn_reference_misses"] == 1
    # NOTE: validate_reference_grounding is informational only — it does NOT
    # override item status. The original status is preserved.
    flagged = validated["parecer_tecnico"]["itens"][1]
    assert flagged["status"] == "A"  # original status preserved


class _FakeResponse:
    def __init__(self, status_code, json_data, headers=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._json_data


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, params=None, json=None):  # noqa: A002
        self.calls += 1
        return self._responses.pop(0)


def test_call_gemini_retries_429_then_succeeds(monkeypatch):
    fake_client = _FakeClient(
        [
            _FakeResponse(
                429,
                {"error": {"message": "Resource exhausted. Please try again later."}},
            ),
            _FakeResponse(
                200,
                {
                    "candidates": [
                        {
                            "finishReason": "STOP",
                            "content": {"parts": [{"text": '{"parecer_tecnico":{"itens":[]}}'}]},
                        }
                    ]
                },
            ),
        ]
    )
    sleep_calls = []

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRIES", 3)
    monkeypatch.setattr(settings, "GEMINI_RETRY_BASE_SECONDS", 0.01)
    monkeypatch.setattr(
        "app.services.llm_client.httpx.Client",
        lambda timeout=180.0: fake_client,
    )
    monkeypatch.setattr("app.services.llm_client.time.sleep", lambda s: sleep_calls.append(s))

    out = _call_gemini("system", "user")

    assert out == '{"parecer_tecnico":{"itens":[]}}'
    assert fake_client.calls == 2
    assert len(sleep_calls) == 1


def test_call_gemini_429_exhausted_raises_friendly_message(monkeypatch):
    fake_client = _FakeClient(
        [
            _FakeResponse(
                429,
                {"error": {"message": "Resource exhausted. Please try again later."}},
            ),
            _FakeResponse(
                429,
                {"error": {"message": "Resource exhausted. Please try again later."}},
            ),
        ]
    )

    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GEMINI_MAX_RETRIES", 2)
    monkeypatch.setattr(settings, "GEMINI_RETRY_BASE_SECONDS", 0.01)
    monkeypatch.setattr(
        "app.services.llm_client.httpx.Client",
        lambda timeout=180.0: fake_client,
    )
    monkeypatch.setattr("app.services.llm_client.time.sleep", lambda _s: None)

    try:
        _call_gemini("system", "user")
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "limite temporario (429)" in str(exc)


# ---------------------------------------------------------------------------
# Tests for _extract_keywords
# ---------------------------------------------------------------------------


def test_extract_keywords_strips_boilerplate():
    keywords = _extract_keywords("Solicitado: conector LC Duplex para fibra otica SM")
    assert "conector" in keywords
    assert "lc" in keywords
    assert "duplex" in keywords
    assert "fibra" in keywords
    assert "otica" in keywords
    assert "sm" in keywords
    # "solicitado" should be stripped as boilerplate prefix
    assert "solicitado:" not in keywords
    assert "solicitado" not in keywords


def test_extract_keywords_strips_stopwords():
    keywords = _extract_keywords("O fornecedor deve apresentar certificado SIL 2")
    # Stopwords should be removed
    assert "fornecedor" not in keywords  # part of boilerplate prefix
    # Technical terms should remain
    assert "certificado" in keywords
    assert "sil" in keywords


def test_extract_keywords_empty_input():
    assert _extract_keywords("") == []
    assert _extract_keywords(None) == []


def test_extract_keywords_returns_normalized():
    keywords = _extract_keywords("Válvula com Conexão INOX-316L")
    # All should be lowercase, no accents
    for kw in keywords:
        assert kw == kw.lower()
        assert all(ord(c) < 128 for c in kw)  # ASCII only


# ---------------------------------------------------------------------------
# Tests for _keyword_found_in_text
# ---------------------------------------------------------------------------


def test_keyword_found_exact_match():
    text = _normalize_text("Distribuidor interno otico LIGHTERA BT48")
    assert _keyword_found_in_text("lightera", text) is True
    assert _keyword_found_in_text("bt48", text) is True


def test_keyword_found_short_word_boundary():
    text = _normalize_text(
        "Distribuidor interno otico SC, LC Duplex, Bastidor 19"
    )
    # "sc" should match because it's at a word boundary
    assert _keyword_found_in_text("sc", text) is True
    # "lc" should match as well
    assert _keyword_found_in_text("lc", text) is True


def test_keyword_not_found_short_false_positive():
    text = _normalize_text("descricao do equipamento principal")
    # "sc" should NOT match inside "descricao"
    assert _keyword_found_in_text("sc", text) is False


def test_keyword_not_found():
    text = _normalize_text("Transmissor de pressao com saida Modbus RTU")
    assert _keyword_found_in_text("hart", text) is False
    assert _keyword_found_in_text("profibus", text) is False


# ---------------------------------------------------------------------------
# Tests for validate_value_consistency
# ---------------------------------------------------------------------------


def test_consistency_flags_false_negative_lc_connector():
    """Core test: the LC connector scenario from real bug report."""
    data = {
        "parecer_tecnico": {
            "resumo_executivo": {},
            "itens": [
                {
                    "numero": 1,
                    "status": "B",
                    "valor_requerido": "Solicitado: conector LC Duplex",
                    "valor_fornecedor": "Ofertado: conector SC",
                    "justificativa_tecnica": "Fornecedor oferece apenas conector SC.",
                    "descricao_requisito": "Tipo de conector otico",
                    "prioridade": "MEDIA",
                },
            ],
        }
    }
    texto_fornecedor = (
        "Distribuidor interno otico LIGHTERA BT48, ANSI/TIA-569, "
        "fibra otica SM, conector SC, LC Duplex, Bastidor 19"
    )
    validated, summary = validate_value_consistency(data, texto_fornecedor)

    assert summary["items_checked"] == 1
    assert summary["items_flagged"] == 1
    assert len(summary["flag_details"]) == 1

    flagged_item = validated["parecer_tecnico"]["itens"][0]
    # O flag vai para um campo interno — NUNCA polui a justificativa exportada.
    assert flagged_item.get("_flag_consistencia")
    assert "VALIDACAO_CONSISTENCIA" not in flagged_item["justificativa_tecnica"]


def test_consistency_no_false_flag_when_truly_missing():
    """When the required value truly is absent, no flag should be raised."""
    data = {
        "parecer_tecnico": {
            "resumo_executivo": {},
            "itens": [
                {
                    "numero": 1,
                    "status": "C",
                    "valor_requerido": "Solicitado: protocolo HART",
                    "valor_fornecedor": "Ofertado: protocolo Modbus",
                    "justificativa_tecnica": "Fornecedor nao oferece HART.",
                    "descricao_requisito": "Protocolo de comunicacao",
                    "prioridade": "ALTA",
                },
            ],
        }
    }
    texto_fornecedor = "Transmissor de pressao com saida 4-20mA e Modbus RTU."
    validated, summary = validate_value_consistency(data, texto_fornecedor)

    assert summary["items_flagged"] == 0


def test_consistency_skips_status_a_and_e():
    """Status A and E items should not be checked."""
    data = {
        "parecer_tecnico": {
            "resumo_executivo": {},
            "itens": [
                {
                    "numero": 1,
                    "status": "A",
                    "valor_requerido": "Solicitado: pressao 10bar",
                    "valor_fornecedor": "Ofertado: pressao 10bar",
                    "justificativa_tecnica": "Conforme.",
                    "descricao_requisito": "Pressao",
                    "prioridade": "BAIXA",
                },
                {
                    "numero": 2,
                    "status": "E",
                    "valor_requerido": "",
                    "valor_fornecedor": "Item adicional do fornecedor",
                    "justificativa_tecnica": "Adicional.",
                    "descricao_requisito": "Extra",
                    "prioridade": "BAIXA",
                },
            ],
        }
    }
    texto_fornecedor = "Pressao de trabalho 10bar, item adicional XYZ."
    validated, summary = validate_value_consistency(data, texto_fornecedor)

    assert summary["items_checked"] == 0
    assert summary["items_flagged"] == 0


def test_consistency_flags_status_d_with_found_terms():
    """Status D (info ausente) should be flagged when terms are found."""
    data = {
        "parecer_tecnico": {
            "resumo_executivo": {},
            "itens": [
                {
                    "numero": 1,
                    "status": "D",
                    "valor_requerido": "Solicitado: certificado SIL 2",
                    "valor_fornecedor": "Nao informado pelo fornecedor",
                    "justificativa_tecnica": "Informacao ausente.",
                    "descricao_requisito": "Certificacao SIL",
                    "prioridade": "ALTA",
                },
            ],
        }
    }
    texto_fornecedor = (
        "Transmissor com certificacao SIL 2 conforme IEC 61508. "
        "Certificado emitido por TUV."
    )
    validated, summary = validate_value_consistency(data, texto_fornecedor)

    assert summary["items_flagged"] == 1
    flagged = validated["parecer_tecnico"]["itens"][0]
    assert flagged.get("_flag_consistencia")
    assert "VALIDACAO_CONSISTENCIA" not in flagged["justificativa_tecnica"]


def test_consistency_multiple_items_mixed():
    """Test with multiple items, some should be flagged, some not."""
    data = {
        "parecer_tecnico": {
            "resumo_executivo": {},
            "itens": [
                {
                    "numero": 1,
                    "status": "A",
                    "valor_requerido": "Solicitado: 4-20mA",
                    "valor_fornecedor": "Ofertado: 4-20mA",
                    "justificativa_tecnica": "OK",
                    "descricao_requisito": "Sinal",
                    "prioridade": "BAIXA",
                },
                {
                    "numero": 2,
                    "status": "C",
                    "valor_requerido": "Solicitado: material INOX 316",
                    "valor_fornecedor": "Ofertado: material aco carbono",
                    "justificativa_tecnica": "Material nao conforme",
                    "descricao_requisito": "Material",
                    "prioridade": "ALTA",
                },
                {
                    "numero": 3,
                    "status": "B",
                    "valor_requerido": "Solicitado: conector LC Duplex fibra otica",
                    "valor_fornecedor": "Ofertado: conector SC",
                    "justificativa_tecnica": "Apenas SC ofertado",
                    "descricao_requisito": "Conector",
                    "prioridade": "MEDIA",
                },
            ],
        }
    }
    texto_fornecedor = (
        "Equipamento com saida 4-20mA, material aco carbono, "
        "conector SC, LC Duplex, fibra otica SM."
    )
    validated, summary = validate_value_consistency(data, texto_fornecedor)

    # Item 1 (A) not checked, Item 2 (C) - "inox 316" NOT in text, not flagged
    # Item 3 (B) - "lc", "duplex", "fibra", "otica" ARE in text -> flagged
    assert summary["items_checked"] == 2  # items 2 and 3
    assert summary["items_flagged"] >= 1  # at least item 3


# ---------------------------------------------------------------------------
# Cross-item verification (detector + Pro verifier)
# ---------------------------------------------------------------------------


def test_flag_items_for_verification_detects_duplicate_supplier_value():
    # Two near-identical requirements (qty differs) where the LLM pasted the SAME
    # supplier value onto both — the exact production bug (items 7/8). Items are
    # numbered sequentially because _validate_parecer_json renumbers to 1..N.
    data = {
        "parecer_tecnico": {
            "resumo_executivo": {},
            "itens": [
                {
                    "numero": 1,
                    "status": "C",
                    "descricao_requisito": "Remote Panels (General) - 8 un",
                    "valor_fornecedor": "8 Armarios IO Remotos DCS + 8 SIS",
                    "justificativa_tecnica": "x",
                },
                {
                    "numero": 2,
                    "status": "C",
                    "descricao_requisito": "Remote Panels (General) - 1 un",
                    "valor_fornecedor": "8 Armarios IO Remotos DCS + 8 SIS",
                    "justificativa_tecnica": "x",
                },
                {
                    "numero": 3,
                    "status": "A",
                    "descricao_requisito": "Outro",
                    "valor_fornecedor": "Transmissor unico modelo XPTO-500",
                    "justificativa_tecnica": "x",
                },
            ],
        }
    }
    out, summary = flag_items_for_verification(data)
    itens = {i["numero"]: i for i in out["parecer_tecnico"]["itens"]}

    assert summary["items_flagged"] == 2
    assert summary["flagged_numbers"] == [1, 2]
    # The flag survives _validate_parecer_json (underscore-key guard) and
    # references the sibling item.
    assert "2" in itens[1]["_verificacao_flag"]
    assert "1" in itens[2]["_verificacao_flag"]
    assert "_verificacao_flag" not in itens[3]


def test_flag_items_ignores_generic_and_short_supplier_values():
    data = {
        "parecer_tecnico": {
            "resumo_executivo": {},
            "itens": [
                {"numero": 1, "status": "D", "valor_fornecedor": "Nao informado.",
                 "descricao_requisito": "a", "justificativa_tecnica": "x"},
                {"numero": 2, "status": "D", "valor_fornecedor": "Nao informado.",
                 "descricao_requisito": "b", "justificativa_tecnica": "x"},
                {"numero": 3, "status": "A", "valor_fornecedor": "4-20 mA",
                 "descricao_requisito": "c", "justificativa_tecnica": "x"},
                {"numero": 4, "status": "A", "valor_fornecedor": "4-20 mA",
                 "descricao_requisito": "d", "justificativa_tecnica": "x"},
            ],
        }
    }
    out, summary = flag_items_for_verification(data)
    assert summary["items_flagged"] == 0
    for item in out["parecer_tecnico"]["itens"]:
        assert "_verificacao_flag" not in item


def test_flag_items_is_idempotent_on_rerun():
    data = {
        "parecer_tecnico": {
            "resumo_executivo": {},
            "itens": [
                {"numero": 1, "status": "C", "valor_fornecedor": "Modelo ABC-123 unidade",
                 "descricao_requisito": "a", "justificativa_tecnica": "x"},
                {"numero": 2, "status": "C", "valor_fornecedor": "Modelo ABC-123 unidade",
                 "descricao_requisito": "b", "justificativa_tecnica": "x"},
            ],
        }
    }
    out, _ = flag_items_for_verification(data)
    # second run: supplier values now unique would clear flags
    out["parecer_tecnico"]["itens"][1]["valor_fornecedor"] = "Modelo XYZ-999 distinto"
    out2, summary2 = flag_items_for_verification(out)
    itens = out2["parecer_tecnico"]["itens"]
    assert summary2["items_flagged"] == 0
    assert "_verificacao_flag" not in itens[0]
    assert "_verificacao_flag" not in itens[1]


def test_verify_flagged_items_applies_correction(monkeypatch):
    data = {
        "parecer_tecnico": {
            "resumo_executivo": {},
            "itens": [
                {
                    "numero": 1,
                    "status": "C",
                    "descricao_requisito": "8 Remote Panels",
                    "valor_requerido": "8 paineis",
                    "valor_fornecedor": "8 Armarios IO Remotos",
                    "justificativa_tecnica": "orig 1",
                    "_verificacao_flag": "Mesmo valor do item 2",
                },
                {
                    "numero": 2,
                    "status": "C",
                    "descricao_requisito": "1 Remote Panel",
                    "valor_requerido": "1 painel",
                    "valor_fornecedor": "8 Armarios IO Remotos",
                    "justificativa_tecnica": "orig 2",
                    "_verificacao_flag": "Mesmo valor do item 1",
                },
            ],
        }
    }

    fake_json = (
        '{"itens": ['
        '{"numero": 1, "correto": true, "nota": "8 paineis batem com a oferta"},'
        '{"numero": 2, "correto": false, "nota": "9o painel nao contemplado",'
        ' "valor_fornecedor_corrigido": "Nao informado.", "status_corrigido": "D",'
        ' "justificativa_corrigida": "Fornecedor ofertou 8 paineis (item 1); este nao."}'
        ']}'
    )
    captured = {}

    def fake_call(system, user_content, **kwargs):
        captured.update(kwargs)
        return fake_json

    monkeypatch.setattr(analyzer, "_call_gemini", fake_call)

    out, summary = verify_flagged_items(
        data=data,
        texto_engenharia="eng",
        texto_fornecedor="forn",
        flag_summary={"flagged_numbers": [1, 2]},
    )
    itens = {i["numero"]: i for i in out["parecer_tecnico"]["itens"]}

    # Uses the configured Pro verifier model, not the default analysis model.
    assert captured.get("model") == settings.GEMINI_VERIFIER_MODEL
    assert summary["reviewed"] == 2
    assert summary["corrections"] == 1
    # Item 1 confirmed (trace note, no change)
    assert itens[1]["status"] == "C"
    assert "Verificado (IA Pro)" in itens[1]["_verificacao_nota"]
    # Item 2 corrected
    assert itens[2]["status"] == "D"
    assert itens[2]["valor_fornecedor"] == "Nao informado."
    assert "Corrigido pela verificacao" in itens[2]["_verificacao_nota"]


def test_verify_flagged_items_noop_when_nothing_flagged():
    data = {"parecer_tecnico": {"itens": [{"numero": 1, "status": "A"}]}}
    out, summary = verify_flagged_items(
        data=data, texto_engenharia="e", texto_fornecedor="f",
        flag_summary={"flagged_numbers": []},
    )
    assert summary == {"reviewed": 0, "corrections": 0}
    assert out is data


def test_verify_flagged_items_survives_llm_failure(monkeypatch):
    data = {
        "parecer_tecnico": {
            "resumo_executivo": {},
            "itens": [
                {"numero": 1, "status": "C", "valor_fornecedor": "X",
                 "descricao_requisito": "a", "justificativa_tecnica": "orig"},
            ],
        }
    }

    def boom(*a, **k):
        raise RuntimeError("429")

    monkeypatch.setattr(analyzer, "_call_gemini", boom)
    out, summary = verify_flagged_items(
        data=data, texto_engenharia="e", texto_fornecedor="f",
        flag_summary={"flagged_numbers": [1]},
    )
    # Pipeline must not break; original item unchanged.
    assert summary["corrections"] == 0
    assert out["parecer_tecnico"]["itens"][0]["justificativa_tecnica"] == "orig"


def test_call_llm_model_override_changes_url(monkeypatch):
    captured = {}

    class _CaptureClient(_FakeClient):
        def post(self, url, params=None, json=None):  # noqa: A002
            captured["url"] = url
            return super().post(url, params=params, json=json)

    ok = _FakeResponse(
        200, {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
    )
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(
        "app.services.llm_client.httpx.Client", lambda *a, **k: _CaptureClient([ok])
    )
    _call_gemini("system", "user", model="gemini-3.1-pro")
    assert "gemini-3.1-pro:generateContent" in captured["url"]
