"""
Streaming Microservice
======================
Two OpenAPI endpoints for live streaming.

  POST  /api/v1/streams          — start a stream, get broadcast credentials
  GET   /api/v1/streams/{id}     — poll stream status / viewer count

Runs in camera (mock) mode by default — no AWS account needed.
Add AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY to .env to switch to Amazon IVS.

Docs: http://localhost:8001/docs
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import os

from config import settings
from provider import provider

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Streaming Microservice",
    description=(
        "Stateless streaming API with two endpoints.\n\n"
        "**Mode:** `mock` (camera) — set AWS credentials in `.env` to switch to Amazon IVS.\n\n"
        "**Broadcaster flow:** `POST /api/v1/streams` → get `ingest_endpoint` + `stream_key` → "
        "point OBS / IVS Web Broadcast SDK at them.\n\n"
        "**Viewer flow:** `GET /api/v1/streams/{session_id}` → read `playback_url` → "
        "play with Amazon IVS Player or HLS.js."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class StartStreamRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120, example="My First Stream")
    description: str = Field(default="", max_length=500, example="Live coding session")


class StartStreamResponse(BaseModel):
    session_id: str = Field(..., description="Unique ID for this streaming session")
    title: str
    description: str

    # Broadcaster — what to put into OBS / IVS Web Broadcast SDK
    ingest_endpoint: str = Field(
        ...,
        description="RTMPS ingest hostname (IVS Web Broadcast SDK uses this directly)"
    )
    stream_key: str = Field(..., description="Secret stream key — keep this private")
    rtmps_url: str = Field(
        ...,
        description="Full RTMPS URL for OBS / mobile apps: rtmps://<host>:443/app/<key>"
    )

    # Viewer — share this URL or embed it
    playback_url: str = Field(..., description="HLS playback URL for viewers")

    # Meta
    provider: str = Field(..., description="'mock' (camera mode) or 'ivs' (Amazon IVS)")
    camera_mode: bool = Field(
        ...,
        description=(
            "True when running without AWS credentials. "
            "The browser can call getUserMedia() and broadcast via the IVS Web Broadcast SDK "
            "against the ingest endpoint once real credentials are added."
        ),
    )
    is_live: bool
    started_at: float = Field(..., description="Unix timestamp when the session was created")

    model_config = {"from_attributes": True}


class StreamStatusResponse(BaseModel):
    session_id: str
    title: str
    description: str
    is_live: bool
    viewer_count: int
    playback_url: Optional[str]
    provider: str
    camera_mode: bool

    model_config = {"from_attributes": True}


class StopStreamResponse(BaseModel):
    session_id: str
    stopped: bool


# ---------------------------------------------------------------------------
# Endpoint 0 — List active streams
# ---------------------------------------------------------------------------

class StreamSummary(BaseModel):
    session_id: str
    title: str
    is_live: bool
    viewer_count: int
    provider: str
    camera_mode: bool


@app.get(
    "/api/v1/streams",
    response_model=List[StreamSummary],
    summary="List all streaming sessions",
    description="Returns every session that has been started (live and stopped).",
    tags=["streaming"],
)
def list_streams():
    sessions = list(provider()._sessions.values())
    return [
        StreamSummary(
            session_id=s.session_id,
            title=s.title,
            is_live=s.is_live,
            viewer_count=s.viewer_count,
            provider=s.provider,
            camera_mode=s.camera_mode,
        )
        for s in sessions
    ]


# ---------------------------------------------------------------------------
# Endpoint 1 — Start a stream
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/streams",
    response_model=StartStreamResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a streaming session",
    description=(
        "Creates a new streaming session and returns broadcast credentials.\n\n"
        "**Camera / mock mode (no AWS):**\n"
        "- `camera_mode` is `true`\n"
        "- Use the IVS Web Broadcast SDK with `getUserMedia()` to stream from the browser camera.\n"
        "- `ingest_endpoint` and `stream_key` are mock values — replace with real IVS values "
        "once you add AWS credentials.\n\n"
        "**Amazon IVS mode (with AWS credentials in .env):**\n"
        "- A real IVS channel is created on-the-fly.\n"
        "- `ingest_endpoint`, `stream_key`, and `playback_url` are live IVS values.\n"
        "- Point OBS → `rtmps_url`, or use the IVS Web Broadcast SDK → `ingest_endpoint` + `stream_key`."
    ),
    tags=["streaming"],
)
def start_stream(body: StartStreamRequest):
    session = provider().start_stream(title=body.title, description=body.description)
    return StartStreamResponse(
        session_id=session.session_id,
        title=session.title,
        description=session.description,
        ingest_endpoint=session.ingest_endpoint,
        stream_key=session.stream_key,
        rtmps_url=session.rtmps_url,
        playback_url=session.playback_url,
        provider=session.provider,
        camera_mode=session.camera_mode,
        is_live=session.is_live,
        started_at=session.started_at,
    )


# ---------------------------------------------------------------------------
# Endpoint 2 — Get stream status
# ---------------------------------------------------------------------------

@app.get(
    "/api/v1/streams/{session_id}",
    response_model=StreamStatusResponse,
    summary="Get stream status",
    description=(
        "Poll this endpoint to check whether a session is live and how many viewers are watching.\n\n"
        "In **mock mode** the status is read from in-process state (is_live = True after start).\n\n"
        "In **IVS mode** this calls `GetStream` on the IVS API and returns live viewer count and health."
    ),
    tags=["streaming"],
)
def get_stream_status(session_id: str):
    session = provider().get_status(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Stream session not found")
    return StreamStatusResponse(
        session_id=session.session_id,
        title=session.title,
        description=session.description,
        is_live=session.is_live,
        viewer_count=session.viewer_count,
        playback_url=session.playback_url,
        provider=session.provider,
        camera_mode=session.camera_mode,
    )


# ---------------------------------------------------------------------------
# Bonus: Stop a stream  (not counted in the "two" but needed for cleanup)
# ---------------------------------------------------------------------------

@app.delete(
    "/api/v1/streams/{session_id}",
    response_model=StopStreamResponse,
    summary="Stop a streaming session",
    description="Ends the stream. In IVS mode this calls `StopStream` on the AWS API.",
    tags=["streaming"],
)
def stop_stream(session_id: str):
    stopped = provider().stop_stream(session_id)
    if not stopped:
        raise HTTPException(status_code=404, detail="Stream session not found")
    return StopStreamResponse(session_id=session_id, stopped=True)


# ---------------------------------------------------------------------------
# Health / info
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
def health():
    return {
        "status": "ok",
        "streaming_provider": "ivs" if settings.ivs_enabled else "mock",
        "camera_mode": not settings.ivs_enabled,
    }


@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.get("/watch", include_in_schema=False)
def serve_watch():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "watch.html"))


static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
