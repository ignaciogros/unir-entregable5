import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Form, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import vector_store
from app.auth import (
    AuthMiddleware,
    create_session,
    delete_session,
    get_current_user,
    verify_password,
)
from app.database import get_db
from app.admin import router as admin_router
from app.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app import init_db

    os.makedirs("uploads", exist_ok=True)
    init_db.init()
    yield


app = FastAPI(title="RAG Chatbot", lifespan=lifespan)
app.add_middleware(AuthMiddleware)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads", check_dir=False), name="uploads")
app.include_router(admin_router)
app.include_router(chat_router)

templates = Jinja2Templates(directory="app/templates")


@app.get("/")
def root(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/chat")
    return RedirectResponse(url="/login")


@app.get("/health")
def health(db: Session = Depends(get_db)):
    postgres_ok = False
    active_collection = None
    try:
        db.execute(text("SELECT 1"))
        postgres_ok = True
        active_collection = vector_store.get_active_collection(db)
    except Exception:
        pass

    qdrant_ok = False
    total_vectors = 0
    try:
        vector_store.get_client().get_collections()
        qdrant_ok = True
        if active_collection:
            total_vectors = vector_store.get_total_vectors(active_collection)
    except Exception:
        pass

    return {
        "status": "ok" if (postgres_ok and qdrant_ok) else "degraded",
        "postgres": "connected" if postgres_ok else "disconnected",
        "qdrant": "connected" if qdrant_ok else "disconnected",
        "active_collection": active_collection,
        "total_vectors": total_vectors,
    }


@app.get("/login")
def login_page(request: Request):
    if get_current_user(request):
        return RedirectResponse(url="/chat")
    return templates.TemplateResponse(request, "login.html")


@app.post("/login")
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    from app.models import User

    user = db.query(User).filter_by(username=username).first()
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Usuario o contraseña incorrectos"},
            status_code=401,
        )
    response = RedirectResponse(url="/chat", status_code=303)
    create_session(response, username)
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    delete_session(response)
    return response
