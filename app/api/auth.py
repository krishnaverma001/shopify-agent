"""
Simple username-based JWT auth for ShopBot MVP.
No email, no password complexity requirements.
Users are created on first login (username + password).
Tokens are signed HS256 JWTs; secret lives in settings.SECRET_KEY.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import hashlib
import hmac
import json
import base64

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .models import AuthRequest, AuthResponse
from app.logging import get_logger

logger = get_logger(__name__)

try:
    from jose import jwt, JWTError
    USE_JOSE = True
except ImportError:
    USE_JOSE = False

from app.config import settings

router = APIRouter()
security = HTTPBearer(auto_error=False)

# In-memory user store (swap for a real DB for production)
# Structure: { username: { "password_hash": str, "created_at": str } }
_users: dict[str, dict] = {}

TOKEN_EXPIRE_HOURS = 72
ALGORITHM = "HS256"
SECRET = getattr(settings, "SECRET_KEY", "shopbot-dev-secret")


# Password hashing (SHA-256 + HMAC, no bcrypt dep needed for MVP) 
def _hash_password(password: str) -> str:
    return hmac.new(
        SECRET.encode(),
        password.encode(),
        hashlib.sha256,
    ).hexdigest()


def _verify_password(password: str, hashed: str) -> bool:
    return hmac.compare_digest(_hash_password(password), hashed)


# JWT helpers 
def _create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": (datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)).timestamp(),
        "iat": datetime.now(timezone.utc).timestamp(),
    }
    if USE_JOSE:
        return jwt.encode(payload, SECRET, algorithm=ALGORITHM)
    
    
    return _pure_encode(payload)    # Fallback


def _decode_token(token: str) -> Optional[str]:
    """Returns username or None if invalid/expired."""
    try:
        if USE_JOSE:
            payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        else:
            payload = _pure_decode(token)
        exp = payload.get("exp", 0)
        if datetime.now(timezone.utc).timestamp() > exp:
            return None
        return payload.get("sub")
    except Exception:
        logger.info(
            "Token decode failed"
        )
        return None


# Pure-python JWT (HS256) fallback 
def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * pad)

def _pure_encode(payload: dict) -> str:
    header = _b64url_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    body   = _b64url_encode(json.dumps(payload).encode())
    sig    = _b64url_encode(
        hmac.new(SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    )
    return f"{header}.{body}.{sig}"

def _pure_decode(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token")
    header, body, sig = parts
    expected = _b64url_encode(
        hmac.new(SECRET.encode(), f"{header}.{body}".encode(), hashlib.sha256).digest()
    )
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid signature")
    return json.loads(_b64url_decode(body))


# Dependency: get current user from Bearer token 
def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    username = _decode_token(credentials.credentials)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return username


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    if not credentials:
        return None
    return _decode_token(credentials.credentials)

# Routes
@router.post("/auth/login", response_model=AuthResponse)
async def login_or_register(req: AuthRequest):
    """
    Single endpoint: if username exists → verify password (login).
    If username doesn't exist → create account (register).
    This is intentional for a frictionless MVP.
    """
    username = req.username.strip().lower()
    password = req.password

    if not username or len(username) < 2:
        raise HTTPException(status_code=400, detail="Username must be at least 2 characters")
    if not password or len(password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    if len(username) > 32:
        raise HTTPException(status_code=400, detail="Username too long")

    created = False
    if username in _users:
        logger.info(
            f"Login attempt user={username}"
        )

        # Login flow
        if not _verify_password(
            password, 
            _users[username]["password_hash"]
        ):
            raise HTTPException(
                status_code=401, 
                detail="Incorrect password"
            )
    else:
        # Register flow

        logger.info(
            f"Registering user={username}"
        )
        _users[username] = {
            "password_hash": _hash_password(password),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        created = True

    token = _create_token(username)
    logger.info(
        f"Authenticated user={username}"
    )
    return AuthResponse(token=token, username=username, created=created)


@router.get("/auth/me")
async def me(username: str = Depends(get_current_user)):
    return {"username": username}