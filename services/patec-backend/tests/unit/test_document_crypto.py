from pathlib import Path

from app.services.document_crypto import decrypt_bytes, decrypted_temp_file, encrypt_bytes


def test_encrypt_and_decrypt_roundtrip():
    raw = b"conteudo-super-secreto"
    encrypted = encrypt_bytes(raw)
    assert encrypted != raw
    assert decrypt_bytes(encrypted) == raw


def test_decrypt_backward_compat_plaintext():
    raw = b"arquivo-antigo-sem-criptografia"
    assert decrypt_bytes(raw) == raw


def test_decrypted_temp_file_context_manager(tmp_path: Path):
    stored = tmp_path / "sample.bin"
    stored.write_bytes(encrypt_bytes(b"abc-123"))

    with decrypted_temp_file(str(stored), "txt") as temp_path:
        data = Path(temp_path).read_bytes()
        assert data == b"abc-123"

    assert stored.exists()
