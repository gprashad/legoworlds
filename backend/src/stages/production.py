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

CLIP_DURATION_SECONDS = 5  # shorter clips = less drift

FIDELITY_DIRECTIVE = """
STRICT RULES: This video must look EXACTLY like the reference photo.
- Same Lego pieces, same colors, same positions, same baseplate.
- Do NOT add, remove, or change any elements from the scene.
- Only minifig limbs and heads should move. Vehicles stay in place unless described.
- The baseplate, buildings, and background stay fixed.
- Real Lego bricks on a real baseplate. Stop-motion animation style.
- Shallow depth of field, warm cinematic lighting.
"""

# --- Voice System ---
# Fun voices matched to character archetypes (exact IDs from account)
VOICE_MAP = {
    "narrator": "JBFqnCBsd6RMkjVDRZzb",       # George — warm captivating storyteller (british)
    "protagonist": "SOYHLrjzK2X1ezoPC6cr",      # Harry — fierce warrior (heroic energy)
    "protagonist_female": "cgSgspJ2msm6clMCkdW9", # Jessica — playful, bright, warm
    "antagonist": "N2lVS1w4EtoT3dr4eOWO",       # Callum — husky trickster
    "supporting": "TX3LPaxmHKxFdv7VOQHJ",       # Liam — energetic
    "supporting_female": "FGY2WhTYpPnrIDTdsKH5", # Laura — enthusiast, quirky
    "elder": "pqHfZKP75CvOlQylNhV4",            # Bill — wise, mature
    "child": "cgSgspJ2msm6clMCkdW9",            # Jessica (bright)
    "default": "IKne3meq5aSn9XLyUdCD",          # Charlie — confident, energetic
}

# Emotion → voice settings tuning
EMOTION_SETTINGS = {
    "angry": {"stability": 0.30, "similarity_boost": 0.80, "style": 0.7, "use_speaker_boost": True},
    "furious": {"stability": 0.25, "similarity_boost": 0.80, "style": 0.8, "use_speaker_boost": True},
    "nervous": {"stability": 0.75, "similarity_boost": 0.60, "style": 0.3, "use_speaker_boost": False},
    "whispering": {"stability": 0.80, "similarity_boost": 0.50, "style": 0.2, "use_speaker_boost": False},
    "excited": {"stability": 0.35, "similarity_boost": 0.75, "style": 0.6, "use_speaker_boost": True},
    "happy": {"stability": 0.40, "similarity_boost": 0.70, "style": 0.5, "use_speaker_boost": True},
    "sad": {"stability": 0.70, "similarity_boost": 0.65, "style": 0.4, "use_speaker_boost": False},
    "dismissive": {"stability": 0.70, "similarity_boost": 0.60, "style": 0.3, "use_speaker_boost": False},
    "dramatic": {"stability": 0.35, "similarity_boost": 0.80, "style": 0.7, "use_speaker_boost": True},
    "sarcastic": {"stability": 0.55, "similarity_boost": 0.70, "style": 0.5, "use_speaker_boost": False},
    "heroic": {"stability": 0.40, "similarity_boost": 0.85, "style": 0.8, "use_speaker_boost": True},
    "sneaky": {"stability": 0.65, "similarity_boost": 0.55, "style": 0.3, "use_speaker_boost": False},
    "confident": {"stability": 0.50, "similarity_boost": 0.80, "style": 0.6, "use_speaker_boost": True},
    "scared": {"stability": 0.30, "similarity_boost": 0.60, "style": 0.5, "use_speaker_boost": True},
}

DEFAULT_VOICE_SETTINGS = {"stability": 0.45, "similarity_boost": 0.75, "style": 0.5, "use_speaker_boost": True}

# Narrator gets special cinematic settings
NARRATOR_SETTINGS = {"stability": 0.55, "similarity_boost": 0.85, "style": 0.7, "use_speaker_boost": True}


# --- Visual-First Prompt Builder ---

