import os

import openai
from sqlalchemy.orm import Session

from app import vector_store
from app.ingest import embed_text

SYSTEM_PROMPT = (
    "Eres un asistente que responde EXCLUSIVAMENTE en español usando SOLO la información "
    "proporcionada en el CONTEXTO. No uses conocimiento externo bajo ninguna circunstancia. "
    "Si la información no está en el contexto, responde exactamente:\n"
    '"No encuentro información sobre eso en los documentos disponibles."'
)

REFUSAL = "No encuentro información sobre eso en los documentos disponibles."
CONFIDENCE_THRESHOLD = 0.75
TOP_K = 5
MAX_HISTORY = 6


def _chat_client() -> openai.AzureOpenAI:
    return openai.AzureOpenAI(
        api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    )


def _build_context(chunks: list[dict]) -> str:
    parts = []
    for c in chunks:
        parts.append(f"[Fuente: {c['source']} · pág. {c['page']}]\n{c['content']}")
    return "\n\n".join(parts)


def _build_messages(context: str, question: str, history: list[dict]) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for exchange in history[-MAX_HISTORY:]:
        messages.append({"role": "user", "content": exchange["q"]})
        messages.append({"role": "assistant", "content": exchange["a"]})
    messages.append({
        "role": "user",
        "content": f"CONTEXTO:\n{context}\n\nPREGUNTA: {question}",
    })
    return messages


def answer_question(
    db: Session, question: str, history: list[dict] | None = None
) -> dict:
    """Pipeline RAG: embed → retrieve → generate.

    Devuelve {"answer": str, "sources": [{"source", "page", "score"}], "low_confidence": bool}.
    Preserva los cuatro mecanismos de grounding (prompt restrictivo, rechazo explícito,
    umbral de confianza y citas obligatorias).
    """
    history = history or []

    collection = vector_store.get_active_collection(db)
    if not collection:
        return {"answer": REFUSAL, "sources": [], "low_confidence": True}

    vector = embed_text(question)
    chunks = vector_store.search(collection, vector, top_k=TOP_K)
    if not chunks:
        return {"answer": REFUSAL, "sources": [], "low_confidence": True}

    context = _build_context(chunks)
    messages = _build_messages(context, question, history)

    client = _chat_client()
    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "chat"),
        messages=messages,
        temperature=0.2,
    )
    answer = (response.choices[0].message.content or "").strip()

    max_score = max((c["score"] for c in chunks), default=0.0)
    low_confidence = max_score < CONFIDENCE_THRESHOLD

    sources = [
        {"source": c["source"], "page": c["page"], "score": c["score"]} for c in chunks
    ]

    return {"answer": answer, "sources": sources, "low_confidence": low_confidence}
