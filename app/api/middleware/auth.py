from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from datetime import datetime, timedelta
import os
import structlog

logger = structlog.get_logger()

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

Roles = {
    "admin": ["read", "write", "delete", "admin"],
    "operator": ["read", "write"],
    "viewer": ["read"],
}


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        logger.warning("token_decode_failed", error=str(e))
        return None


class JWTBearer(HTTPBearer):
    def __init__(self, roles: list[str] = None, **kwargs):
        super().__init__(**kwargs)
        self.roles = roles or []

    async def __call__(self, request: Request) -> dict:
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        if not credentials:
            raise HTTPException(status_code=403, detail="Missing credentials")

        token_data = decode_token(credentials.credentials)
        if not token_data:
            raise HTTPException(status_code=403, detail="Invalid token")

        if self.roles:
            user_role = token_data.get("role", "viewer")
            allowed = Roles.get(user_role, [])
            if not any(r in allowed for r in self.roles):
                raise HTTPException(status_code=403, detail="Insufficient permissions")

        return token_data


def require_role(*roles):
    return JWTBearer(roles=list(roles))


def admin_only(): return JWTBearer(["admin"])
def operator_or_admin(): return JWTBearer(["admin", "operator"])
def read_only(): return JWTBearer(["admin", "operator", "viewer"])
