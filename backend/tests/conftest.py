import os
import sys
import tempfile

os.environ["BUZZ_RATE_LIMIT_DISABLED"] = "1"
os.environ["BUZZ_DISABLE_WORKER"] = "1"
_tmpdb = os.path.join(tempfile.mkdtemp(prefix="buzz-test-"), "test.db")
os.environ["BUZZ_DB_URL"] = f"sqlite:///{_tmpdb}"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app import seed


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    seed.seed()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


ADMIN = {"X-Admin-Token": "dev-admin"}
