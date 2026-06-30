from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import RedirectResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app import init_db
    init_db.init()
    yield


app = FastAPI(title="RAG Chatbot", lifespan=lifespan)


@app.get("/")
def root():
    return RedirectResponse(url="/login")


@app.get("/health")
def health():
    return {"status": "ok"}
