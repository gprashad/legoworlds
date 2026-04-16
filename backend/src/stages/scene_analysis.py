import json
import logging
import base64
from pathlib import Path
import anthropic
from src.supabase_client import get_supabase
from src.config import SUPABASE_STORAGE_BUCKET
from src.utils.json_repair import repair_and_parse_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "scene_analysis.txt").read_text()

SCENE_BIBLE_SCHEMA = """{
  "title": "string",
  "genre": "string (action/comedy/drama/adventure/mystery/sci-fi)",
  "mood": "string",
  "setting": {
    "description": "string — detailed spatial layout of the entire scene",
    "locations": [{ "id": "string", "description": "string", "position": "string — relative to other elements" }],
    "spatial_layout": "string — describe depth layers: foreground, midground, background",
    "key_angles": ["string — best camera angles to show the scene"]
  },
  "cast": [{
    "id": "string (snake_case identifier)",
    "description": "string",
    "role": "string (protagonist/antagonist/supporting)",
    "backstory": "string",
    "visual_details": "string — EXACT appearance: clothing colors, hair, accessories, position in scene",
    "personality": "string — if the builder described their personality"
  }],
  "vehicles": [{
    "id": "string",
    "type": "string",
    "color": "string — exact color",
    "operator": "string or null",
    "cargo": "string or null",
    "position": "string — where in the scene"
  }],
  "props": [{ "id": "string", "description": "string", "location": "string" }],
  "key_conflicts": ["string"],
  "story_beats": {
    "setup": "string — what's the situation",
    "conflict": "string — what's the problem/tension",
    "stakes": "string — what happens if the conflict isn't resolved"
  }
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


async def _download_video_as_base64(scene_id: str) -> dict | None:
    """Download the original walkthrough video if it exists."""
    sb = get_supabase()
    folder = f"scenes/{scene_id}/input"
    files = sb.storage.from_(SUPABASE_STORAGE_BUCKET).list(folder)

    for f in files:
        name = f["name"]
        if name.lower().endswith((".mp4", ".mov", ".webm", ".m4v")):
            data = sb.storage.from_(SUPABASE_STORAGE_BUCKET).download(f"{folder}/{name}")
            # Claude Vision has size limits — skip videos over 20MB for base64
            if len(data) > 20 * 1024 * 1024:
                logger.info(f"Video {name} too large for Claude Vision ({len(data)} bytes), using frames only")
                return None
            ext = name.rsplit(".", 1)[-1].lower()
            media_type = {"mp4": "video/mp4", "mov": "video/quicktime", "webm": "video/webm", "m4v": "video/mp4"}.get(ext, "video/mp4")
            logger.info(f"Downloaded video {name} for Claude Vision ({len(data)} bytes)")
            return {"base64": base64.b64encode(data).decode(), "media_type": media_type, "filename": name}

    return None


def _get_video_intelligence(scene_id: str) -> dict | None:
    """Retrieve narration intelligence stored during video intake processing."""
    sb = get_supabase()
    scene = sb.table("scenes").select("scene_bible").eq("id", scene_id).execute().data
    if not scene:
        return None
    bible = scene[0].get("scene_bible")
    if bible and bible.get("_video_intelligence"):
        return bible
    return None


async def analyze_scene(scene_id: str, backstory: str) -> dict:
    """
    Analyze scene using video (if available) + photos + narration intelligence.
    Produces a rich scene bible with spatial layout and character details.
    """
    photos = await download_photos_as_base64(scene_id)
    if not photos:
        raise ValueError(f"No photos found in storage for scene {scene_id}")

    # Pull structured_description (Nolan brief) if available
    sb = get_supabase()
    scene_row = sb.table("scenes").select("structured_description").eq("id", scene_id).execute().data
    structured_description = (scene_row[0].get("structured_description") if scene_row else None) or {}

    # Check for video intelligence from walkthrough processing
    video_intel = _get_video_intelligence(scene_id)
    narration_intel = video_intel.get("_narration_intelligence", {}) if video_intel else {}
    camera_notes = video_intel.get("_camera_notes", []) if video_intel else []
    story_beats = video_intel.get("_story_beats", {}) if video_intel else {}
    character_hints = video_intel.get("_character_hints", []) if video_intel else []

    # Try to get the actual video for Claude Vision
    video = await _download_video_as_base64(scene_id)

    # Build multimodal content
    content = []

    # Video first — Claude watches the full walkthrough (Phase 1)
    if video:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": video["media_type"],
                "data": video["base64"],
            },
        })
        content.append({
            "type": "text",
            "text": "Above: The builder's walkthrough video of their Lego scene. Watch carefully for spatial layout, character positions, and details only visible from certain angles.",
        })

    # Then photos for detail
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

    # Build the analysis prompt with all intelligence
    prompt_parts = []

    # Nolan brief (PRIMARY input — what the builder wants)
    if structured_description:
        prompt_parts.append("BUILDER'S BRIEF (use this to guide your analysis):")
        if structured_description.get("one_liner"):
            prompt_parts.append(f"  Logline: {structured_description['one_liner']}")
        if structured_description.get("characters"):
            prompt_parts.append(f"  Characters: {structured_description['characters']}")
        if structured_description.get("what_happens"):
            prompt_parts.append(f"  Story: {structured_description['what_happens']}")
        if structured_description.get("mood"):
            prompt_parts.append(f"  Mood: {structured_description['mood']}")

    if backstory:
        prompt_parts.append(f"\nAdditional notes:\n{backstory}")

    # Phase 2: Narration intelligence
    if character_hints:
        prompt_parts.append("\nThe builder specifically mentioned these characters in their narration:")
        for ch in character_hints:
            prompt_parts.append(f"  - {ch.get('name', '?')}: {ch.get('description', '')} — personality: {ch.get('personality', 'unknown')} — role: {ch.get('role', 'unknown')}")

    if story_beats:
        prompt_parts.append(f"\nThe builder described this story structure:")
        prompt_parts.append(f"  Setup: {story_beats.get('setup', '?')}")
        prompt_parts.append(f"  Conflict: {story_beats.get('conflict', '?')}")
        prompt_parts.append(f"  Stakes: {story_beats.get('stakes', '?')}")

    # Phase 4: Camera notes from walkthrough
    if camera_notes:
        prompt_parts.append(f"\nFrom the builder's walkthrough, these areas/angles are most important:")
        for note in camera_notes:
            prompt_parts.append(f"  - {note}")

    prompt_parts.append(f"""

