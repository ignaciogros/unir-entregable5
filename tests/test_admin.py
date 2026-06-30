import io
from unittest.mock import patch
import pytest
from app import init_db
from app.models import Config


@pytest.fixture(autouse=True)
def seed_user(setup_test_db):
    init_db.init()


@pytest.fixture(autouse=True)
def clean_tables(setup_test_db):
    from app.database import SessionLocal
    from app.models import UploadedFile
    s = SessionLocal()
    s.query(Config).delete()
    s.query(UploadedFile).delete()
    s.commit()
    s.close()


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


# --- Proceso ---

def test_process_starts_background_task_and_redirects(auth_client):
    with patch("app.ingest.process_all_pdfs"):
        response = auth_client.post("/admin/process", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/admin")


# --- Status ---

def test_status_returns_json(auth_client):
    response = auth_client.get("/admin/status")
    assert response.status_code == 200
    data = response.json()
    assert "processing" in data
    assert "active_collection" in data
    assert "total_vectors" in data


# --- Restaurar ---

def test_restore_no_previous_still_redirects(auth_client):
    response = auth_client.post("/admin/restore", follow_redirects=False)
    assert response.status_code == 303


def test_restore_swaps_collections(auth_client, db):
    db.add(Config(key="active_collection", value="knowledge_200"))
    db.add(Config(key="previous_collection", value="knowledge_100"))
    db.commit()

    auth_client.post("/admin/restore")

    active = db.query(Config).filter_by(key="active_collection").first()
    assert active.value == "knowledge_100"
