"""
Streaming provider layer.

- MockProvider  : active now — no AWS needed, works with browser camera via WebRTC.
- IVSProvider   : plug in when you have AWS IVS credentials.

Switch is automatic: if AWS creds are present in .env the IVS provider is used,
otherwise the mock provider handles all requests.
"""

import uuid
import time
from abc import ABC, abstractmethod
from typing import Optional

from config import settings


# ---------------------------------------------------------------------------
# Base contract
# ---------------------------------------------------------------------------

class StreamSession:
    def __init__(
        self,
        session_id: str,
        title: str,
        description: str,
        # ingest (broadcaster side)
        ingest_endpoint: Optional[str],
        stream_key: Optional[str],
        rtmps_url: Optional[str],
        # playback (viewer side)
        playback_url: Optional[str],
        # meta
        provider: str,
        camera_mode: bool = False,
    ):
        self.session_id = session_id
        self.title = title
        self.description = description
        self.ingest_endpoint = ingest_endpoint
        self.stream_key = stream_key
        self.rtmps_url = rtmps_url
        self.playback_url = playback_url
        self.provider = provider
        self.camera_mode = camera_mode
        self.is_live = False
        self.viewer_count = 0
        self.started_at = time.time()


class BaseProvider(ABC):
    @abstractmethod
    def start_stream(self, title: str, description: str) -> StreamSession:
        ...

    @abstractmethod
    def get_status(self, session_id: str) -> Optional[StreamSession]:
        ...

    @abstractmethod
    def stop_stream(self, session_id: str) -> bool:
        ...


# ---------------------------------------------------------------------------
# Mock provider  (camera mode — fully active, no AWS required)
# ---------------------------------------------------------------------------

class MockProvider(BaseProvider):
    """
    Simulates a streaming session backed by the browser camera (WebRTC).

    The response includes everything the IVS Web Broadcast SDK or a simple
    getUserMedia() loop needs so the frontend can start streaming immediately.
    When you add real IVS credentials, swap this for IVSProvider below.
    """

    def __init__(self):
        self._sessions: dict[str, StreamSession] = {}

    def start_stream(self, title: str, description: str) -> StreamSession:
        session_id = str(uuid.uuid4())
        session = StreamSession(
            session_id=session_id,
            title=title,
            description=description,
            # These will be replaced by real IVS values once credentials are added.
            ingest_endpoint="mock-ingest.local",
            stream_key=f"sk_mock_{session_id[:8]}",
            rtmps_url=f"rtmps://mock-ingest.local:443/app/sk_mock_{session_id[:8]}",
            playback_url=f"https://mock-playback.local/{session_id}/index.m3u8",
            provider="mock",
            camera_mode=True,
        )
        session.is_live = True
        self._sessions[session_id] = session
        return session

    def get_status(self, session_id: str) -> Optional[StreamSession]:
        return self._sessions.get(session_id)

    def stop_stream(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        session.is_live = False
        return True


# ---------------------------------------------------------------------------
# IVS provider  (plug in when you have AWS credentials)
# ---------------------------------------------------------------------------

class IVSProvider(BaseProvider):
    """
    Real Amazon IVS provider.

    Activated automatically when AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
    are present in the environment / .env file.
    """

    def __init__(self):
        self._sessions: dict[str, StreamSession] = {}
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client(
                "ivs",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
        return self._client

    def start_stream(self, title: str, description: str) -> StreamSession:
        # ------------------------------------------------------------------ #
        # TODO: swap stub with real IVS call once you add AWS credentials.    #
        # The channel is created fresh each session (stateless microservice). #
        # ------------------------------------------------------------------ #
        response = self.client.create_channel(
            name=f"stream-{title[:40].replace(' ', '-')}",
            type="STANDARD",
            latencyMode="LOW",
            authorized=False,
        )
        ch = response["channel"]
        sk = response["streamKey"]

        session_id = str(uuid.uuid4())
        session = StreamSession(
            session_id=session_id,
            title=title,
            description=description,
            ingest_endpoint=ch["ingestEndpoint"],
            stream_key=sk["value"],
            rtmps_url=f"rtmps://{ch['ingestEndpoint']}:443/app/{sk['value']}",
            playback_url=ch["playbackUrl"],
            provider="ivs",
            camera_mode=False,
        )
        # Attach IVS ARNs so we can clean up later
        session._ivs_channel_arn = ch["arn"]
        session._ivs_stream_key_arn = sk["arn"]

        session.is_live = True
        self._sessions[session_id] = session
        return session

    def get_status(self, session_id: str) -> Optional[StreamSession]:
        session = self._sessions.get(session_id)
        if not session:
            return None
        try:
            from botocore.exceptions import ClientError
            resp = self.client.get_stream(channelArn=session._ivs_channel_arn)
            s = resp["stream"]
            session.is_live = True
            session.viewer_count = s.get("viewerCount", 0)
        except Exception:
            session.is_live = False
        return session

    def stop_stream(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        try:
            self.client.stop_stream(channelArn=session._ivs_channel_arn)
        except Exception:
            pass
        session.is_live = False
        return True


# ---------------------------------------------------------------------------
# Active provider — chosen at import time based on config
# ---------------------------------------------------------------------------

def get_provider() -> BaseProvider:
    if settings.ivs_enabled:
        return IVSProvider()
    return MockProvider()


_provider: BaseProvider = get_provider()


def provider() -> BaseProvider:
    return _provider
