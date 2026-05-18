from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import structlog
from app.api.middleware.auth import create_access_token, JWTBearer, decode_token
from datetime import timedelta

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


DEMO_USERS = {
    "admin": {"password": "admin-secret", "role": "admin"},
    "operator": {"password": "operator-secret", "role": "operator"},
    "viewer": {"password": "viewer-secret", "role": "viewer"},
}


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    user = DEMO_USERS.get(req.username)
    if not user or user["password"] != req.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": req.username, "role": user["role"]})
    return TokenResponse(access_token=token)


@router.get("/me")
async def get_current_user(credentials: dict = Depends(JWTBearer())):
    return {"username": credentials.get("sub"), "role": credentials.get("role")}
