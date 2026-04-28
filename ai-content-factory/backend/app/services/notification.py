"""Notification service — Telegram and SendGrid."""

import asyncio
import html

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
                await asyncio.sleep(2**attempt)
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
                        headers={
                            "Authorization": f"Bearer {settings.SENDGRID_API_KEY}"
                        },
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
                await asyncio.sleep(2**attempt)
        return False

    async def notify_job_complete(
        self,
        video_title: str,
        clips_count: int,
        user_email: str,
        provider_used: str = "",
        duration: str = "",
    ) -> None:
        """Notify user that pipeline completed."""
        safe_title = html.escape(video_title)
        provider_line = (
            f"\n🤖 AI: <b>{html.escape(provider_used)}</b>" if provider_used else ""
        )
        duration_line = f"\n⏱️ Selesai dalam {html.escape(duration)}" if duration else ""
        message = (
            f"✅ <b>{safe_title}</b>\n"
            f"\n📊 {clips_count} clips siap direview{provider_line}{duration_line}\n"
            f"\n👉 Buka dashboard untuk review"
        )
        await asyncio.gather(
            self.send_telegram(message),
            self.send_email(
                to=user_email,
                subject=f"✅ {clips_count} clips siap direview — {video_title}",
                body=(
                    f"<h2>Processing Complete</h2>"
                    f"<p>Video: <strong>{safe_title}</strong></p>"
                    f"<p>{clips_count} clips siap direview di dashboard kamu.</p>"
                    + (
                        f"<p>🤖 AI Provider: {html.escape(provider_used)}</p>"
                        if provider_used
                        else ""
                    )
                ),
            ),
            return_exceptions=True,
        )

    async def notify_job_error(
        self,
        video_title: str,
        error: str,
        user_email: str,
        stage: str = "",
    ) -> None:
        """Notify user of pipeline failure."""
        safe_title = html.escape(video_title)
        safe_error = html.escape(error[:200])
        stage_line = f"\nStage: <b>{html.escape(stage)}</b>" if stage else ""
        message = (
            f"❌ Error di stage <b>{html.escape(stage) if stage else 'pipeline'}</b>\n"
            f"Video: {safe_title}{stage_line}\n"
            f"Error: {safe_error}\n\n"
            f"Pipeline akan resume dari checkpoint ini."
        )
        await asyncio.gather(
            self.send_telegram(message),
            self.send_email(
                to=user_email,
                subject=f"❌ Processing failed: {safe_title}",
                body=(
                    f"<h2>Processing Failed</h2>"
                    f"<p>Video: <strong>{safe_title}</strong></p>"
                    + (f"<p>Stage: {html.escape(stage)}</p>" if stage else "")
                    + f"<pre>{html.escape(error)}</pre>"
                ),
            ),
            return_exceptions=True,
        )

    async def notify_provider_fallback(
        self,
        from_provider: str,
        to_provider: str,
        reason: str = "",
    ) -> None:
        """Notify when AI provider falls back to next in chain."""
        reason_line = f"\nAlasan: {html.escape(reason)}" if reason else ""
        message = (
            f"⚠️ AI fallback: <b>{html.escape(from_provider)}</b> → <b>{html.escape(to_provider)}</b>"
            f"{reason_line}"
        )
        await self.send_telegram(message)

    async def notify_upload_success(
        self, clip_title: str, platform: str, user_email: str
    ) -> None:
        """Notify on successful platform upload."""
        message = f"🚀 <b>Clip Published!</b>\n\n<i>{clip_title}</i> uploaded to <b>{platform}</b>"
        await self.send_telegram(message)
