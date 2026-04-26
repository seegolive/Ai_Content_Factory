"""Google OAuth authentication routes."""
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db
from app.core.security import (
    build_google_auth_url,
    create_access_token,
    exchange_code_for_tokens,
    get_google_user_info,
)
from app.models.user import User
from app.models.video import YoutubeAccount
from app.schemas.user import UserOut

router = APIRouter()


@router.get("/auth/google/login")
async def google_login():
    """Return Google OAuth authorization URL."""
    state = secrets.token_urlsafe(32)
    url = build_google_auth_url(state=state)
    return {"auth_url": url, "state": state}


@router.get("/auth/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle OAuth callback, create/update user, return JWT."""
    try:
        tokens = await exchange_code_for_tokens(code)
    except Exception as e:
        logger.error(f"Token exchange failed: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth token exchange failed")

    access_token = tokens.get("access_token")
    refresh_token = tokens.get("refresh_token")

    try:
        user_info = await get_google_user_info(access_token)
    except Exception as e:
        logger.error(f"Failed to fetch Google user info: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to get user info")

    google_id = user_info.get("sub")
    email = user_info.get("email")

    # Upsert user
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            google_id=google_id,
            email=email,
            name=user_info.get("name"),
            avatar_url=user_info.get("picture"),
        )
        db.add(user)
        await db.flush()
        logger.info(f"Created new user: {email}")
    else:
        user.name = user_info.get("name", user.name)
        user.avatar_url = user_info.get("picture", user.avatar_url)

    # Upsert YouTube account if we got a refresh token (YouTube scope granted)
    if refresh_token:
        from app.core.config import settings
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials

        try:
            creds = Credentials(token=access_token)
            yt_service = build("youtube", "v3", credentials=creds)
            channels_response = yt_service.channels().list(part="snippet", mine=True).execute()
            if channels_response.get("items"):
                channel = channels_response["items"][0]
                channel_id = channel["id"]
                channel_name = channel["snippet"]["title"]

                result = await db.execute(
                    select(YoutubeAccount).where(
                        YoutubeAccount.user_id == user.id,
                        YoutubeAccount.channel_id == channel_id,
                    )
                )
                yt_account = result.scalar_one_or_none()
                if yt_account is None:
                    yt_account = YoutubeAccount(
                        user_id=user.id,
                        channel_id=channel_id,
                        channel_name=channel_name,
                        access_token=access_token,
                        refresh_token=refresh_token,
                    )
                    db.add(yt_account)
                else:
                    yt_account.access_token = access_token
                    if refresh_token:
                        yt_account.refresh_token = refresh_token
        except Exception as e:
            logger.warning(f"Could not sync YouTube channel: {e}")

    await db.commit()

    jwt_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": jwt_token, "token_type": "bearer"}


@router.get("/auth/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """Return current authenticated user profile."""
    return current_user


@router.post("/auth/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout endpoint (client should discard token; no server-side blacklist in MVP)."""
    return {"message": "Logged out successfully"}
