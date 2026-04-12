import os
import json
import logging
import base64
import httpx
import asyncio
from src.supabase_client import get_supabase
from src.config import SUPABASE_STORAGE_BUCKET

logger = logging.getLogger(__name__)


def _storage_upload(path: str, data: bytes, content_type: str):
    """Upload to Supabase Storage with upsert to handle retries."""
    sb = get_supabase()
    sb.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
        path, data, {"content-type": content_type, "upsert": "true"}
    )


async def cleanup_production_files(scene_id: str):
    """Remove old production and output files before retrying."""
    sb = get_supabase()
    for folder in ["production/video", "production/audio", "output"]:
        path = f"scenes/{scene_id}/{folder}"
        try:
            files = sb.storage.from_(SUPABASE_STORAGE_BUCKET).list(path)
            if files:
                paths = [f"{path}/{f['name']}" for f in files]
                sb.storage.from_(SUPABASE_STORAGE_BUCKET).remove(paths)
                logger.info(f"[{scene_id}] Cleaned up {len(paths)} files from {folder}")
        except Exception:
            pass  # folder may not exist


KIE_BASE = "https://api.kie.ai"
KIE_API_KEY = os.getenv("KIE_API_KEY", "")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

POLL_INTERVAL = 30  # seconds
MAX_POLL_ATTEMPTS = 60  # ~30 min max

STYLE_DIRECTIVE = (
    "Stop-motion animated Lego scene, cinematic lighting, "
    "shallow depth of field, real Lego pieces, maintain exact appearance "
    "from reference photo. Smooth camera movement."
)

# Voice assignments for character types
VOICE_MAP = {
    "protagonist": "pNInz6obpgDQGcFmaJgB",   # Adam
    "antagonist": "VR6AewLTigWG4xSOukaG",     # Arnold
    "supporting": "ErXwobaYiN019PkySvjV",      # Antoni
    "narrator": "EXAVITQu4vr4xnSDxMaL",       # Bella (narrator)
    "default": "pNInz6obpgDQGcFmaJgB",
}


# --- Kie.ai Video Generation ---

async def _get_photo_urls(scene_id: str) -> list[str]:
    """Get signed URLs for scene input photos."""
    sb = get_supabase()
    folder = f"scenes/{scene_id}/input"
    files = sb.storage.from_(SUPABASE_STORAGE_BUCKET).list(folder)

    urls = []
    for f in files:
        name = f["name"]
        if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            url = sb.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(f"{folder}/{name}")
            urls.append(url)
    return urls


async def _submit_video_generation(prompt: str, image_urls: list[str]) -> str:
    """Submit image-to-video task to Kie.ai, return taskId."""
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            f"{KIE_BASE}/api/v1/veo/generate",
            headers={"Authorization": f"Bearer {KIE_API_KEY}"},
            json={
                "prompt": prompt,
                "model": "veo3_fast",
                "aspect_ratio": "16:9",
                "generationType": "REFERENCE_2_VIDEO",
                "imageUrls": image_urls,
                "enableTranslation": False,
                "enableFallback": False,
            },
        )
        data = res.json()
        if data.get("code") != 200:
            raise RuntimeError(f"Kie.ai submit failed: {data.get('msg', data)}")
        return data["data"]["taskId"]


async def _poll_video(task_id: str) -> str:
    """Poll Kie.ai until video is ready, return download URL."""
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
            await asyncio.sleep(POLL_INTERVAL)
            res = await client.get(
                f"{KIE_BASE}/api/v1/veo/record-info",
                params={"taskId": task_id},
                headers={"Authorization": f"Bearer {KIE_API_KEY}"},
            )
            data = res.json()
            if data.get("code") != 200:
                if attempt % 4 == 0:
                    logger.info(f"  Poll #{attempt}: code={data.get('code')}")
                continue

            r = data["data"]
            if r.get("successFlag") == 1 and r.get("response", {}).get("resultUrls"):
                return r["response"]["resultUrls"][0]
            if r.get("successFlag") == 0 and r.get("errorMessage"):
                raise RuntimeError(f"Kie.ai generation failed: {r['errorMessage']}")
            if attempt % 4 == 0:
                logger.info(f"  Still generating... ({attempt * POLL_INTERVAL // 60}min)")

    raise RuntimeError(f"Kie.ai timeout after {MAX_POLL_ATTEMPTS * POLL_INTERVAL // 60}min")


