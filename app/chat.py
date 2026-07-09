import os

from fastapi import APIRouter, Depends, Form, Request
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from app import rag
from app.database import get_db

SECRET_KEY = os.getenv("SECRET_KEY", "changeme-replace-in-production")
HISTORY_COOKIE = "chat_history"
HISTORY_MAX_AGE = 60 * 60 * 8  # 8 horas, igual que la sesión
MAX_EXCHANGES = 6

_signer = URLSafeTimedSerializer(SECRET_KEY)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _load_history(request: Request) -> list[dict]:
    token = request.cookies.get(HISTORY_COOKIE)
    if not token:
        return []
    try:
        data = _signer.loads(token, max_age=HISTORY_MAX_AGE)
    except BadSignature:
        return []
    return data if isinstance(data, list) else []


def _save_history(response, history: list[dict]) -> None:
    # Solo se persiste el texto (q/a) para mantener la cookie < 4 KB.
    trimmed = [{"q": e["q"], "a": e["a"]} for e in history[-MAX_EXCHANGES:]]
    token = _signer.dumps(trimmed)
    response.set_cookie(
        key=HISTORY_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=HISTORY_MAX_AGE,
    )


@router.get("/chat")
def chat_page(request: Request):
    history = _load_history(request)
    return templates.TemplateResponse(request, "chat.html", {"history": history})


@router.post("/chat/ask")
def chat_ask(
    request: Request,
    question: str = Form(...),
    db: Session = Depends(get_db),
):
    question = question.strip()
    history = _load_history(request)

    result = rag.answer_question(db, question, history)
    exchange = {
        "q": question,
        "a": result["answer"],
        "sources": result["sources"],
        "low_confidence": result["low_confidence"],
    }

    response = templates.TemplateResponse(
        request, "chat_message.html", {"ex": exchange}
    )
    _save_history(response, history + [exchange])
    return response
