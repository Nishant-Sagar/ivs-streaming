# IVS Streaming Platform

Live streaming platform built with **Amazon IVS**, **FastAPI**, and vanilla JS. Supports streaming from desktop and mobile browsers via the IVS Web Broadcast SDK, plus any RTMP app (OBS, Larix Broadcaster, etc.).

## Architecture

```
Browser/Mobile              Backend (FastAPI)           AWS
──────────────              ─────────────────           ───
IVS Web Broadcast SDK  ──►  /api/channels               Amazon IVS (Low-Latency)
  (WebRTC → RTMPS)          /api/streams                  - Channel (ingest + playback)
                            /api/auth                     - Stream Key
IVS Player SDK         ◄──  /api/webhooks               Amazon IVS Chat
  (HLS playback)                                           - Chat Room
                                                          - Chat Token
IVS Chat (WebSocket)   ◄──  createChatToken API
  (direct connection)
```

## Folder Structure

```
ivs-streaming/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings (pydantic-settings)
│   │   ├── database.py          # SQLAlchemy setup
│   │   ├── models/              # ORM models (User, Channel)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── routers/             # API route handlers
│   │   │   ├── auth.py          # Register, login, /me
│   │   │   ├── channels.py      # Channel CRUD + stream key + chat token
│   │   │   ├── streams.py       # Stream status + stop
│   │   │   └── webhooks.py      # IVS SNS lifecycle events
│   │   ├── services/
│   │   │   ├── ivs.py           # boto3 IVS wrapper
│   │   │   └── chat.py          # boto3 IVS Chat wrapper
│   │   └── core/
│   │       ├── security.py      # JWT + password hashing
│   │       └── exceptions.py    # HTTP exception classes
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── public/
│   │   ├── index.html           # Browse channels
│   │   ├── watch.html           # Watch stream + chat
│   │   ├── stream.html          # Go live (browser/mobile)
│   │   └── dashboard.html       # Streamer dashboard
│   └── static/
│       ├── css/main.css
│       └── js/
│           ├── api.js           # Backend API client
│           ├── player.js        # IVS Player wrapper
│           ├── broadcaster.js   # IVS Web Broadcast SDK wrapper
│           └── chat.js          # IVS Chat WebSocket client
├── nginx.conf                   # Frontend + API proxy config
├── docker-compose.yml
└── .env.example
```

## Quick Start

### 1. AWS Setup

Create an IAM user with these permissions:
- `AmazonIVSFullAccess`
- `ivschat:CreateRoom`, `ivschat:DeleteRoom`, `ivschat:CreateChatToken`, `ivschat:SendEvent`

### 2. Configure environment

```bash
cp .env.example .env
# Fill in AWS credentials and a random SECRET_KEY
```

### 3a. Run with Docker Compose (recommended)

```bash
docker compose up --build
# Frontend: http://localhost:8080
# API docs: http://localhost:8000/api/docs
```

### 3b. Run locally

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in values
uvicorn app.main:app --reload --port 8000

# Serve frontend separately
cd ../frontend
python -m http.server 8080
```

## Streaming Methods

### From browser (desktop + mobile)
1. Log in → Dashboard → **Go Live**
2. Allow camera/microphone access
3. Click "Start Camera" to preview
4. Click "Go Live" to broadcast

> On mobile, the portrait layout is used automatically. Use the flip button to switch between front/back camera.

### From OBS Studio
1. Settings → Stream → Custom
2. **Server**: the RTMPS URL from your dashboard
3. **Stream Key**: from your dashboard

### From mobile RTMP apps (Larix Broadcaster, etc.)
Use the **RTMPS URL** + **Stream Key** from your dashboard in any RTMP streaming app.

## API Reference

Interactive docs: `http://localhost:8000/api/docs`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | — | Create account |
| POST | `/api/auth/login` | — | Login (returns JWT) |
| GET | `/api/auth/me` | ✓ | Current user |
| GET | `/api/channels` | — | List all channels |
| GET | `/api/channels/live` | — | List live channels |
| POST | `/api/channels` | ✓ | Create channel (provisions IVS) |
| GET | `/api/channels/mine` | ✓ | Your channel |
| GET | `/api/channels/{id}/stream-key` | ✓ | Get stream key |
| POST | `/api/channels/{id}/rotate-key` | ✓ | Rotate stream key |
| POST | `/api/channels/{id}/chat-token` | ✓ | Get IVS Chat token |
| GET | `/api/streams/{id}/status` | — | Check if live |
| POST | `/api/streams/{id}/stop` | ✓ | Stop stream |
| POST | `/api/webhooks/ivs` | — | IVS SNS events |

## Webhooks (optional but recommended)

IVS can notify your backend when streams start/end via SNS. Set up an SNS topic → subscribe with `POST https://yourdomain.com/api/webhooks/ivs`.

In AWS Console: IVS → Notifications → Create SNS subscription.

## Production Checklist

- [ ] Replace SQLite with PostgreSQL (`DATABASE_URL=postgresql+psycopg2://...`)
- [ ] Set a strong `SECRET_KEY`
- [ ] Use HTTPS (required for camera access on mobile)
- [ ] Configure SNS webhooks for accurate live status
- [ ] Set up CloudFront in front of IVS playback URLs for lower latency
- [ ] Add rate limiting (e.g., slowapi) to the API
