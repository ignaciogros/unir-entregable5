import os

# Fijar ANTES de cualquier import de app para que el engine use SQLite
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["APP_USER"] = "testuser"
os.environ["APP_PASSWORD"] = "testpass123"
os.environ["SECRET_KEY"] = "test-secret-key-xxxxxxxxxxxxxxxxxx"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    from app.database import Base, engine
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db(setup_test_db):
    from app.database import SessionLocal
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)
