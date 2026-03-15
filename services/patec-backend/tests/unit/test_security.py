from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)


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
