import os
import time
import uuid
from pathlib import Path

import openai
import pypdf
from qdrant_client.models import PointStruct
from sqlalchemy.orm import Session

from app import vector_store
from app.models import UploadedFile

UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "uploads"))
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 200

_processing = False


def is_processing() -> bool:
    return _processing


def parse_pdf(filepath: Path) -> list[dict]:
    reader = pypdf.PdfReader(str(filepath))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append({"text": text, "page": i})
    return pages


def chunk_text(pages: list[dict], filename: str) -> list[dict]:
    chunks = []
    chunk_idx = 0
    for page_data in pages:
        text = page_data["text"]
        page = page_data["page"]
        start = 0
        while start < len(text):
            chunk = text[start : start + CHUNK_SIZE]
            if chunk.strip():
                chunks.append(
                    {
                        "text": chunk,
                        "page": page,
                        "source": filename,
                        "chunk_idx": chunk_idx,
                    }
                )
                chunk_idx += 1
            start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def embed_text(text: str) -> list[float]:
    client = openai.AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    )
    response = client.embeddings.create(
        model=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
        input=text,
    )
    return response.data[0].embedding


def process_all_pdfs(db: Session) -> None:
    global _processing
    _processing = True
    try:
        collection_name = f"knowledge_{int(time.time())}"
        vector_store.create_collection(collection_name)

        for f in db.query(UploadedFile).all():
            filepath = UPLOADS_DIR / f.filename
            if not filepath.exists():
                continue
            pages = parse_pdf(filepath)
            chunks = chunk_text(pages, f.filename)
            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embed_text(chunk["text"]),
                    payload={
                        "source": chunk["source"],
                        "page": chunk["page"],
                        "chunk_idx": chunk["chunk_idx"],
                        "content": chunk["text"],
                    },
                )
                for chunk in chunks
            ]
            if points:
                vector_store.upsert_points(collection_name, points)
            f.processed = True

        db.commit()
        vector_store.swap_collections(db, collection_name)
    finally:
        _processing = False
