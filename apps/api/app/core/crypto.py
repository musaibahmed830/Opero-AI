"""Symmetric encryption for secrets stored at rest — OAuth refresh tokens above all.

Per docs/SYSTEM_ARCHITECTURE.md §4: connected-account OAuth tokens are the
highest-sensitivity secret in the system. They are encrypted with this module
before being written to the database and decrypted only at the point of use.
"""

from functools import lru_cache

from cryptography.fernet import Fernet

from app.core.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().token_encryption_key.encode())


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
