from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
import os
import socket

from .config import settings
from .database import engine, Base
from .routers import auth, channels, streams, webhooks

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="IVS Streaming Platform",
    description="Live streaming platform powered by Amazon IVS",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(channels.router)
app.include_router(streams.router)
app.include_router(webhooks.router)

# Serve frontend static files if the directory exists
# Note: directory is named "pages" (not "public") — Vercel excludes "public/" from function bundles
frontend_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.isdir(os.path.join(frontend_path, "static")):
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_path, "static")), name="static")

if os.path.isdir(os.path.join(frontend_path, "pages")):
    app.mount("/app", StaticFiles(directory=os.path.join(frontend_path, "pages")), name="frontend")


@app.get("/api/local-ip")
def get_local_ip(request: Request):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    scheme = request.url.scheme
    port = request.url.port or (443 if scheme == "https" else 8000)
    return {"ip": ip, "port": port, "scheme": scheme}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/")
def root():
    return RedirectResponse(url="/app/index.html")