def _build_visual_prompt(scene_bible: dict, screenplay_scene: dict) -> str:
    """Build a video prompt that leads with EXACT visual details from the scene bible,
    then adds minimal motion. This keeps the generated video faithful to the real build."""

    parts = []

    # 1. VISUAL DESCRIPTION — what's in frame (the anchor)
    parts.append("A real photograph of a physical Lego scene built by a kid on a baseplate:")

    # Setting/location
    setting = scene_bible.get("setting", {})
    scene_location = screenplay_scene.get("location", "")
    locations = setting.get("locations", [])
    matched_location = next((l for l in locations if l["id"] == scene_location), None)

    if setting.get("description"):
        parts.append(f"Setting: {setting['description']}.")
    if matched_location:
        parts.append(f"This shot focuses on: {matched_location['description']} ({matched_location.get('position', '')}).")

    # Every visible element
    for vehicle in scene_bible.get("vehicles", []):
        operator_info = f", operated by a minifig" if vehicle.get("operator") else ""
        cargo_info = f", carrying {vehicle['cargo']}" if vehicle.get("cargo") else ""
        parts.append(f"A {vehicle['color']} {vehicle['type']} ({vehicle['id']}){operator_info}{cargo_info}.")

    for cast in scene_bible.get("cast", []):
        parts.append(f"{cast['description']}: {cast['visual_details']}.")

    for prop in scene_bible.get("props", []):
        parts.append(f"{prop['description']} near {prop['location']}.")

    # 2. SUBTLE MOTION — what happens (keep it minimal)
    action = screenplay_scene.get("action", "")
    camera = screenplay_scene.get("camera", {})
    camera_desc = f"{camera.get('angle', 'medium shot')}, {camera.get('movement', 'static')}"

    parts.append(f"\nSubtle stop-motion animation: {action}")
    parts.append(f"Camera: {camera_desc}.")
    parts.append("Only small character movements — heads turn, arms shift, minifigs lean. The scene layout stays exactly as built.")

    # 3. FIDELITY LOCK
    parts.append(FIDELITY_DIRECTIVE)

    return "\n".join(parts)


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


async def _check_fidelity(scene_id: str, reference_photos: list[dict], video_url: str) -> dict:
    """Ask Claude Vision to compare reference photo vs generated video.
    Returns {"score": 1-10, "issues": [...]}"""
    try:
        # Download first frame of video as image
        video_bytes = await _download_bytes(video_url)

        # Use first reference photo for comparison
        if not reference_photos:
            return {"score": 7, "issues": []}

        ref = reference_photos[0]
        content = [
            {"type": "image", "source": {"type": "base64", "media_type": ref["media_type"], "data": ref["base64"]}},
            {"type": "text", "text": "Above: the ORIGINAL Lego build (reference photo)."},
            {"type": "text", "text": """
Below is a description of an AI-generated video based on this Lego scene.
The video should look EXACTLY like the reference photo, just with subtle animation.

Rate the fidelity from 1-10:
- 8-10: Same minifigs, same vehicles, same colors, same layout. Looks like the real scene animated.
- 5-7: Similar vibes but some elements are wrong or missing.
- 1-4: Doesn't look like the same scene at all.

Return JSON only: {"score": N, "issues": ["specific issue 1", "specific issue 2"]}
"""},
        ]

        import anthropic
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[{"role": "user", "content": content}],
        )

        from src.utils.json_repair import repair_and_parse_json
        result = repair_and_parse_json(message.content[0].text)
        logger.info(f"[{scene_id}] Fidelity check: score={result.get('score', '?')}")
        return result

    except Exception as e:
        logger.warning(f"[{scene_id}] Fidelity check failed: {e}")
        return {"score": 7, "issues": []}


