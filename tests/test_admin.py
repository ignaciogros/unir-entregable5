import io
import pytest
from app import init_db


@pytest.fixture(autouse=True)
def seed_user(setup_test_db):
    init_db.init()


@pytest.fixture
def auth_client(client):
    client.post("/login", data={"username": "testuser", "password": "testpass123"})
    return client


# --- Acceso sin autenticación ---

def test_admin_requires_auth(client):
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "/login" in response.headers["location"]


# --- Renderizado ---

def test_admin_page_renders(auth_client):
    response = auth_client.get("/admin")
    assert response.status_code == 200
    assert "Administración" in response.text


def test_admin_shows_no_files_message(auth_client):
    response = auth_client.get("/admin")
    assert "No hay documentos" in response.text


# --- Subida de PDF ---

def test_upload_valid_pdf(auth_client):
    pdf = b"%PDF-1.4\n%%EOF"
    response = auth_client.post(
        "/admin/upload",
        files={"file": ("muestra.pdf", io.BytesIO(pdf), "application/pdf")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith("/admin")


def test_upload_shows_file_in_list(auth_client):
    pdf = b"%PDF-1.4\n%%EOF"
    auth_client.post(
        "/admin/upload",
        files={"file": ("visible.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    response = auth_client.get("/admin")
    assert "visible.pdf" in response.text


def test_upload_non_pdf_extension_rejected(auth_client):
    response = auth_client.post(
        "/admin/upload",
        files={"file": ("doc.txt", io.BytesIO(b"texto plano"), "text/plain")},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "PDF" in response.text


def test_upload_fake_pdf_extension_rejected(auth_client):
    """Fichero con extensión .pdf pero sin magic bytes %PDF."""
    response = auth_client.post(
        "/admin/upload",
        files={"file": ("trampa.pdf", io.BytesIO(b"no es un pdf real"), "application/pdf")},
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_upload_too_large_rejected(auth_client):
    large = b"%PDF-" + b"x" * (21 * 1024 * 1024)
    response = auth_client.post(
        "/admin/upload",
        files={"file": ("grande.pdf", io.BytesIO(large), "application/pdf")},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "20 MB" in response.text


# --- Borrado ---

def test_delete_pdf(auth_client):
    pdf = b"%PDF-1.4\n%%EOF"
    auth_client.post(
        "/admin/upload",
        files={"file": ("borrar.pdf", io.BytesIO(pdf), "application/pdf")},
    )
    response = auth_client.post("/admin/delete/borrar.pdf", follow_redirects=False)
    assert response.status_code == 303
    page = auth_client.get("/admin")
    assert "borrar.pdf" not in page.text


def test_delete_nonexistent_does_not_crash(auth_client):
    response = auth_client.post("/admin/delete/fantasma.pdf", follow_redirects=False)
    assert response.status_code == 303


# --- Proceso (placeholder) ---

def test_process_returns_not_implemented(auth_client):
    response = auth_client.post("/admin/process")
    assert response.status_code == 200
    assert response.json()["status"] == "not_implemented"
