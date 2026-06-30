import os
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)
from sqlalchemy.orm import Session
from app.models import Config

VECTOR_SIZE = 1536


def get_client() -> QdrantClient:
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    api_key = os.getenv("QDRANT_API_KEY") or None
    return QdrantClient(url=url, api_key=api_key)


def create_collection(name: str) -> None:
    client = get_client()
    if client.collection_exists(collection_name=name):
        return
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )


def upsert_points(collection: str, points: list[PointStruct]) -> None:
    get_client().upsert(collection_name=collection, points=points)


def search(collection: str, vector: list[float], top_k: int = 5) -> list[dict]:
    response = get_client().query_points(
        collection_name=collection,
        query=vector,
        limit=top_k,
        with_payload=True,
    )
    return [
        {
            "source": r.payload.get("source", ""),
            "page": r.payload.get("page", 0),
            "score": r.score,
            "content": r.payload.get("content", ""),
        }
        for r in response.points
    ]


def delete_by_source(collection: str, filename: str) -> None:
    get_client().delete(
        collection_name=collection,
        points_selector=Filter(
            must=[FieldCondition(key="source", match=MatchValue(value=filename))]
        ),
    )


def get_active_collection(db: Session) -> str | None:
    row = db.query(Config).filter_by(key="active_collection").first()
    return row.value if row else None


def get_total_vectors(collection: str) -> int:
    info = get_client().get_collection(collection_name=collection)
    return info.points_count or 0


def swap_collections(db: Session, new_name: str) -> None:
    """Ingesta completada: new_name → activa, activa → anterior, anterior → eliminada."""
    client = get_client()

    active_row = db.query(Config).filter_by(key="active_collection").first()
    prev_row = db.query(Config).filter_by(key="previous_collection").first()

    current_active = active_row.value if active_row else None
    current_prev = prev_row.value if prev_row else None

    # Eliminar la colección más antigua
    if current_prev:
        try:
            client.delete_collection(collection_name=current_prev)
        except Exception:
            pass

    # Rotar: activa → anterior
    if current_active:
        if prev_row:
            prev_row.value = current_active
        else:
            db.add(Config(key="previous_collection", value=current_active))
    elif prev_row:
        db.delete(prev_row)

    # Nueva colección → activa
    if active_row:
        active_row.value = new_name
    else:
        db.add(Config(key="active_collection", value=new_name))

    db.commit()


def restore_collection(db: Session) -> bool:
    """Restaura la versión anterior (swap activa ↔ anterior). Devuelve False si no hay anterior."""
    active_row = db.query(Config).filter_by(key="active_collection").first()
    prev_row = db.query(Config).filter_by(key="previous_collection").first()

    if not prev_row:
        return False

    current_active = active_row.value if active_row else None

    if active_row:
        active_row.value = prev_row.value
    else:
        db.add(Config(key="active_collection", value=prev_row.value))

    if current_active:
        prev_row.value = current_active
    else:
        db.delete(prev_row)

    db.commit()
    return True
