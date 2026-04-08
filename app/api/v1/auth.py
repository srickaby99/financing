from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from fastapi import Depends

from app.core.config import settings
from app.core.security import create_access_token, verify_password
from app.schemas.auth import TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
async def issue_token(form: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """Issue a JWT for internal/admin use.

    In production this should validate against a user store.
    For now it validates against the ADMIN_API_KEY env var.
    """
    if not verify_password(form.password, settings.ADMIN_API_KEY):
        # Simple check — replace with user DB lookup when auth is expanded
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(subject=form.username)
    return TokenResponse(
        access_token=token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
