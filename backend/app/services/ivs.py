import boto3
from botocore.exceptions import ClientError
from typing import Optional
from ..config import settings


class IVSService:
    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client(
                "ivs",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
        return self._client

    def create_channel(self, name: str) -> dict:
        response = self.client.create_channel(
            name=name,
            type="STANDARD",
            latencyMode="LOW",
            authorized=False,
        )
        ch = response["channel"]
        sk = response["streamKey"]
        return {
            "channel_arn": ch["arn"],
            "ingest_endpoint": ch["ingestEndpoint"],   # hostname only
            "playback_url": ch["playbackUrl"],
            "stream_key_arn": sk["arn"],
            "stream_key_value": sk["value"],
        }

    def delete_channel(self, channel_arn: str) -> None:
        self.client.delete_channel(arn=channel_arn)

    def get_stream(self, channel_arn: str) -> Optional[dict]:
        try:
            response = self.client.get_stream(channelArn=channel_arn)
            return response["stream"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "ChannelNotBroadcasting":
                return None
            raise

    def stop_stream(self, channel_arn: str) -> None:
        self.client.stop_stream(channelArn=channel_arn)

    def rotate_stream_key(self, channel_arn: str) -> dict:
        response = self.client.create_stream_key(channelArn=channel_arn)
        sk = response["streamKey"]
        return {"arn": sk["arn"], "value": sk["value"]}

    def list_channels(self) -> list:
        response = self.client.list_channels()
        return response.get("channels", [])


ivs_service = IVSService()
