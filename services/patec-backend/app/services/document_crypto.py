import base64
import hashlib
import os
import tempfile
from contextlib import contextmanager
from typing import Iterator

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_ENCRYPTED_PREFIX = b"PATECENC1:"


def _resolve_fernet_key() -> bytes:
    raw_key = settings.DOCUMENT_ENCRYPTION_KEY.strip()
    if raw_key:
        return raw_key.encode("utf-8")

    # Fallback deterministic key from SECRET_KEY to keep encryption enabled by default.
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def _fernet() -> Fernet:
    return Fernet(_resolve_fernet_key())


def encrypt_bytes(data: bytes) -> bytes:
    encrypted = _fernet().encrypt(data)
    return _ENCRYPTED_PREFIX + encrypted


def decrypt_bytes(data: bytes) -> bytes:
    # Backward compatibility with old plaintext files.
    if not data.startswith(_ENCRYPTED_PREFIX):
        return data

    token = data[len(_ENCRYPTED_PREFIX):]
    try:
        return _fernet().decrypt(token)
    except InvalidToken as exc:
        raise ValueError("Falha ao descriptografar arquivo armazenado") from exc


@contextmanager
def decrypted_temp_file(stored_path: str, ext: str) -> Iterator[str]:
    with open(stored_path, "rb") as f:
        plaintext = decrypt_bytes(f.read())

    fd, temp_path = tempfile.mkstemp(suffix=f".{ext}")
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(plaintext)
        yield temp_path
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
