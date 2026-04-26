"""Notification service — Telegram and SendGrid."""
import asyncio
import html
from typing import Optional

import httpx
from loguru import logger

from app.core.config import settings


class NotificationService:

    async def send_telegram(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send Telegram message with 3 retries."""
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_CHAT_ID:
            logger.debug("Telegram not configured, skipping notification")
            return False

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(
                        url,
                        json={
                            "chat_id": settings.TELEGRAM_CHAT_ID,
                            "text": message,
                            "parse_mode": parse_mode,
                        },
                    )
                    resp.raise_for_status()
                    return True
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Telegram notification failed after 3 attempts: {e}")
                    return False
                await asyncio.sleep(2 ** attempt)
        return False

    async def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send HTML email via SendGrid with 3 retries."""
        if not settings.SENDGRID_API_KEY:
            logger.debug("SendGrid not configured, skipping email")
            return False

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(
                        "https://api.sendgrid.com/v3/mail/send",
                        headers={"Authorization": f"Bearer {settings.SENDGRID_API_KEY}"},
                        json={
                            "personalizations": [{"to": [{"email": to}]}],
                            "from": {"email": settings.FROM_EMAIL},
                            "subject": subject,
                            "content": [{"type": "text/html", "value": body}],
                        },
                    )
                    resp.raise_for_status()
                    return True
            except Exception as e:
                if attempt == 2:
                    logger.error(f"Email notification failed after 3 attempts: {e}")
                    return False
                await asyncio.sleep(2 ** attempt)
        return False

    async def notify_job_complete(self, video_title: str, clips_count: int, user_email: str) -> None:
        """Notify user that pipeline completed."""
        safe_title = html.escape(video_title)
        message = (
            f"✅ <b>Processing Complete!</b>\n\n"
            f"Video: <i>{safe_title}</i>\n"
            f"Clips ready for review: <b>{clips_count}</b>\n\n"
            f"Open your dashboard to review and approve clips."
        )
        await asyncio.gather(
            self.send_telegram(message),
            self.send_email(
                to=user_email,
                subject=f"✅ {clips_count} clips ready for review",
                body=f"<h2>Processing Complete</h2><p>Video: <strong>{safe_title}</strong></p>"
                     f"<p>{clips_count} clips are ready for review in your dashboard.</p>",
            ),
            return_exceptions=True,
        )

    async def notify_job_error(self, video_title: str, error: str, user_email: str) -> None:
        """Notify user of pipeline failure."""
        safe_title = html.escape(video_title)
        safe_error = html.escape(error[:200])
        message = (
            f"❌ <b>Processing Failed</b>\n\n"
            f"Video: <i>{safe_title}</i>\n"
            f"Error: {safe_error}"
        )
        await asyncio.gather(
            self.send_telegram(message),
            self.send_email(
                to=user_email,
                subject=f"❌ Processing failed: {safe_title}",
                body=f"<h2>Processing Failed</h2><p>Video: <strong>{safe_title}</strong></p>"
                     f"<pre>{html.escape(error)}</pre>",
            ),
            return_exceptions=True,
        )

    async def notify_upload_success(self, clip_title: str, platform: str, user_email: str) -> None:
        """Notify on successful platform upload."""
        message = f"🚀 <b>Clip Published!</b>\n\n<i>{clip_title}</i> uploaded to <b>{platform}</b>"
        await self.send_telegram(message)
