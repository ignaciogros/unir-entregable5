import os
import tempfile

# Fijar ANTES de cualquier import de app para que el engine use SQLite
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["APP_USER"] = "testuser"
os.environ["APP_PASSWORD"] = "testpass123"
os.environ["SECRET_KEY"] = "test-secret-key-xxxxxxxxxxxxxxxxxx"
os.environ["UPLOADS_DIR"] = tempfile.mkdtemp()

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _make_test_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # todas las conexiones comparten la misma DB en memoria
    )


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    import app.models  # noqa: F401  (registra los modelos en Base antes de create_all)
    import app.database as db_mod
    import app.init_db as init_mod

    test_engine = _make_test_engine()
    TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    # Parchar los módulos para que usen el engine de test
    db_mod.engine = test_engine
    db_mod.SessionLocal = TestSessionLocal
    init_mod.engine = test_engine
    init_mod.SessionLocal = TestSessionLocal

    db_mod.Base.metadata.create_all(bind=test_engine)
    yield test_engine
    db_mod.Base.metadata.drop_all(bind=test_engine)


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
    from fastapi.testclient import TestClient
    return TestClient(app)
