import pytest
from app.api.middleware.auth import (
    create_access_token,
    decode_token,
    JWTBearer,
    Roles,
)
from datetime import timedelta


class TestJWTAuth:
    def test_create_and_decode_token(self):
        token = create_access_token({"sub": "testuser", "role": "admin"})
        data = decode_token(token)
        assert data is not None
        assert data["sub"] == "testuser"
        assert data["role"] == "admin"

    def test_decode_invalid_token(self):
        data = decode_token("not.a.valid.token")
        assert data is None

    def test_decode_empty_token(self):
        data = decode_token("")
        assert data is None

    def test_create_token_with_expiry(self):
        token = create_access_token(
            {"sub": "testuser", "role": "viewer"},
            expires_delta=timedelta(hours=2),
        )
        data = decode_token(token)
        assert data is not None
        assert data["sub"] == "testuser"
        assert data["role"] == "viewer"
        assert "exp" in data


class TestRoles:
    def test_admin_has_all_roles(self):
        assert "admin" in Roles["admin"]
        assert "read" in Roles["admin"]
        assert "write" in Roles["admin"]
        assert "delete" in Roles["admin"]

    def test_viewer_has_read_only(self):
        assert "read" in Roles["viewer"]
        assert "write" not in Roles["viewer"]
        assert "admin" not in Roles["viewer"]

    def test_operator_has_read_write(self):
        assert "read" in Roles["operator"]
        assert "write" in Roles["operator"]
        assert "delete" not in Roles["operator"]
