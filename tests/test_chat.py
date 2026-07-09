from unittest.mock import patch

import pytest

from app import init_db
from app.models import Config, UploadedFile


@pytest.fixture(autouse=True)
def seed_user(setup_test_db):
    init_db.init()


@pytest.fixture(autouse=True)
def clean_tables(setup_test_db):
    from app.database import SessionLocal
    s = SessionLocal()
    s.query(Config).delete()
    s.query(UploadedFile).delete()
    s.commit()
    s.close()


@pytest.fixture
def auth_client(client):
    client.post("/login", data={"username": "testuser", "password": "testpass123"})
    return client


# --- Acceso ---

def test_chat_requires_auth(client):
    response = client.get("/chat", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert "/login" in response.headers["location"]


def test_chat_page_renders(auth_client):
    response = auth_client.get("/chat")
    assert response.status_code == 200
    assert "Chat" in response.text
    assert 'id="conversation"' in response.text


# --- Preguntar ---

def test_ask_returns_answer_and_sources(auth_client):
    result = {
        "answer": "Respuesta anclada al contexto.",
        "sources": [{"source": "tema1.pdf", "page": 12, "score": 0.92}],
        "low_confidence": False,
    }
    with patch("app.chat.rag.answer_question", return_value=result):
        response = auth_client.post("/chat/ask", data={"question": "¿Qué es?"})
    assert response.status_code == 200
    assert "Respuesta anclada al contexto." in response.text
    assert "tema1.pdf" in response.text
    assert "92%" in response.text
    assert "¿Qué es?" in response.text


def test_ask_shows_low_confidence_warning(auth_client):
    result = {"answer": "Dudoso", "sources": [], "low_confidence": True}
    with patch("app.chat.rag.answer_question", return_value=result):
        response = auth_client.post("/chat/ask", data={"question": "algo"})
    assert "Baja confianza" in response.text


def test_ask_refusal_has_no_sources_block(auth_client):
    from app.rag import REFUSAL
    result = {"answer": REFUSAL, "sources": [], "low_confidence": True}
    with patch("app.chat.rag.answer_question", return_value=result):
        response = auth_client.post("/chat/ask", data={"question": "algo"})
    assert REFUSAL in response.text
    assert "<details" not in response.text


def test_ask_sets_history_cookie(auth_client):
    result = {"answer": "Hola", "sources": [], "low_confidence": False}
    with patch("app.chat.rag.answer_question", return_value=result):
        response = auth_client.post("/chat/ask", data={"question": "saludo"})
    assert "chat_history" in response.headers.get("set-cookie", "")


def test_history_persists_across_requests(auth_client):
    result = {"answer": "Primera respuesta", "sources": [], "low_confidence": False}
    with patch("app.chat.rag.answer_question", return_value=result):
        auth_client.post("/chat/ask", data={"question": "primera pregunta"})
    # La página de chat debe re-renderizar el historial desde la cookie
    page = auth_client.get("/chat")
    assert "primera pregunta" in page.text
    assert "Primera respuesta" in page.text


def test_history_passed_to_rag(auth_client):
    result = {"answer": "R2", "sources": [], "low_confidence": False}
    with patch("app.chat.rag.answer_question", return_value=result) as mock_answer:
        auth_client.post("/chat/ask", data={"question": "q1"})
        auth_client.post("/chat/ask", data={"question": "q2"})
    # En la segunda llamada, el historial debe contener el primer intercambio
    second_call_history = mock_answer.call_args_list[1].args[2]
    assert any(e["q"] == "q1" for e in second_call_history)


def test_history_capped_at_six(auth_client):
    result = {"answer": "a", "sources": [], "low_confidence": False}
    with patch("app.chat.rag.answer_question", return_value=result):
        for i in range(8):
            auth_client.post("/chat/ask", data={"question": f"q{i}"})
    page = auth_client.get("/chat")
    # Solo los últimos 6 intercambios permanecen
    assert "q0" not in page.text
    assert "q1" not in page.text
    assert "q7" in page.text


def test_load_history_ignores_bad_cookie(auth_client):
    auth_client.cookies.set("chat_history", "cookie-manipulada-invalida")
    result = {"answer": "ok", "sources": [], "low_confidence": False}
    with patch("app.chat.rag.answer_question", return_value=result):
        response = auth_client.post("/chat/ask", data={"question": "hola"})
    assert response.status_code == 200
