import os
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Config, UploadedFile as UploadedFileModel
import app.vector_store as vs

UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "uploads"))
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="app/templates")


def _error(request: Request, db: Session, message: str):
    files = db.query(UploadedFileModel).order_by(UploadedFileModel.uploaded_at.desc()).all()
    return templates.TemplateResponse(
        request, "admin.html", {"files": files, "error": message, "processing": False, "has_previous": False}, status_code=400
    )


@router.get("")
def admin_page(request: Request, db: Session = Depends(get_db)):
    from app import ingest
    files = db.query(UploadedFileModel).order_by(UploadedFileModel.uploaded_at.desc()).all()
    has_previous = db.query(Config).filter_by(key="previous_collection").first() is not None
    return templates.TemplateResponse(request, "admin.html", {
        "files": files,
        "processing": ingest.is_processing(),
        "has_previous": has_previous,
    })


@router.post("/upload")
async def upload_pdf(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".pdf"):
        return _error(request, db, "Solo se permiten ficheros PDF (.pdf)")

    content = await file.read()

    if not content.startswith(b"%PDF"):
        return _error(request, db, "El fichero no es un PDF válido")

    if len(content) > MAX_FILE_SIZE:
        return _error(request, db, "El fichero supera el límite de 20 MB")

    UPLOADS_DIR.mkdir(exist_ok=True)
    (UPLOADS_DIR / file.filename).write_bytes(content)

    existing = db.query(UploadedFileModel).filter_by(filename=file.filename).first()
    if existing:
        existing.size_bytes = len(content)
        existing.processed = False
    else:
        db.add(UploadedFileModel(filename=file.filename, size_bytes=len(content)))
    db.commit()

    return RedirectResponse(url="/admin", status_code=303)


@router.post("/delete/{filename}")
def delete_pdf(filename: str, db: Session = Depends(get_db)):
    path = UPLOADS_DIR / filename
    if path.exists():
        path.unlink()

    collection = vs.get_active_collection(db)
    if collection:
        try:
            vs.delete_by_source(collection, filename)
        except Exception:
            pass

    db.query(UploadedFileModel).filter_by(filename=filename).delete()
    db.commit()

    return RedirectResponse(url="/admin", status_code=303)


@router.post("/process")
def process_pdfs(background_tasks: BackgroundTasks):
    from app import ingest
    from app.database import SessionLocal

    def _run():
        db = SessionLocal()
        try:
            ingest.process_all_pdfs(db)
        finally:
            db.close()

    background_tasks.add_task(_run)
    return RedirectResponse(url="/admin", status_code=303)


@router.get("/status")
def admin_status(db: Session = Depends(get_db)):
    from app import ingest
    collection = vs.get_active_collection(db)
    total = 0
    if collection:
        try:
            total = vs.get_total_vectors(collection)
        except Exception:
            pass
    return {
        "processing": ingest.is_processing(),
        "active_collection": collection,
        "total_vectors": total,
    }


@router.post("/restore")
def restore_collection(db: Session = Depends(get_db)):
    vs.restore_collection(db)
    return RedirectResponse(url="/admin", status_code=303)
