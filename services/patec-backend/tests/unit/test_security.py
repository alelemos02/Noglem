import asyncio
import types

import pytest
from fastapi import HTTPException

from app.core import deps
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)


def _user(email):
    return types.SimpleNamespace(email=email, papel="admin", ativo=True)


def _run_require_owner(user, x_user_email=None):
    return asyncio.run(
        deps.require_owner(current_user=user, x_user_email=x_user_email)
    )


def test_require_owner_producao_bloqueia_nao_dono(monkeypatch):
    monkeypatch.setattr(deps.settings, "ENV", "production")
    monkeypatch.setattr(deps.settings, "OWNER_EMAILS", "dono@noglem.com.br")
    with pytest.raises(HTTPException) as exc:
        _run_require_owner(_user("qualquer@noglem.com.br"))
    assert exc.value.status_code == 403


def test_require_owner_producao_libera_dono(monkeypatch):
    monkeypatch.setattr(deps.settings, "ENV", "production")
    monkeypatch.setattr(deps.settings, "OWNER_EMAILS", "Dono@Noglem.com.br, outro@x.com")
    u = _user("dono@noglem.com.br")  # case-insensitive
    assert _run_require_owner(u) is u


def test_require_owner_dev_aberto(monkeypatch):
    monkeypatch.setattr(deps.settings, "ENV", "development")
    monkeypatch.setattr(deps.settings, "OWNER_EMAILS", "")
    u = _user("qualquer@x.com")
    assert _run_require_owner(u) is u


def test_require_owner_producao_libera_por_header(monkeypatch):
    # Usuário Clerk tem e-mail sintético; o e-mail real vem no X-User-Email
    monkeypatch.setattr(deps.settings, "ENV", "production")
    monkeypatch.setattr(deps.settings, "OWNER_EMAILS", "dono@noglem.com.br")
    u = _user("clerk_abc123@noglem.com.br")
    assert _run_require_owner(u, x_user_email="Dono@Noglem.com.br") is u


def test_require_owner_producao_header_nao_dono_bloqueia(monkeypatch):
    monkeypatch.setattr(deps.settings, "ENV", "production")
    monkeypatch.setattr(deps.settings, "OWNER_EMAILS", "dono@noglem.com.br")
    with pytest.raises(HTTPException) as exc:
        _run_require_owner(
            _user("clerk_abc123@noglem.com.br"), x_user_email="outro@x.com"
        )
    assert exc.value.status_code == 403


def test_password_hash_and_verify_roundtrip():
    raw = "SenhaForte123!"
    hashed = get_password_hash(raw)
    assert hashed != raw
    assert verify_password(raw, hashed) is True
    assert verify_password("errada", hashed) is False


def test_access_token_contains_type_and_is_decodable():
    token = create_access_token({"sub": "user-1", "papel": "analista"})
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user-1"
    assert payload["papel"] == "analista"
    assert payload["type"] == "access"


def test_refresh_token_contains_type_and_is_decodable():
    token = create_refresh_token({"sub": "user-2", "papel": "admin"})
    payload = decode_token(token)
    assert payload is not None
    assert payload["sub"] == "user-2"
    assert payload["papel"] == "admin"
    assert payload["type"] == "refresh"


def test_decode_token_returns_none_for_invalid_token():
    assert decode_token("token-invalido") is None
