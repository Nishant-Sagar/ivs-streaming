from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ChannelCreate(BaseModel):
    name: str
    description: str = ""


class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class ChannelResponse(BaseModel):
    id: int
    owner_id: int
    name: str
    description: str
    ivs_ingest_endpoint: Optional[str]
    ivs_playback_url: Optional[str]
    is_live: bool
    viewer_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ChannelStreamKey(BaseModel):
    stream_key: str
    ingest_endpoint: str   # hostname only — for IVS Web Broadcast SDK
    rtmps_url: str         # full URL — for OBS / mobile RTMP apps


class ChatTokenResponse(BaseModel):
    token: str
    session_expiration_time: str
    token_expiration_time: str
    region: str
