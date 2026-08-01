"""
Helpers for encrypting sensitive text (chat messages) before it's stored in
the database, and decrypting it transparently when it's read back out.

Uses Fernet (AES-128 in CBC mode with an HMAC for authentication) from the
`cryptography` package - a well-reviewed, high-level symmetric encryption
recipe that's the standard choice for "encrypt this field at rest" in
Django apps.
"""
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is None:
        _fernet = Fernet(settings.MESSAGE_ENCRYPTION_KEY)
    return _fernet


def encrypt_text(plaintext):
    if plaintext is None or plaintext == "":
        return plaintext
    token = _get_fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(value):
    if value is None or value == "":
        return value
    try:
        return _get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        # Row written before encryption was enabled, or not valid Fernet
        # data - fall back to showing it as-is rather than erroring out.
        return value
