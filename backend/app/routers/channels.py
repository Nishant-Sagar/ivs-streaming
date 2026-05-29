from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List
from botocore.exceptions import ClientError

from ..database import get_db
from ..models.user import User
from ..models.channel import Channel
from ..schemas.channel import (
    ChannelCreate, ChannelUpdate, ChannelResponse,
    ChannelStreamKey, ChatTokenResponse,
)
from ..core.security import get_current_user
from ..core.exceptions import NotFoundError, ConflictError, ForbiddenError, AWSError
from ..services.ivs import ivs_service
from ..services.chat import ivs_chat_service
from ..config import settings

router = APIRouter(prefix="/api/channels", tags=["channels"])


@router.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
def create_channel(
    channel_data: ChannelCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if db.query(Channel).filter(Channel.owner_id == current_user.id).first():
        raise ConflictError("You already have a channel. Delete it first to create a new one.")

    try:
        ivs_data = ivs_service.create_channel(name=f"{current_user.username}-{channel_data.name}")
        chat_data = ivs_chat_service.create_room(name=f"chat-{current_user.username}")
    except ClientError as e:
        raise AWSError(f"Failed to create IVS resources: {e.response['Error']['Message']}")
    except Exception as e:
        raise AWSError(f"Failed to create IVS resources: {e}")

    channel = Channel(
        owner_id=current_user.id,
        name=channel_data.name,
        description=channel_data.description,
        ivs_channel_arn=ivs_data["channel_arn"],
        ivs_stream_key_arn=ivs_data["stream_key_arn"],
        ivs_stream_key_value=ivs_data["stream_key_value"],
        ivs_ingest_endpoint=ivs_data["ingest_endpoint"],
        ivs_playback_url=ivs_data["playback_url"],
        ivs_chat_room_arn=chat_data["room_arn"],
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


@router.get("", response_model=List[ChannelResponse])
def list_channels(db: Session = Depends(get_db)):
    return db.query(Channel).all()


@router.get("/live", response_model=List[ChannelResponse])
def list_live_channels(db: Session = Depends(get_db)):
    return db.query(Channel).filter(Channel.is_live == True).all()  # noqa: E712


@router.get("/mine", response_model=ChannelResponse)
def get_my_channel(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    channel = db.query(Channel).filter(Channel.owner_id == current_user.id).first()
    if not channel:
        raise NotFoundError("You don't have a channel yet")
    return channel


@router.get("/{channel_id}", response_model=ChannelResponse)
def get_channel(channel_id: int, db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise NotFoundError("Channel not found")
    return channel


@router.patch("/{channel_id}", response_model=ChannelResponse)
def update_channel(
    channel_id: int,
    channel_data: ChannelUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise NotFoundError("Channel not found")
    if channel.owner_id != current_user.id:
        raise ForbiddenError()

    if channel_data.name is not None:
        channel.name = channel_data.name
    if channel_data.description is not None:
        channel.description = channel_data.description

    db.commit()
    db.refresh(channel)
    return channel


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(
    channel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise NotFoundError("Channel not found")
    if channel.owner_id != current_user.id:
        raise ForbiddenError()

    try:
        if channel.ivs_channel_arn:
            ivs_service.delete_channel(channel.ivs_channel_arn)
        if channel.ivs_chat_room_arn:
            ivs_chat_service.delete_room(channel.ivs_chat_room_arn)
    except ClientError:
        pass  # Best-effort AWS cleanup

    db.delete(channel)
    db.commit()


@router.get("/{channel_id}/stream-key", response_model=ChannelStreamKey)
def get_stream_key(
    channel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise NotFoundError("Channel not found")
    if channel.owner_id != current_user.id:
        raise ForbiddenError()

    return {
        "stream_key": channel.ivs_stream_key_value,
        "ingest_endpoint": channel.ivs_ingest_endpoint,
        "rtmps_url": f"rtmps://{channel.ivs_ingest_endpoint}:443/app/",
    }


@router.post("/{channel_id}/rotate-key", response_model=ChannelStreamKey)
def rotate_stream_key(
    channel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise NotFoundError("Channel not found")
    if channel.owner_id != current_user.id:
        raise ForbiddenError()

    try:
        new_key = ivs_service.rotate_stream_key(channel.ivs_channel_arn)
    except ClientError as e:
        raise AWSError(f"Failed to rotate stream key: {e.response['Error']['Message']}")

    channel.ivs_stream_key_arn = new_key["arn"]
    channel.ivs_stream_key_value = new_key["value"]
    db.commit()

    return {
        "stream_key": channel.ivs_stream_key_value,
        "ingest_endpoint": channel.ivs_ingest_endpoint,
        "rtmps_url": f"rtmps://{channel.ivs_ingest_endpoint}:443/app/",
    }


@router.post("/{channel_id}/chat-token", response_model=ChatTokenResponse)
def get_chat_token(
    channel_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise NotFoundError("Channel not found")
    if not channel.ivs_chat_room_arn:
        raise NotFoundError("Chat room not configured for this channel")

    is_moderator = channel.owner_id == current_user.id
    capabilities = (
        ["SEND_MESSAGE", "DELETE_MESSAGE", "DISCONNECT_USER"] if is_moderator else ["SEND_MESSAGE"]
    )

    try:
        token_data = ivs_chat_service.create_chat_token(
            room_arn=channel.ivs_chat_room_arn,
            user_id=str(current_user.id),
            username=current_user.username,
            capabilities=capabilities,
        )
    except ClientError as e:
        raise AWSError(f"Failed to create chat token: {e.response['Error']['Message']}")

    return {**token_data, "region": settings.aws_region}
