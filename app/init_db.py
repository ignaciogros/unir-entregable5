import os
import bcrypt
from app.database import Base, SessionLocal, engine
from app.models import User


def init() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            username = os.getenv("APP_USER", "admin")
            password = os.getenv("APP_PASSWORD", "changeme")
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            db.add(User(username=username, hashed_password=hashed))
            db.commit()
    finally:
        db.close()
