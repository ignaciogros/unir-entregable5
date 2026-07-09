from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_expected_keys():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    for key in ("status", "postgres", "qdrant", "active_collection", "total_vectors"):
        assert key in body


def test_health_all_connected():
    with patch("app.main.vector_store.get_client") as mock_client:
        mock_client.return_value.get_collections.return_value = MagicMock()
        response = client.get("/health")
    body = response.json()
    assert body["status"] == "ok"
    assert body["postgres"] == "connected"
    assert body["qdrant"] == "connected"


def test_health_reports_active_collection_and_vectors():
    with (
        patch("app.main.vector_store.get_client") as mock_client,
        patch(
            "app.main.vector_store.get_active_collection", return_value="knowledge_42"
        ),
        patch("app.main.vector_store.get_total_vectors", return_value=137),
    ):
        mock_client.return_value.get_collections.return_value = MagicMock()
        response = client.get("/health")
    body = response.json()
    assert body["active_collection"] == "knowledge_42"
    assert body["total_vectors"] == 137


def test_health_qdrant_down_is_degraded():
    with patch("app.main.vector_store.get_client", side_effect=Exception("sin qdrant")):
        response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["qdrant"] == "disconnected"
    assert body["status"] == "degraded"


def test_root_redirects_to_login():
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (307, 302)
    assert response.headers["location"] == "/login"
