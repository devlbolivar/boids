import base64
from datetime import datetime, timedelta, timezone
from typing import Union
import jwt
import bcrypt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from app.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # bcrypt requires bytes
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        return False

def get_password_hash(password: str) -> str:
    # Generate salt and hash
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def create_access_token(data: dict, expires_delta: Union[timedelta, None] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict | None:
    try:
        decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return decoded_token
    except jwt.InvalidTokenError:
        return None

# Tenant credential encryption helpers

def derive_tenant_key(tenant_id: str) -> bytes:
    """
    Derives a unique 32-byte key for Fernet from the MASTER_ENCRYPTION_KEY
    and the specific tenant ID to isolate cryptographic secrets.
    """
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=tenant_id.encode("utf-8"),
    )
    derived_key = hkdf.derive(settings.MASTER_ENCRYPTION_KEY.encode("utf-8"))
    return base64.urlsafe_b64encode(derived_key)

def encrypt_credential(plain_text: str, tenant_id: str) -> str:
    """
    Encrypts a sensitive credential (e.g. Apollo API Key) using a key derived from tenant_id.
    Returns a hex or string formatted representation of the cipher text.
    """
    if not plain_text:
        return ""
    key = derive_tenant_key(tenant_id)
    f = Fernet(key)
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")

def decrypt_credential(cipher_text: str, tenant_id: str) -> str:
    """
    Decrypts a sensitive credential using a key derived from tenant_id.
    """
    if not cipher_text:
        return ""
    key = derive_tenant_key(tenant_id)
    f = Fernet(key)
    return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
