from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from .config import Settings


class ArtifactStore:
    def __init__(self, settings: Settings):
        self.settings = settings

    def put_json(self, session_id: str, name: str, payload: dict) -> str:
        key = f"sessions/{session_id}/{uuid4()}-{name}.json"
        body = json.dumps(payload, sort_keys=True, indent=2).encode()
        if self.settings.s3_bucket:
            import boto3
            boto3.client("s3", region_name=self.settings.aws_region).put_object(
                Bucket=self.settings.s3_bucket, Key=key, Body=body, ContentType="application/json"
            )
            return f"s3://{self.settings.s3_bucket}/{key}"
        path = Path(self.settings.artifacts_dir) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return f"file://{path.resolve()}"
