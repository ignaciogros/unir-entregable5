from unittest.mock import MagicMock, patch

import pytest

from app import init_db, rag
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


def _mock_chat(answer: str):
    """Devuelve un cliente Azure OpenAI simulado que responde `answer`."""
    response = MagicMock()
    response.choices[0].message.content = answer
    client = MagicMock()
    client.chat.completions.create.return_value = response
    return client


# --- Sin colección activa / sin resultados: rechazo explícito ---

def test_no_active_collection_returns_refusal(db):
    result = rag.answer_question(db, "¿Qué es la fotosíntesis?")
    assert result["answer"] == rag.REFUSAL
    assert result["sources"] == []
    assert result["low_confidence"] is True


def test_no_search_results_returns_refusal(db):
    db.add(Config(key="active_collection", value="knowledge_1"))
    db.commit()
    with patch("app.rag.embed_text", return_value=[0.1] * 1536), \
         patch("app.vector_store.search", return_value=[]):
        result = rag.answer_question(db, "pregunta")
    assert result["answer"] == rag.REFUSAL
    assert result["sources"] == []


# --- Flujo completo con contexto ---

def test_answer_with_context_returns_sources(db):
    db.add(Config(key="active_collection", value="knowledge_1"))
    db.commit()
    chunks = [
        {"source": "tema1.pdf", "page": 12, "score": 0.92, "content": "La célula es..."},
        {"source": "tema1.pdf", "page": 14, "score": 0.87, "content": "El núcleo..."},
    ]
    with patch("app.rag.embed_text", return_value=[0.1] * 1536), \
         patch("app.vector_store.search", return_value=chunks), \
         patch("app.rag._chat_client", return_value=_mock_chat("Una respuesta anclada.")):
        result = rag.answer_question(db, "¿Qué es la célula?")

    assert result["answer"] == "Una respuesta anclada."
    assert result["low_confidence"] is False
    assert len(result["sources"]) == 2
    assert result["sources"][0]["source"] == "tema1.pdf"
    assert result["sources"][0]["page"] == 12
    assert result["sources"][0]["score"] == 0.92


def test_low_confidence_when_below_threshold(db):
    db.add(Config(key="active_collection", value="knowledge_1"))
    db.commit()
    chunks = [{"source": "x.pdf", "page": 1, "score": 0.5, "content": "algo"}]
    with patch("app.rag.embed_text", return_value=[0.1] * 1536), \
         patch("app.vector_store.search", return_value=chunks), \
         patch("app.rag._chat_client", return_value=_mock_chat("respuesta")):
        result = rag.answer_question(db, "pregunta")
    assert result["low_confidence"] is True


def test_high_confidence_at_threshold(db):
    db.add(Config(key="active_collection", value="knowledge_1"))
    db.commit()
    chunks = [{"source": "x.pdf", "page": 1, "score": 0.75, "content": "algo"}]
    with patch("app.rag.embed_text", return_value=[0.1] * 1536), \
         patch("app.vector_store.search", return_value=chunks), \
         patch("app.rag._chat_client", return_value=_mock_chat("respuesta")):
        result = rag.answer_question(db, "pregunta")
    assert result["low_confidence"] is False


# --- Historial y construcción del prompt ---

def test_history_included_in_messages(db):
    db.add(Config(key="active_collection", value="knowledge_1"))
    db.commit()
    chunks = [{"source": "x.pdf", "page": 1, "score": 0.9, "content": "ctx"}]
    client = _mock_chat("ok")
    history = [{"q": "hola", "a": "qué tal"}]
    with patch("app.rag.embed_text", return_value=[0.1] * 1536), \
         patch("app.vector_store.search", return_value=chunks), \
         patch("app.rag._chat_client", return_value=client):
        rag.answer_question(db, "nueva pregunta", history)

    messages = client.chat.completions.create.call_args.kwargs["messages"]
    roles = [m["role"] for m in messages]
    assert roles == ["system", "user", "assistant", "user"]
    assert messages[0]["content"] == rag.SYSTEM_PROMPT
    assert "hola" in messages[1]["content"]
    assert "CONTEXTO" in messages[-1]["content"]
    assert "nueva pregunta" in messages[-1]["content"]


def test_system_prompt_preserves_grounding_rules():
    assert "EXCLUSIVAMENTE en español" in rag.SYSTEM_PROMPT
    assert "SOLO la información" in rag.SYSTEM_PROMPT
    assert "No uses conocimiento externo" in rag.SYSTEM_PROMPT
    assert rag.REFUSAL in rag.SYSTEM_PROMPT


def test_build_context_labels_sources():
    chunks = [{"source": "doc.pdf", "page": 3, "score": 0.8, "content": "texto"}]
    context = rag._build_context(chunks)
    assert "doc.pdf" in context
    assert "pág. 3" in context
    assert "texto" in context


def test_answer_strips_whitespace(db):
    db.add(Config(key="active_collection", value="knowledge_1"))
    db.commit()
    chunks = [{"source": "x.pdf", "page": 1, "score": 0.9, "content": "ctx"}]
    with patch("app.rag.embed_text", return_value=[0.1] * 1536), \
         patch("app.vector_store.search", return_value=chunks), \
         patch("app.rag._chat_client", return_value=_mock_chat("  respuesta  \n")):
        result = rag.answer_question(db, "pregunta")
    assert result["answer"] == "respuesta"
