import os
from pathlib import Path
from unittest.mock import MagicMock, patch
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


# --- parse_pdf ---

def test_parse_pdf_extracts_text():
    from app.ingest import parse_pdf
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Texto de la página"
    with patch("app.ingest.pypdf.PdfReader") as mock_reader:
        mock_reader.return_value.pages = [mock_page]
        result = parse_pdf(Path("fake.pdf"))
    assert len(result) == 1
    assert result[0]["text"] == "Texto de la página"
    assert result[0]["page"] == 1


def test_parse_pdf_skips_empty_pages():
    from app.ingest import parse_pdf
    page_empty = MagicMock()
    page_empty.extract_text.return_value = "   "
    page_text = MagicMock()
    page_text.extract_text.return_value = "Contenido real"
    with patch("app.ingest.pypdf.PdfReader") as mock_reader:
        mock_reader.return_value.pages = [page_empty, page_text]
        result = parse_pdf(Path("fake.pdf"))
    assert len(result) == 1
    assert result[0]["page"] == 2


def test_parse_pdf_none_text_handled():
    from app.ingest import parse_pdf
    mock_page = MagicMock()
    mock_page.extract_text.return_value = None
    with patch("app.ingest.pypdf.PdfReader") as mock_reader:
        mock_reader.return_value.pages = [mock_page]
        result = parse_pdf(Path("fake.pdf"))
    assert result == []


# --- chunk_text ---

def test_chunk_text_single_chunk():
    from app.ingest import chunk_text
    pages = [{"text": "Texto corto", "page": 1}]
    chunks = chunk_text(pages, "doc.pdf")
    assert len(chunks) == 1
    assert chunks[0]["source"] == "doc.pdf"
    assert chunks[0]["page"] == 1
    assert chunks[0]["chunk_idx"] == 0
    assert chunks[0]["text"] == "Texto corto"


def test_chunk_text_splits_large_text():
    from app.ingest import chunk_text, CHUNK_SIZE
    long_text = "A" * (CHUNK_SIZE * 2 + 100)
    pages = [{"text": long_text, "page": 1}]
    chunks = chunk_text(pages, "doc.pdf")
    assert len(chunks) >= 2


def test_chunk_text_increments_chunk_idx():
    from app.ingest import chunk_text, CHUNK_SIZE
    text = "B" * (CHUNK_SIZE + 500)
    pages = [{"text": text, "page": 1}]
    chunks = chunk_text(pages, "doc.pdf")
    for i, chunk in enumerate(chunks):
        assert chunk["chunk_idx"] == i


def test_chunk_text_preserves_page():
    from app.ingest import chunk_text
    pages = [{"text": "Pag 1", "page": 1}, {"text": "Pag 2", "page": 2}]
    chunks = chunk_text(pages, "doc.pdf")
    assert chunks[0]["page"] == 1
    assert chunks[1]["page"] == 2


# --- embed_text ---

def test_embed_text_calls_azure_openai():
    from app.ingest import embed_text
    mock_response = MagicMock()
    mock_response.data[0].embedding = [0.1] * 1536
    with patch("app.ingest.openai.AzureOpenAI") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.embeddings.create.return_value = mock_response
        result = embed_text("texto de prueba")
    assert len(result) == 1536
    assert result[0] == 0.1


# --- process_all_pdfs ---

def test_process_all_pdfs(db):
    from app.ingest import process_all_pdfs

    uploads = Path(os.getenv("UPLOADS_DIR", "uploads"))
    pdf_file = uploads / "sample.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    db.add(UploadedFile(filename="sample.pdf", size_bytes=13))
    db.commit()

    with patch("app.ingest.parse_pdf") as mock_parse, \
         patch("app.ingest.embed_text") as mock_embed, \
         patch("app.vector_store.create_collection"), \
         patch("app.vector_store.upsert_points") as mock_upsert, \
         patch("app.vector_store.swap_collections") as mock_swap:

        mock_parse.return_value = [{"text": "Contenido", "page": 1}]
        mock_embed.return_value = [0.1] * 1536

        process_all_pdfs(db)

    mock_upsert.assert_called_once()
    mock_swap.assert_called_once()

    f = db.query(UploadedFile).filter_by(filename="sample.pdf").first()
    assert f.processed is True


def test_process_all_pdfs_skips_missing_file(db):
    from app.ingest import process_all_pdfs

    db.add(UploadedFile(filename="ghost.pdf", size_bytes=0))
    db.commit()

    with patch("app.vector_store.create_collection"), \
         patch("app.vector_store.upsert_points") as mock_upsert, \
         patch("app.vector_store.swap_collections"):

        process_all_pdfs(db)

    mock_upsert.assert_not_called()


def test_is_processing_false_by_default():
    from app import ingest
    assert ingest.is_processing() is False
