from unittest.mock import MagicMock, patch
import pytest
from app import init_db
from app.models import Config


@pytest.fixture(autouse=True)
def seed_user(setup_test_db):
    init_db.init()


@pytest.fixture(autouse=True)
def clean_config(setup_test_db):
    """Limpia la tabla config antes de cada test para evitar conflictos de clave única."""
    from app.database import SessionLocal

    session = SessionLocal()
    session.query(Config).delete()
    session.commit()
    session.close()


@pytest.fixture
def mock_qdrant():
    with patch("app.vector_store.get_client") as mock_get:
        mock_client = MagicMock()
        mock_get.return_value = mock_client
        yield mock_client


# --- get_active_collection ---


def test_get_active_collection_none(db):
    from app.vector_store import get_active_collection

    assert get_active_collection(db) is None


def test_get_active_collection_returns_value(db):
    from app.vector_store import get_active_collection

    db.add(Config(key="active_collection", value="knowledge_123"))
    db.commit()
    assert get_active_collection(db) == "knowledge_123"


# --- create_collection ---


def test_create_collection_calls_client(mock_qdrant):
    from app.vector_store import create_collection

    mock_qdrant.collection_exists.return_value = False
    create_collection("test_col")
    mock_qdrant.create_collection.assert_called_once()
    assert (
        mock_qdrant.create_collection.call_args.kwargs["collection_name"] == "test_col"
    )


def test_create_collection_skips_if_exists(mock_qdrant):
    from app.vector_store import create_collection

    mock_qdrant.collection_exists.return_value = True
    create_collection("test_col")
    mock_qdrant.create_collection.assert_not_called()


# --- upsert_points ---


def test_upsert_points_calls_client(mock_qdrant):
    from app.vector_store import upsert_points
    from qdrant_client.models import PointStruct

    points = [
        PointStruct(
            id=1,
            vector=[0.1] * 1536,
            payload={"source": "a.pdf", "page": 1, "content": "hola"},
        )
    ]
    upsert_points("test_col", points)
    mock_qdrant.upsert.assert_called_once_with(
        collection_name="test_col", points=points
    )


# --- search ---


def test_search_returns_formatted_results(mock_qdrant):
    from app.vector_store import search

    hit = MagicMock()
    hit.payload = {"source": "doc.pdf", "page": 3, "content": "contenido de prueba"}
    hit.score = 0.92
    mock_response = MagicMock()
    mock_response.points = [hit]
    mock_qdrant.query_points.return_value = mock_response

    results = search("test_col", [0.1] * 1536)

    assert len(results) == 1
    assert results[0]["source"] == "doc.pdf"
    assert results[0]["page"] == 3
    assert results[0]["score"] == 0.92
    assert results[0]["content"] == "contenido de prueba"


def test_search_empty_results(mock_qdrant):
    from app.vector_store import search

    mock_response = MagicMock()
    mock_response.points = []
    mock_qdrant.query_points.return_value = mock_response
    assert search("test_col", [0.0] * 1536) == []


# --- delete_by_source ---


def test_delete_by_source_calls_client(mock_qdrant):
    from app.vector_store import delete_by_source

    delete_by_source("test_col", "borrar.pdf")
    mock_qdrant.delete.assert_called_once()


# --- swap_collections ---


def test_swap_first_time(db, mock_qdrant):
    from app.vector_store import swap_collections, get_active_collection

    swap_collections(db, "knowledge_100")
    assert get_active_collection(db) == "knowledge_100"
    mock_qdrant.delete_collection.assert_not_called()


def test_swap_moves_active_to_previous(db, mock_qdrant):
    from app.vector_store import swap_collections, get_active_collection

    db.add(Config(key="active_collection", value="knowledge_100"))
    db.commit()

    swap_collections(db, "knowledge_200")

    assert get_active_collection(db) == "knowledge_200"
    prev = db.query(Config).filter_by(key="previous_collection").first()
    assert prev.value == "knowledge_100"
    mock_qdrant.delete_collection.assert_not_called()


def test_swap_deletes_oldest_collection(db, mock_qdrant):
    from app.vector_store import swap_collections

    db.add(Config(key="active_collection", value="knowledge_200"))
    db.add(Config(key="previous_collection", value="knowledge_100"))
    db.commit()

    swap_collections(db, "knowledge_300")

    mock_qdrant.delete_collection.assert_called_once_with(
        collection_name="knowledge_100"
    )
    prev = db.query(Config).filter_by(key="previous_collection").first()
    assert prev.value == "knowledge_200"


# --- restore_collection ---


def test_restore_no_previous_returns_false(db):
    from app.vector_store import restore_collection

    assert restore_collection(db) is False


def test_restore_swaps_active_and_previous(db):
    from app.vector_store import restore_collection, get_active_collection

    db.add(Config(key="active_collection", value="knowledge_200"))
    db.add(Config(key="previous_collection", value="knowledge_100"))
    db.commit()

    result = restore_collection(db)

    assert result is True
    assert get_active_collection(db) == "knowledge_100"
    prev = db.query(Config).filter_by(key="previous_collection").first()
    assert prev.value == "knowledge_200"
