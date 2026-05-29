import json
import urllib.request
from fastapi import APIRouter, Request, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.channel import Channel

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/ivs")
async def ivs_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receives IVS stream lifecycle events via Amazon SNS / EventBridge.
    Configure this URL as an SNS subscription endpoint in AWS.
    """
    body = await request.body()
    data = json.loads(body)
    msg_type = data.get("Type", "")

    # Confirm the SNS subscription on first delivery
    if msg_type == "SubscriptionConfirmation":
        urllib.request.urlopen(data["SubscribeURL"])
        return {"message": "Subscription confirmed"}

    if msg_type == "Notification":
        message = json.loads(data.get("Message", "{}"))
        event_type = message.get("detail-type", "")
        detail = message.get("detail", {})
        channel_arn = detail.get("channel_arn", "")

        channel = db.query(Channel).filter(Channel.ivs_channel_arn == channel_arn).first()
        if channel:
            if event_type == "IVS Stream Start":
                channel.is_live = True
            elif event_type == "IVS Stream End":
                channel.is_live = False
                channel.viewer_count = 0
            elif event_type == "IVS Stream State Change":
                state = detail.get("stream_state", "")
                channel.is_live = state == "Live"
                if not channel.is_live:
                    channel.viewer_count = 0
            db.commit()

    return {"message": "OK"}