async def _download_bytes(url: str) -> bytes:
    """Download file from URL."""
    async with httpx.AsyncClient(timeout=120) as client:
        res = await client.get(url)
        res.raise_for_status()
        return res.content


async def generate_scene_videos(
    scene_id: str,
    screenplay: dict,
    on_progress: callable = None,
) -> list[str]:
    """Generate video clips for each screenplay scene. Returns storage paths."""
    photo_urls = await _get_photo_urls(scene_id)
    if not photo_urls:
        raise ValueError("No photos found for video generation")

    sb = get_supabase()
    storage_paths = []

    for scene in screenplay["scenes"]:
        num = scene["scene_number"]
        logger.info(f"[{scene_id}] Generating video for scene {num}...")

        prompt = f"{scene['action']} {scene['camera']['angle']}, {scene['camera']['movement']}. {STYLE_DIRECTIVE}"

        task_id = await _submit_video_generation(prompt, photo_urls[:2])
        video_url = await _poll_video(task_id)
        video_bytes = await _download_bytes(video_url)

        storage_path = f"scenes/{scene_id}/production/video/scene_{num}.mp4"
        _storage_upload(storage_path, video_bytes, "video/mp4")
        storage_paths.append(storage_path)
        logger.info(f"[{scene_id}] Scene {num} video uploaded ({len(video_bytes)} bytes)")

        if on_progress:
            on_progress(num, len(screenplay["scenes"]))

    return storage_paths


# --- ElevenLabs Voice Generation ---

async def _generate_speech(text: str, voice_id: str) -> bytes:
    """Generate speech audio via ElevenLabs API."""
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            },
        )
        if res.status_code != 200:
            raise RuntimeError(f"ElevenLabs error {res.status_code}: {res.text[:200]}")
        return res.content


def _voice_for_role(role: str) -> str:
    """Get ElevenLabs voice ID for a character role."""
    return VOICE_MAP.get(role, VOICE_MAP["default"])


async def generate_scene_audio(
    scene_id: str,
    screenplay: dict,
    scene_bible: dict,
    on_progress: callable = None,
) -> dict:
    """Generate all audio for a screenplay. Returns dict of storage paths."""
    sb = get_supabase()
    audio_paths = {}

    # Build character → role lookup from scene bible
    char_roles = {}
    for member in scene_bible.get("cast", []):
        char_roles[member["id"]] = member.get("role", "supporting")

    # Narrator intro
    logger.info(f"[{scene_id}] Generating narrator intro...")
    intro_audio = await _generate_speech(screenplay["narrator_intro"], VOICE_MAP["narrator"])
    intro_path = f"scenes/{scene_id}/production/audio/narrator_intro.mp3"
    _storage_upload(intro_path, intro_audio, "audio/mpeg")
    audio_paths["narrator_intro"] = intro_path

    # Dialogue per scene
    for scene in screenplay["scenes"]:
        num = scene["scene_number"]
        for i, line in enumerate(scene.get("dialogue", [])):
            char_id = line["character"]
            role = char_roles.get(char_id, "supporting")
            voice_id = _voice_for_role(role)

            logger.info(f"[{scene_id}] Generating dialogue: {char_id} scene {num} line {i + 1}")
            audio = await _generate_speech(line["line"], voice_id)
            path = f"scenes/{scene_id}/production/audio/dialogue_{num}_{i + 1}.mp3"
            _storage_upload(path, audio, "audio/mpeg")
            audio_paths[f"dialogue_{num}_{i + 1}"] = path

    # Narrator outro
    logger.info(f"[{scene_id}] Generating narrator outro...")
    outro_audio = await _generate_speech(screenplay["narrator_outro"], VOICE_MAP["narrator"])
    outro_path = f"scenes/{scene_id}/production/audio/narrator_outro.mp3"
    _storage_upload(outro_path, outro_audio, "audio/mpeg")
    audio_paths["narrator_outro"] = outro_path

    logger.info(f"[{scene_id}] All audio generated ({len(audio_paths)} files)")
    return audio_paths
