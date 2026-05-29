from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(500), default="")

    # IVS low-latency channel resources
    ivs_channel_arn = Column(String(500), unique=True, nullable=True)
    ivs_stream_key_arn = Column(String(500), nullable=True)
    ivs_stream_key_value = Column(String(500), nullable=True)
    ivs_ingest_endpoint = Column(String(500), nullable=True)  # hostname only
    ivs_playback_url = Column(String(500), nullable=True)

    # IVS Chat room
    ivs_chat_room_arn = Column(String(500), nullable=True)

    is_live = Column(Boolean, default=False)
    viewer_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="channel")
