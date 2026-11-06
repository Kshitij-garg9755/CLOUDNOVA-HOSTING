import os
os.environ["DATABASE_URL"]="sqlite:///./test_cloudnova.db"
os.environ["SECRET_KEY"]="test-secret-key-that-is-long-enough"
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import Base,engine
import pytest
@pytest.fixture(autouse=True)
def db_reset():
    Base.metadata.drop_all(engine);Base.metadata.create_all(engine);yield;Base.metadata.drop_all(engine)
@pytest.fixture
def client():
    with TestClient(app) as c:yield c
