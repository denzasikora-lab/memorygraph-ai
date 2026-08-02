import os
from pathlib import Path

TEST_DB = Path(__file__).parent / "memorygraph-test.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["MEMORYGRAPH_DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["MEMORYGRAPH_ARTIFACTS_DIR"] = str(Path(__file__).parent / ".artifacts")
