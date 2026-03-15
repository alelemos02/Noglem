from app.core.config import settings
from app.services.analyzer import (
    _call_gemini,
    _extract_json,
    _extract_keywords,
    _keyword_found_in_text,
    _normalize_text,
    _split_text_into_chunks,
    _validate_parecer_json,
    validate_reference_grounding,
    validate_value_consistency,
)


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
        "app.services.analyzer.httpx.Client",
        lambda timeout=180.0: fake_client,
    )
    monkeypatch.setattr("app.services.analyzer.time.sleep", lambda s: sleep_calls.append(s))

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
        "app.services.analyzer.httpx.Client",
        lambda timeout=180.0: fake_client,
    )
    monkeypatch.setattr("app.services.analyzer.time.sleep", lambda _s: None)

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
    assert "VALIDACAO_CONSISTENCIA" in flagged_item["justificativa_tecnica"]


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
    assert "VALIDACAO_CONSISTENCIA" in flagged["justificativa_tecnica"]


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
