import os
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .database import Base, engine, get_db
from .models import User, StoredFile
from .security import hash_password, verify_password, SESSION_SECRET

STORAGE_DIR = Path(os.getenv("STORAGE_DIR", "storage")).resolve()
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title="CloudNest API", description="A self-hosted cloud file storage portfolio project", version="1.0.0", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, same_site="lax", https_only=os.getenv("COOKIE_HTTPS_ONLY", "false").lower() == "true")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

def current_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)

def require_user(request: Request, db: Session) -> User:
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Please log in.")
    return user

def safe_display_name(name: str) -> str:
    # Keep only the filename, remove control characters, and cap its length.
    cleaned = Path(name.replace("\\", "/")).name
    cleaned = "".join(ch for ch in cleaned if ch.isprintable()).strip()
    return (cleaned or "download")[:255]

@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    if current_user(request, db):
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": None})

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"error": None})

@app.post("/register", response_class=HTMLResponse)
def register(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    username = username.strip()
    if len(username) < 3 or len(username) > 50:
        return templates.TemplateResponse(request, "register.html", {"error": "Username must be 3–50 characters."}, status_code=400)
    if len(password) < 8:
        return templates.TemplateResponse(request, "register.html", {"error": "Password must be at least 8 characters."}, status_code=400)
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        return templates.TemplateResponse(request, "register.html", {"error": "That username is already taken."}, status_code=409)
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/login", response_class=HTMLResponse)
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == username.strip()))
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(request, "login.html", {"error": "Invalid username or password."}, status_code=401)
    request.session.clear()
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/", status_code=303)
    files = db.scalars(select(StoredFile).where(StoredFile.owner_id == user.id).order_by(StoredFile.uploaded_at.desc())).all()
    total_bytes = sum(item.size_bytes for item in files)
    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user, "files": files, "total_bytes": total_bytes,
        "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024), "error": None
    })

@app.post("/files/upload")
async def upload_file(request: Request, upload: UploadFile = File(...), db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/", status_code=303)
    original_name = safe_display_name(upload.filename or "upload")
    storage_name = f"{uuid.uuid4().hex}_{original_name}"
    user_dir = STORAGE_DIR / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    target = user_dir / storage_name
    size = 0
    try:
        with target.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024*1024)} MB limit.")
                output.write(chunk)
        record = StoredFile(
            owner_id=user.id, original_name=original_name, storage_name=storage_name,
            content_type=upload.content_type or "application/octet-stream", size_bytes=size
        )
        db.add(record)
        db.commit()
    except Exception:
        db.rollback()
        target.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/files/{file_id}/download")
def download_file(file_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/", status_code=303)
    record = db.scalar(select(StoredFile).where(StoredFile.id == file_id, StoredFile.owner_id == user.id))
    if not record:
        raise HTTPException(status_code=404, detail="File not found.")
    path = (STORAGE_DIR / str(user.id) / record.storage_name).resolve()
    if not path.is_relative_to(STORAGE_DIR) or not path.is_file():
        raise HTTPException(status_code=404, detail="Stored file is missing.")
    return FileResponse(path, filename=record.original_name, media_type="application/octet-stream")

@app.post("/files/{file_id}/delete")
def delete_file(file_id: int, request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse("/", status_code=303)
    record = db.scalar(select(StoredFile).where(StoredFile.id == file_id, StoredFile.owner_id == user.id))
    if not record:
        raise HTTPException(status_code=404, detail="File not found.")
    path = STORAGE_DIR / str(user.id) / record.storage_name
    path.unlink(missing_ok=True)
    db.delete(record)
    db.commit()
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/health")
def health():
    return {"status": "ok", "service": "CloudNest"}

@app.get("/api/files")
def list_files(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Please log in.")
    files = db.scalars(select(StoredFile).where(StoredFile.owner_id == user.id).order_by(StoredFile.uploaded_at.desc())).all()
    return [{"id": f.id, "name": f.original_name, "size_bytes": f.size_bytes, "content_type": f.content_type, "uploaded_at": f.uploaded_at.isoformat()} for f in files]
