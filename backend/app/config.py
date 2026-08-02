from dataclasses import dataclass
from functools import lru_cache
import os


@dataclass(frozen=True)
class Settings:
    database_url: str
    embedding_dimensions: int
    mock_llm: bool
    aws_region: str
    s3_bucket: str | None
    artifacts_dir: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv("MEMORYGRAPH_DATABASE_URL", "sqlite:///./memorygraph.db"),
        embedding_dimensions=int(os.getenv("MEMORYGRAPH_EMBEDDING_DIMENSIONS", "64")),
        mock_llm=os.getenv("MEMORYGRAPH_MOCK_LLM", "true").lower() == "true",
        aws_region=os.getenv("MEMORYGRAPH_AWS_REGION", "us-east-1"),
        s3_bucket=os.getenv("MEMORYGRAPH_S3_BUCKET") or None,
        artifacts_dir=os.getenv("MEMORYGRAPH_ARTIFACTS_DIR", ".artifacts"),
    )
