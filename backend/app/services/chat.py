import boto3
from ..config import settings


class IVSChatService:
    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client(
                "ivschat",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                endpoint_url=f"https://ivschat.{settings.aws_region.strip()}.amazonaws.com",
            )
        return self._client

    def create_room(self, name: str) -> dict:
        response = self.client.create_room(
            name=name,
            maximumMessageLength=500,
            maximumMessageRatePerSecond=5,
        )
        return {"room_arn": response["arn"]}

    def delete_room(self, room_arn: str) -> None:
        self.client.delete_room(identifier=room_arn)

    def create_chat_token(
        self,
        room_arn: str,
        user_id: str,
        username: str,
        capabilities: list = None,
        session_duration_minutes: int = 180,
    ) -> dict:
        if capabilities is None:
            capabilities = ["SEND_MESSAGE"]

        response = self.client.create_chat_token(
            roomIdentifier=room_arn,
            userId=user_id,
            capabilities=capabilities,
            sessionDurationInMinutes=session_duration_minutes,
            attributes={"username": username},
        )
        return {
            "token": response["token"],
            "session_expiration_time": response["sessionExpirationTime"].isoformat(),
            "token_expiration_time": response["tokenExpirationTime"].isoformat(),
        }

    def send_event(self, room_arn: str, event_name: str, attributes: dict) -> None:
        self.client.send_event(
            roomIdentifier=room_arn,
            eventName=event_name,
            attributes={k: str(v) for k, v in attributes.items()},
        )


ivs_chat_service = IVSChatService()
