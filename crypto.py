# AES-GCM encryption, PBKDF2 key derivation for vault.
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

PBKDF2_ITERATIONS = 250_000
SALT_LENGTH = 16
IV_LENGTH = 12
KEY_LENGTH = 32

_in_memory_key: bytes | None = None


def set_key(key: bytes) -> None:
    global _in_memory_key
    _in_memory_key = key


def get_key() -> bytes | None:
    return _in_memory_key


def clear_key() -> None:
    global _in_memory_key
    _in_memory_key = None


def is_unlocked() -> bool:
    return _in_memory_key is not None


def generate_salt():
    return os.urandom(SALT_LENGTH)


def generate_iv():
    return os.urandom(IV_LENGTH)


def derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
        backend=default_backend(),
    )
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt(plaintext: str, key: bytes) -> tuple[str, str]:
    iv = generate_iv()
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
    return base64.b64encode(ct).decode("ascii"), base64.b64encode(iv).decode("ascii")


def decrypt(ciphertext_b64: str, iv_b64: str, key: bytes) -> str:
    ct = base64.b64decode(ciphertext_b64)
    iv = base64.b64decode(iv_b64)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, ct, None).decode("utf-8")


def salt_to_b64(salt: bytes) -> str:
    return base64.b64encode(salt).decode("ascii")


def b64_to_salt(b64: str) -> bytes:
    return base64.b64decode(b64)
