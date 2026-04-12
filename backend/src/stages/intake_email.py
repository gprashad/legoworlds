"""
Email intake: poll a Gmail inbox via IMAP, extract photos → create scenes.

Setup:
1. Create a Gmail address for intake (e.g. scenes.legoworlds@gmail.com)
2. Enable 2FA on that Google account
3. Create an App Password: Google Account → Security → App Passwords
4. Set INTAKE_EMAIL_ADDRESS and INTAKE_EMAIL_APP_PASSWORD in env vars

How it works:
- Polls for unread emails every N minutes (called by scheduler or cron)
- Subject line → scene title
- Body text → backstory
- Attachments (images) → uploaded to Supabase Storage, registered as scene_media
- Sends a reply with link to the scene in the web app
- Marks email as read
"""

import os
import logging
import imaplib
import email
import smtplib
from email.mime.text import MIMEText
from email.header import decode_header
from src.supabase_client import get_supabase
from src.config import SUPABASE_STORAGE_BUCKET
from src.api.auth import DEV_USER_ID

logger = logging.getLogger(__name__)

IMAP_SERVER = "imap.gmail.com"
SMTP_SERVER = "smtp.gmail.com"
INTAKE_EMAIL = os.getenv("INTAKE_EMAIL_ADDRESS", "")
INTAKE_PASSWORD = os.getenv("INTAKE_EMAIL_APP_PASSWORD", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://legoworlds.netlify.app")

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".webm", ".m4v"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS
MAX_ATTACHMENT_SIZE = 50 * 1024 * 1024  # 50MB


def _decode_header_value(value: str) -> str:
    """Decode email header value (handles encoded subjects)."""
    decoded_parts = decode_header(value)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def _get_text_body(msg: email.message.Message) -> str:
    """Extract plain text body from email."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain" and "attachment" not in str(part.get("Content-Disposition", "")):
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace").strip()
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace").strip()
    return ""


def _get_media_attachments(msg: email.message.Message) -> list[dict]:
    """Extract image and video attachments from email."""
    attachments = []
    for part in msg.walk():
        content_type = part.get_content_type()
        disposition = str(part.get("Content-Disposition", ""))

        if not (content_type.startswith("image/") or content_type.startswith("video/")):
            continue

        filename = part.get_filename()
        if filename:
            filename = _decode_header_value(filename)
        else:
            ext = content_type.split("/")[-1]
            filename = f"photo.{ext}"

        # Check extension
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue

        data = part.get_payload(decode=True)
        if data and len(data) <= MAX_ATTACHMENT_SIZE:
            file_type = "video" if content_type.startswith("video/") else "photo"
            attachments.append({
                "filename": filename,
                "content_type": content_type,
                "data": data,
                "file_type": file_type,
            })

    return attachments


def _send_reply(to_addr: str, scene_title: str, scene_id: str, photo_count: int):
    """Send a confirmation reply with link to the scene."""
    scene_url = f"{FRONTEND_URL}/scenes/{scene_id}"

    body = f"""Your Lego scene "{scene_title}" has been received!

We got {photo_count} photo{"s" if photo_count != 1 else ""}.

Open your scene in Lego Worlds to add a backstory and make your movie:
{scene_url}

— Lego Worlds"""

    msg = MIMEText(body)
    msg["Subject"] = f"Re: {scene_title} — Scene received!"
    msg["From"] = INTAKE_EMAIL
    msg["To"] = to_addr

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, 465) as smtp:
            smtp.login(INTAKE_EMAIL, INTAKE_PASSWORD)
            smtp.send_message(msg)
        logger.info(f"Reply sent to {to_addr}")
    except Exception as e:
        logger.error(f"Failed to send reply to {to_addr}: {e}")


async def poll_inbox() -> int:
    """
    Poll Gmail inbox for unread emails, create scenes from them.
    Returns number of scenes created.
    """
    if not INTAKE_EMAIL or not INTAKE_PASSWORD:
        logger.warning("Email intake not configured (INTAKE_EMAIL_ADDRESS / INTAKE_EMAIL_APP_PASSWORD)")
        return 0

    sb = get_supabase()
    scenes_created = 0

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(INTAKE_EMAIL, INTAKE_PASSWORD)
        mail.select("INBOX")

        # Search for unread emails
        _, message_ids = mail.search(None, "UNSEEN")
        if not message_ids[0]:
            logger.info("No new emails")
            mail.logout()
            return 0

        ids = message_ids[0].split()
        logger.info(f"Found {len(ids)} unread emails")

        for msg_id in ids:
            try:
                _, msg_data = mail.fetch(msg_id, "(RFC822)")
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                from_addr = email.utils.parseaddr(msg["From"])[1]
                subject = _decode_header_value(msg.get("Subject", "Untitled Scene"))
                body = _get_text_body(msg)
                attachments = _get_media_attachments(msg)

                if not attachments:
                    logger.info(f"Skipping email from {from_addr}: no media attachments")
                    # Mark as read anyway
                    mail.store(msg_id, "+FLAGS", "\\Seen")
                    continue

                # Create scene
                scene_result = sb.table("scenes").insert({
                    "user_id": DEV_USER_ID,  # TODO: map email → user when auth is live
                    "title": subject[:200],
                    "backstory": body[:5000] if body else None,
                }).execute()
                scene = scene_result.data[0]
                scene_id = scene["id"]

                # Upload attachments to Storage + register as media
                for i, att in enumerate(attachments):
                    ext = os.path.splitext(att["filename"])[1] or ".jpg"
                    storage_path = f"scenes/{scene_id}/input/{i + 1}_{att['filename']}"

                    sb.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
                        storage_path, att["data"],
                        {"content-type": att["content_type"]}
                    )

                    public_url = sb.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(storage_path)

                    sb.table("scene_media").insert({
                        "scene_id": scene_id,
                        "file_url": public_url,
                        "file_type": att["file_type"],
                        "file_name": att["filename"],
                        "file_size_bytes": len(att["data"]),
                        "sort_order": i,
                        "source": "email",
                    }).execute()

                photo_count = sum(1 for a in attachments if a["file_type"] == "photo")
                video_count = sum(1 for a in attachments if a["file_type"] == "video")
                logger.info(f"Created scene '{subject}' from email ({photo_count} photos, {video_count} videos)")

                # Send reply
                _send_reply(from_addr, subject, scene_id, photo_count + video_count)

                # Mark as read
                mail.store(msg_id, "+FLAGS", "\\Seen")
                scenes_created += 1

            except Exception as e:
                logger.error(f"Failed to process email {msg_id}: {e}")
                continue

        mail.logout()

    except Exception as e:
        logger.error(f"Email intake error: {e}")

    return scenes_created