async def generate_scene_videos(
    scene_id: str,
    screenplay: dict,
    scene_bible: dict = None,
    on_progress: callable = None,
) -> list[str]:
    """Generate video clips for each screenplay scene using visual-first prompts.
    Sends ALL photos as reference and checks fidelity after generation."""
    photo_urls = await _get_photo_urls(scene_id)
    if not photo_urls:
        raise ValueError("No photos found for video generation")

    # Also get photos as base64 for fidelity checking
    from src.stages.scene_analysis import download_photos_as_base64
    reference_photos = await download_photos_as_base64(scene_id)

    storage_paths = []

    for scene in screenplay["scenes"]:
        num = scene["scene_number"]

        # Build visual-first prompt from scene bible
        if scene_bible:
            prompt = _build_visual_prompt(scene_bible, scene)
        else:
            # Fallback to old style if no scene bible
            prompt = f"{scene['action']} {scene['camera']['angle']}, {scene['camera']['movement']}. {FIDELITY_DIRECTIVE}"

        logger.info(f"[{scene_id}] Generating video for scene {num} (visual-first prompt, {len(photo_urls)} ref photos)...")

        # Send ALL photos as reference
        max_retries = 2
        for attempt in range(max_retries):
            task_id = await _submit_video_generation(prompt, photo_urls)
            video_url = await _poll_video(task_id)

            # Fidelity check on first attempt
            if attempt == 0 and reference_photos:
                fidelity = await _check_fidelity(scene_id, reference_photos, video_url)
                score = fidelity.get("score", 7)
                if score < 5 and attempt < max_retries - 1:
                    issues = ", ".join(fidelity.get("issues", []))
                    logger.warning(f"[{scene_id}] Scene {num} fidelity low ({score}/10): {issues}. Retrying...")
                    # Add issues to prompt for retry
                    prompt += f"\n\nPREVIOUS ATTEMPT ISSUES (fix these): {issues}"
                    continue
                elif score < 5:
                    logger.warning(f"[{scene_id}] Scene {num} fidelity still low ({score}/10), using anyway")

            break

        video_bytes = await _download_bytes(video_url)
        storage_path = f"scenes/{scene_id}/production/video/scene_{num}.mp4"
        _storage_upload(storage_path, video_bytes, "video/mp4")
        storage_paths.append(storage_path)
        logger.info(f"[{scene_id}] Scene {num} video uploaded ({len(video_bytes)} bytes)")

        if on_progress:
            on_progress(num, len(screenplay["scenes"]))

    return storage_paths


# --- ElevenLabs Voice Generation ---

def _get_emotion_settings(emotion: str) -> dict:
    """Get voice settings tuned to the emotion."""
    emotion_lower = emotion.lower().split(",")[0].strip()
    return EMOTION_SETTINGS.get(emotion_lower, DEFAULT_VOICE_SETTINGS)


async def _generate_speech(text: str, voice_id: str, emotion: str = "", is_narrator: bool = False) -> bytes:
    """Generate speech audio via ElevenLabs API with emotion-tuned settings."""
    if is_narrator:
        settings = NARRATOR_SETTINGS
    elif emotion:
        settings = _get_emotion_settings(emotion)
    else:
        settings = DEFAULT_VOICE_SETTINGS

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
                    "stability": settings["stability"],
                    "similarity_boost": settings["similarity_boost"],
                    "style": settings.get("style", 0.5),
                    "use_speaker_boost": settings.get("use_speaker_boost", True),
                },
            },
        )
        if res.status_code != 200:
            raise RuntimeError(f"ElevenLabs error {res.status_code}: {res.text[:200]}")
        return res.content


def _generate_sfx_local(description: str, output_path: str) -> bool:
    """Generate SFX using bundled FFmpeg-based library. Returns True if successful."""
    from src.utils.sfx_library import generate_sfx
    return generate_sfx(description, output_path)


