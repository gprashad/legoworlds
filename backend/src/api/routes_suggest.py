import json
import logging
import base64
import anthropic
from fastapi import APIRouter, Depends, HTTPException
from src.api.auth import get_current_user
from src.supabase_client import get_supabase
from src.config import SUPABASE_STORAGE_BUCKET

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenes/{scene_id}", tags=["suggest"])


@router.post("/suggest-backstory")
async def suggest_backstory(scene_id: str, user: dict = Depends(get_current_user)):
    """Look at uploaded photos and suggest a backstory starting point."""
    sb = get_supabase()
    uid = user["sub"]

    scene = sb.table("scenes").select("*").eq("id", scene_id).eq("user_id", uid).execute()
    if not scene.data:
        raise HTTPException(status_code=404, detail="Scene not found")

    # Get photos from storage
    folder = f"scenes/{scene_id}/input"
    files = sb.storage.from_(SUPABASE_STORAGE_BUCKET).list(folder)

    photos_b64 = []
    for f in files:
        name = f["name"]
        if not name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue
        data = sb.storage.from_(SUPABASE_STORAGE_BUCKET).download(f"{folder}/{name}")
        ext = name.rsplit(".", 1)[-1].lower()
        media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}.get(ext, "image/jpeg")
        photos_b64.append({"data": base64.b64encode(data).decode(), "media_type": media_type})

    if not photos_b64:
        raise HTTPException(status_code=400, detail="No photos uploaded yet")

    # Build prompt
    content = []
    for photo in photos_b64:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": photo["media_type"], "data": photo["data"]},
        })

    content.append({
        "type": "text",
        "text": """Look at these photos of a Lego scene built by a kid.

Write a fun, exciting backstory suggestion in 2-3 sentences that the kid can use as a starting point. Describe what seems to be happening in the scene — who are the characters, what's the conflict or adventure?

Write it in second person as if talking to the builder: "Your scene shows..." or "It looks like..."

Keep it playful and inspiring — this should make the kid excited to build on the idea. Just the backstory text, no JSON or formatting.""",
    })

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        messages=[{"role": "user", "content": content}],
    )

    suggestion = message.content[0].text.strip()
    logger.info(f"[{scene_id}] Backstory suggestion generated")

    return {"suggestion": suggestion}
