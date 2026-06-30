from fastapi import FastAPI
from fastapi.responses import RedirectResponse

app = FastAPI(title="RAG Chatbot")


@app.get("/")
def root():
    return RedirectResponse(url="/login")


@app.get("/health")
def health():
    return {"status": "ok"}