{"You have both the walkthrough VIDEO and still photos. The video shows spatial relationships and the full layout — USE IT. The stills show fine details." if video else "Analyze the photos carefully."}

Create a detailed scene bible as JSON. Pay special attention to:
1. EXACT visual details of every minifig (clothing colors, hair, accessories, position)
2. EXACT colors and positions of all vehicles and buildings
3. The full spatial layout — what's in front, what's behind, relative positions
4. The builder's own descriptions of characters and their personalities
5. The story structure the builder described

Use this JSON schema:
{SCENE_BIBLE_SCHEMA}

IMPORTANT: Use the builder's own character names and descriptions when available.
Be extremely specific about visual details — these will be used to generate video
that must look EXACTLY like this physical Lego scene.

Return ONLY the JSON object, no markdown fences or explanation.""")

    content.append({"type": "text", "text": "\n".join(prompt_parts)})

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
    )

    response_text = message.content[0].text.strip()
    scene_bible = repair_and_parse_json(response_text)

    # Preserve video storage path for production stage
    if video_intel and video_intel.get("_video_storage_path"):
        scene_bible["_video_storage_path"] = video_intel["_video_storage_path"]

    logger.info(f"Scene analysis complete: {scene_bible.get('title', 'untitled')} — {len(scene_bible.get('cast', []))} cast, {len(scene_bible.get('locations', scene_bible.get('setting', {}).get('locations', [])))} locations")
    return scene_bible
