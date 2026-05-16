from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from core.config import get_env, get_settings

security = HTTPBasic(auto_error=False)


async def optional_basic_auth(
    credentials: Annotated[HTTPBasicCredentials | None, Security(security)],
) -> None:
    settings = get_settings()
    if not settings.app.optional_basic_auth:
        return
    env = get_env()
    if not env.app_password:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="APP_PASSWORD required when basic auth is enabled",
        )
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    user_ok = secrets.compare_digest(credentials.username.encode(), b"admin")
    pass_ok = secrets.compare_digest(credentials.password.encode(), env.app_password.encode())
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
