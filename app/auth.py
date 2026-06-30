import os
import bcrypt
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

SECRET_KEY = os.getenv("SECRET_KEY", "changeme-replace-in-production")
COOKIE_NAME = "session"
SESSION_MAX_AGE = 60 * 60 * 8  # 8 horas

_signer = URLSafeTimedSerializer(SECRET_KEY)

# Rutas accesibles sin sesión
_PUBLIC_PATHS = {"/login", "/health"}


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_session(response, username: str) -> None:
    token = _signer.dumps(username)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
    )


def delete_session(response) -> None:
    response.delete_cookie(key=COOKIE_NAME)


def get_current_user(request: Request) -> str | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        return _signer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in _PUBLIC_PATHS or path.startswith("/static"):
            return await call_next(request)
        if not get_current_user(request):
            return RedirectResponse(url="/login")
        return await call_next(request)
