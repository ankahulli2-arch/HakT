import base64
import json
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from sqlalchemy import Text, TypeDecorator

from app.core.config import settings


def _master_key() -> bytes:
    kdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"fsp-talent-pii-v1", info=b"pii-master")
    return kdf.derive(settings.secret_key.encode())


_PREFIX = "enc.v1."
_CIPHER = AESGCM(_master_key())


def encrypt(value: str, aad: bytes) -> str:
    nonce = os.urandom(12)
    return _PREFIX + base64.b64encode(nonce + _CIPHER.encrypt(nonce, value.encode(), aad)).decode()


def decrypt(value: str, aad: bytes) -> str:
    if not value.startswith(_PREFIX):
        return value
    raw = base64.b64decode(value[len(_PREFIX):])
    return _CIPHER.decrypt(raw[:12], raw[12:], aad).decode()


class Encrypted(TypeDecorator):
    """Прозрачное поле-шифрование: AES-256-GCM, AAD привязывает шифртекст
    к (таблица, поле) — перенос между полями/записями не расшифровывается.
    Для JSON-полей шифруется сериализованное значение."""
    impl = Text
    cache_ok = True

    def __init__(self, aad: str, json_field: bool = False):
        super().__init__()
        self.aad = aad.encode()
        self.json_field = json_field

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if self.json_field:
            value = json.dumps(value, ensure_ascii=False)
        return encrypt(str(value), self.aad)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            value = decrypt(value, self.aad)
        except Exception:
            return {} if self.json_field else ""
        return json.loads(value) if self.json_field else value