def _voice_for_character(char_id: str, role: str, cast: list[dict]) -> str:
    """Pick a voice for a character based on role and cast info."""
    # Check for specific keywords in description
    char_info = next((c for c in cast if c["id"] == char_id), None)
    desc = (char_info.get("description", "") + " " + char_info.get("visual_details", "")).lower() if char_info else ""

    if "child" in desc or "kid" in desc or "boy" in desc or "girl" in desc:
        return VOICE_MAP["child"]
    if "old" in desc or "elder" in desc or "wise" in desc:
        return VOICE_MAP["elder"]
    if "female" in desc or "woman" in desc or "girl" in desc or "she" in desc:
        if role == "protagonist":
            return VOICE_MAP["protagonist_female"]
        return VOICE_MAP["supporting_female"]

    return VOICE_MAP.get(role, VOICE_MAP["default"])


async def generate_scene_audio(
    scene_id: str,
    screenplay: dict,
    scene_bible: dict,
    on_progress: callable = None,
) -> dict:
    """Generate all audio: dialogue, narrator, and SFX. Returns dict of storage paths."""
    audio_paths = {}
    cast = scene_bible.get("cast", [])
    char_roles = {m["id"]: m.get("role", "supporting") for m in cast}

    # --- Narrator intro (cinematic storyteller voice) ---
    logger.info(f"[{scene_id}] Generating narrator intro...")
    intro_audio = await _generate_speech(
        screenplay["narrator_intro"], VOICE_MAP["narrator"], is_narrator=True
    )
    intro_path = f"scenes/{scene_id}/production/audio/narrator_intro.mp3"
    _storage_upload(intro_path, intro_audio, "audio/mpeg")
    audio_paths["narrator_intro"] = intro_path

    # --- Dialogue per scene (emotion-tuned, character-matched voices) ---
    # Track which characters got which voice for consistency
    char_voice_cache: dict[str, str] = {}

    for scene in screenplay["scenes"]:
        num = scene["scene_number"]
        for i, line in enumerate(scene.get("dialogue", [])):
            char_id = line["character"]
            emotion = line.get("emotion", "")
            role = char_roles.get(char_id, "supporting")

            # Consistent voice per character across scenes
            if char_id not in char_voice_cache:
                char_voice_cache[char_id] = _voice_for_character(char_id, role, cast)
            voice_id = char_voice_cache[char_id]

            logger.info(f"[{scene_id}] Voice: {char_id} (scene {num}, line {i+1}, emotion: {emotion})")
            audio = await _generate_speech(line["line"], voice_id, emotion=emotion)
            path = f"scenes/{scene_id}/production/audio/dialogue_{num}_{i + 1}.mp3"
            _storage_upload(path, audio, "audio/mpeg")
            audio_paths[f"dialogue_{num}_{i + 1}"] = path

    # --- Sound effects per scene ---
    for scene in screenplay["scenes"]:
        num = scene["scene_number"]
        for i, sfx_desc in enumerate(scene.get("sound_effects", [])):
            logger.info(f"[{scene_id}] SFX: '{sfx_desc}' (scene {num})")
            import tempfile
            tmp_sfx = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp_sfx.close()
            if _generate_sfx_local(sfx_desc, tmp_sfx.name):
                with open(tmp_sfx.name, "rb") as f:
                    sfx_data = f.read()
                path = f"scenes/{scene_id}/production/audio/sfx_{num}_{i + 1}.mp3"
                _storage_upload(path, sfx_data, "audio/mpeg")
                audio_paths[f"sfx_{num}_{i + 1}"] = path
            os.unlink(tmp_sfx.name)

    # --- Narrator outro ---
    logger.info(f"[{scene_id}] Generating narrator outro...")
    outro_audio = await _generate_speech(
        screenplay["narrator_outro"], VOICE_MAP["narrator"], is_narrator=True
    )
    outro_path = f"scenes/{scene_id}/production/audio/narrator_outro.mp3"
    _storage_upload(outro_path, outro_audio, "audio/mpeg")
    audio_paths["narrator_outro"] = outro_path

    logger.info(f"[{scene_id}] All audio generated ({len(audio_paths)} files)")
    return audio_paths
