from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from botocore.exceptions import ClientError

from ..database import get_db
from ..models.user import User
from ..models.channel import Channel
from ..core.security import get_current_user
from ..core.exceptions import NotFoundError, ForbiddenError, AWSError
from ..services.ivs import ivs_service

router = APIRouter(prefix="/api/streams", tags=["streams"])


@router.get("/{channel_id}/status")
def get_stream_status(channel_id: int, db: Session = Depends(get_db)):
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise NotFoundError("Channel not found")

    if not channel.ivs_channel_arn:
        return {"is_live": False, "viewer_count": 0}

    try:
        stream = ivs_service.get_stream(channel.ivs_channel_arn)
        if stream:
            channel.is_live = True
            channel.viewer_count = stream.get("viewerCount", 0)
            db.commit()
            return {
                "is_live": True,
                "viewer_count": stream.get("viewerCount", 0),
                "health": stream.get("health"),
                "start_time": stream.get("startTime"),
                "playback_url": channel.ivs_playback_url,
            }
    except ClientError:
        pass

    channel.is_live = False
    db.commit()
    return {"is_live": False, "viewer_count": 0, "playback_url": channel.ivs_playback_url}


@router.post("/{channel_id}/stop")
def stop_stream(
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
        ivs_service.stop_stream(channel.ivs_channel_arn)
    except ClientError as e:
        raise AWSError(f"Failed to stop stream: {e.response['Error']['Message']}")

    channel.is_live = False
    channel.viewer_count = 0
    db.commit()
    return {"message": "Stream stopped"}
