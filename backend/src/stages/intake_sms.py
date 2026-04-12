"""
SMS/MMS intake via Twilio webhook.

Setup:
1. Sign up at twilio.com, get a phone number with MMS capability
2. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER in env vars
3. In Twilio console, set the messaging webhook URL to:
   https://legoworlds-api-production.up.railway.app/api/intake/sms
4. Method: POST

How it works:
- Kid texts photos to the Twilio number
- Twilio sends webhook with MMS media URLs + message body
- We download the media, create a scene, upload to Supabase Storage
- Reply via Twilio with a link to the scene in the web app
"""

import os
import logging
import httpx
from src.supabase_client import get_supabase
from src.config import SUPABASE_STORAGE_BUCKET
from src.api.auth import DEV_USER_ID
from src.stages.video_intake import process_video_intake

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://legoworlds.ai")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm", "video/x-m4v"}
ALLOWED_CONTENT_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_VIDEO_TYPES


async def process_incoming_sms(form_data: dict) -> dict:
    """
    Process an incoming Twilio SMS/MMS webhook.

    form_data contains Twilio's POST parameters:
    - From: sender phone number
    - Body: message text
    - NumMedia: number of media attachments
    - MediaUrl0, MediaContentType0, etc.

    Returns dict with scene_id and reply message.
    """
    from_number = form_data.get("From", "")
    body = form_data.get("Body", "").strip()
    num_media = int(form_data.get("NumMedia", "0"))

    logger.info(f"SMS from {from_number}: '{body[:50]}' with {num_media} media")

    if num_media == 0:
        return {
            "reply": "Hey! Send me some photos of your Lego build and I'll turn it into a movie. Just text photos to this number!",
            "scene_id": None,
        }

    sb = get_supabase()

    # Create scene
    title = body[:100] if body else "Texted Scene"
    backstory = body if len(body) > 20 else None

    scene_result = sb.table("scenes").insert({
        "user_id": DEV_USER_ID,  # TODO: map phone → user when auth is live
        "title": title,
        "backstory": backstory,
    }).execute()
    scene = scene_result.data[0]
    scene_id = scene["id"]

    # Download and upload each media attachment
    photo_count = 0
    async with httpx.AsyncClient(timeout=60) as client:
        for i in range(num_media):
            media_url = form_data.get(f"MediaUrl{i}")
            content_type = form_data.get(f"MediaContentType{i}", "")

            if not media_url or content_type not in ALLOWED_CONTENT_TYPES:
                logger.info(f"Skipping media {i}: type={content_type}")
                continue

            # Download from Twilio (requires auth)
            res = await client.get(
                media_url,
                auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                follow_redirects=True,
            )
            if res.status_code != 200:
                logger.error(f"Failed to download media {i}: {res.status_code}")
                continue

            data = res.content
            is_video = content_type.startswith("video/")
            file_type = "video" if is_video else "photo"
            ext = content_type.split("/")[-1]
            if ext == "jpeg":
                ext = "jpg"
            if ext == "quicktime":
                ext = "mov"
            filename = f"{file_type}_{i + 1}.{ext}"
            storage_path = f"scenes/{scene_id}/input/{filename}"

            sb.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
                storage_path, data, {"content-type": content_type}
            )

            public_url = sb.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(storage_path)

            sb.table("scene_media").insert({
                "scene_id": scene_id,
                "file_url": public_url,
                "file_type": file_type,
                "file_name": filename,
                "file_size_bytes": len(data),
                "sort_order": i,
                "source": "sms",
            }).execute()

            photo_count += 1

            # Auto-process videos
            if is_video:
                try:
                    await process_video_intake(scene_id, storage_path)
                except Exception as e:
                    logger.warning(f"Video processing failed for SMS: {e}")

    if photo_count == 0:
        # Clean up empty scene
        sb.table("scenes").delete().eq("id", scene_id).execute()
        return {
            "reply": "I couldn't find any photos in your message. Try sending some Lego photos!",
            "scene_id": None,
        }

    scene_url = f"{FRONTEND_URL}/scenes/{scene_id}"

    logger.info(f"Created scene '{title}' from SMS ({photo_count} photos)")

    return {
        "reply": f"Got {photo_count} photo{'s' if photo_count != 1 else ''}! Open your scene: {scene_url}",
        "scene_id": scene_id,
    }
