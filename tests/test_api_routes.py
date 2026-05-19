import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestHealthRoutes:
    def test_health_check(self):
        response = client.get("/api/v1/health/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "ev-battery-platform" in data["service"]

    def test_liveness(self):
        response = client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["alive"] is True


class TestAuthRoutes:
    def test_login_success(self):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin-secret"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "wrong"},
        )
        assert response.status_code == 401

    def test_login_unknown_user(self):
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "nobody", "password": "secret"},
        )
        assert response.status_code == 401

    def test_protected_route_without_token(self):
        response = client.get("/api/v1/entities/")
        assert response.status_code == 403

    def test_protected_route_with_invalid_token(self):
        response = client.get(
            "/api/v1/entities/",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 403

    def test_protected_route_with_valid_token(self):
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin-secret"},
        )
        token = login_resp.json()["access_token"]
        response = client.get(
            "/api/v1/entities/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200


class TestEntityRoutes:
    def setup_method(self):
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin-secret"},
        )
        self.token = login_resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_list_entities(self):
        response = client.get("/api/v1/entities/", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data

    def test_list_entities_filtered_by_type(self):
        response = client.get("/api/v1/entities/?entity_type=pack", headers=self.headers)
        assert response.status_code == 200

    def test_get_nonexistent_entity(self):
        response = client.get(
            "/api/v1/entities/00000000-0000-0000-0000-000000000000",
            headers=self.headers,
        )
        assert response.status_code == 404

    def test_get_entity_by_part_number_not_found(self):
        response = client.get(
            "/api/v1/entities/by-part-number/NONEXISTENT123",
            headers=self.headers,
        )
        assert response.status_code == 404

    def test_create_entity(self):
        response = client.post(
            "/api/v1/entities/",
            headers=self.headers,
            json={"entity_type": "pack", "normalized_primary_part_number": "TEST123"},
        )
        assert response.status_code == 201

    def test_create_duplicate_entity_conflict(self):
        client.post(
            "/api/v1/entities/",
            headers=self.headers,
            json={"entity_type": "pack", "normalized_primary_part_number": "DUPTEST123"},
        )
        response = client.post(
            "/api/v1/entities/",
            headers=self.headers,
            json={"entity_type": "pack", "normalized_primary_part_number": "DUPTEST123"},
        )
        assert response.status_code == 409


class TestScrapeRoutes:
    def setup_method(self):
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin-secret"},
        )
        self.token = login_resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_create_scrape_plan(self):
        response = client.post(
            "/api/v1/scrape/",
            headers=self.headers,
            json={"part_number": "9701234567890", "brand": "porsche", "waves": 3},
        )
        assert response.status_code == 200
        data = response.json()
        assert "plan_id" in data
        assert data["status"] == "open"

    def test_create_scrape_plan_viewer_forbidden(self):
        viewer_login = client.post(
            "/api/v1/auth/login",
            json={"username": "viewer", "password": "viewer-secret"},
        )
        viewer_token = viewer_login.json()["access_token"]
        response = client.post(
            "/api/v1/scrape/",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"part_number": "9701234567890", "brand": "porsche"},
        )
        assert response.status_code == 403


class TestSearchRoutes:
    def setup_method(self):
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin-secret"},
        )
        self.token = login_resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_cross_reference_search_requires_query(self):
        response = client.get("/api/v1/search/cross-reference", headers=self.headers)
        assert response.status_code == 422

    def test_cross_reference_search(self):
        response = client.get(
            "/api/v1/search/cross-reference?q=taycan",
            headers=self.headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "query" in data

    def test_part_number_exact_match(self):
        response = client.get(
            "/api/v1/search/part-number/ABC123",
            headers=self.headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "exact_matches" in data
        assert "fuzzy_matches" in data

    def test_superset_chain(self):
        response = client.get(
            "/api/v1/search/superset/ABC123",
            headers=self.headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "chain" in data
        assert "current_pn" in data


class TestConfigRoutes:
    def setup_method(self):
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "admin-secret"},
        )
        self.token = login_resp.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_list_brands(self):
        response = client.get("/api/v1/config/brands", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "brands" in data
        assert any(b["code"] == "porsche" for b in data["brands"])

    def test_wave_policies(self):
        response = client.get("/api/v1/config/wave-policies", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        assert "wave_policies" in data
