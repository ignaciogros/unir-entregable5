import pytest
from fastapi.testclient import TestClient
from app import init_db


@pytest.fixture(autouse=True)
def seed_user(setup_test_db):
    init_db.init()


def test_unauthenticated_redirect_to_login(client):
    response = client.get("/chat", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "/login" in response.headers["location"]


def test_login_page_renders(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "Iniciar sesión" in response.text


def test_login_correct_credentials(client):
    response = client.post(
        "/login",
        data={"username": "testuser", "password": "testpass123"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "session" in response.cookies


def test_login_wrong_password(client):
    response = client.post(
        "/login",
        data={"username": "testuser", "password": "wrongpass"},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert "session" not in response.cookies
    assert "incorrectos" in response.text


def test_login_unknown_user(client):
    response = client.post(
        "/login",
        data={"username": "nobody", "password": "testpass123"},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert "session" not in response.cookies


def test_logout_clears_session(client):
    # Login
    client.post(
        "/login",
        data={"username": "testuser", "password": "testpass123"},
    )
    # Logout
    client.get("/logout", follow_redirects=False)
    # La cookie ya no es válida — ruta protegida redirige a login
    response = client.get("/chat", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "/login" in response.headers["location"]


def test_authenticated_access(client):
    client.post("/login", data={"username": "testuser", "password": "testpass123"})
    response = client.get("/chat")
    assert response.status_code == 200


def test_error_message_visible(client):
    response = client.post(
        "/login",
        data={"username": "testuser", "password": "bad"},
    )
    assert 'role="alert"' in response.text
    assert "incorrectos" in response.text
