import json
import logging
import base64
from pathlib import Path
import anthropic
from src.supabase_client import get_supabase
from src.config import SUPABASE_STORAGE_BUCKET

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "scene_analysis.txt").read_text()

SCENE_BIBLE_SCHEMA = """{
  "title": "string",
  "genre": "string (action/comedy/drama/adventure/mystery/sci-fi)",
  "mood": "string",
  "setting": {
    "description": "string",
    "locations": [{ "id": "string", "description": "string", "position": "string" }]
  },
  "cast": [{
    "id": "string (snake_case identifier)",
    "description": "string",
    "role": "string (protagonist/antagonist/supporting)",
    "backstory": "string",
    "visual_details": "string"
  }],
  "vehicles": [{
    "id": "string",
    "type": "string",
    "color": "string",
    "operator": "string or null",
    "cargo": "string or null"
  }],
  "props": [{ "id": "string", "description": "string", "location": "string" }],
  "key_conflicts": ["string"]
}"""


async def download_photos_as_base64(scene_id: str) -> list[dict]:
    """Download all photos from Supabase Storage and return as base64 with media types."""
    sb = get_supabase()
    folder = f"scenes/{scene_id}/input"
    files = sb.storage.from_(SUPABASE_STORAGE_BUCKET).list(folder)

    photos = []
    for f in files:
        name = f["name"]
        if not name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            continue

        data = sb.storage.from_(SUPABASE_STORAGE_BUCKET).download(f"{folder}/{name}")

        ext = name.rsplit(".", 1)[-1].lower()
        media_type = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
        }.get(ext, "image/jpeg")

        photos.append({
            "base64": base64.b64encode(data).decode(),
            "media_type": media_type,
            "filename": name,
        })

    logger.info(f"Downloaded {len(photos)} photos for scene {scene_id}")
    return photos


async def analyze_scene(scene_id: str, backstory: str) -> dict:
    """Send photos + backstory to Claude Vision, return scene bible JSON."""
    photos = await download_photos_as_base64(scene_id)
    if not photos:
        raise ValueError(f"No photos found in storage for scene {scene_id}")

    # Build multimodal content
    content = []
    for i, photo in enumerate(photos):
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": photo["media_type"],
                "data": photo["base64"],
            },
        })
        content.append({
            "type": "text",
            "text": f"[Photo {i + 1}: {photo['filename']}]",
        })

    content.append({
        "type": "text",
        "text": f"""Backstory from the builder:
{backstory}

Analyze the photos and backstory above. Create a detailed scene bible as JSON.

Use this exact JSON schema:
{SCENE_BIBLE_SCHEMA}

Return ONLY the JSON object, no markdown fences or explanation.""",
    })

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    response_text = message.content[0].text.strip()

    # Strip markdown fences if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = "\n".join(lines)

    scene_bible = json.loads(response_text)
    logger.info(f"Scene analysis complete: {scene_bible.get('title', 'untitled')}")
    return scene_bible
