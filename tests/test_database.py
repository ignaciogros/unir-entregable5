import os
from sqlalchemy import inspect as sa_inspect
from app import init_db
from app.models import User


def test_init_creates_tables(setup_test_db):
    from app.database import engine

    tables = sa_inspect(engine).get_table_names()
    assert "users" in tables
    assert "config" in tables
    assert "uploaded_files" in tables


def test_init_creates_user(db):
    init_db.init()
    user = db.query(User).filter_by(username=os.getenv("APP_USER")).first()
    assert user is not None
    assert user.username == "testuser"


def test_init_is_idempotent(db):
    init_db.init()
    init_db.init()
    assert db.query(User).count() == 1


def test_get_db():
    from app.database import get_db

    gen = get_db()
    session = next(gen)
    assert session is not None
    try:
        next(gen)
    except StopIteration:
        pass
