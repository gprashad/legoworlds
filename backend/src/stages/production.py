import os
import json
import logging
import base64
import httpx
import asyncio
from src.supabase_client import get_supabase
from src.config import SUPABASE_STORAGE_BUCKET
from src.stages.shot_qa import qa_shot

logger = logging.getLogger(__name__)

# Per-shot Vision drift QA. Set SHOT_QA_ENABLED=false to skip during cheap iter runs.
SHOT_QA_ENABLED = os.getenv("SHOT_QA_ENABLED", "true").lower() in ("1", "true", "yes")
SHOT_QA_MAX_RETRIES = int(os.getenv("SHOT_QA_MAX_RETRIES", "2"))


def _storage_upload(path: str, data: bytes, content_type: str):
    """Upload to Supabase Storage with upsert to handle retries."""
    sb = get_supabase()
    sb.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
        path, data, {"content-type": content_type, "upsert": "true"}
    )


async def cleanup_production_files(scene_id: str, full: bool = False):
    """Remove old output files before retrying. By default only wipes the final
    output (so Kie.ai shot regens and ElevenLabs audio regens are skipped on
    retry). Pass full=True to wipe production assets too."""
    sb = get_supabase()
    folders = ["output"]
    if full:
        folders = ["production/video", "production/audio", "output"]
    for folder in folders:
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

# Video model on Kie.ai. "kling-v2-1-pro" = Kling 2.1 Pro (negative_prompt +
# cfg_scale + tail_image_url, $0.25/5s). "veo3_fast" = the old path, kept as
# fallback behind env var.
KIE_VIDEO_MODEL = os.getenv("KIE_VIDEO_MODEL", "kling-v2-1-pro")
# Kling cfg_scale: 0-1, default 0.5. Crank for strict first-frame adherence.
KLING_CFG_SCALE = float(os.getenv("KLING_CFG_SCALE", "0.8"))

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

# TRAILER NARRATOR — deep, dramatic, movie-trailer-guy voice
TRAILER_NARRATOR_VOICE = "nPczCjzI2devNBz1zQrb"  # Brian — deep, resonant, comforting
# Lower stability = more Jeff-Bridges texture variation (dry, knowing, warm).
# Higher style = more dramatic cadence. Speaker boost keeps low end present.
TRAILER_NARRATOR_SETTINGS = {
    "stability": 0.40,
    "similarity_boost": 0.90,
    "style": 0.75,
    "use_speaker_boost": True,
}


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


# LEGO physics rules prepended to every shot prompt. Keep tight — Kling has
# a 5000-char prompt cap and these rules should leave room for scene-specific detail.
LEGO_PHYSICS_PREAMBLE = """This is stop-motion LEGO animation — NOT cinematic video. RULES:
- Every object is a hard plastic LEGO piece. Pieces do not deform, stretch, or morph.
- Minifigures have stiff plastic bodies. They rotate only at head, arms, and waist.
  They do NOT walk smoothly — they hold still or snap to the next pose.
- Vehicles roll on their wheels in their facing direction only. No sideways sliding.
- Base plates are glued to the table. They DO NOT move, rotate, lift, or tilt.
- Nothing disappears. Every minifig and piece visible at frame 0 is visible at the final frame.
- No new objects, minifigs, or animals appear that were not in the reference photo.
- Lighting and camera angle are LOCKED unless the CAMERA section explicitly moves them.
- Visual style: plastic sheen, matte table surface, handmade stop-motion feel, slight fingerprint imperfection."""


# Passed to Kling as the `negative_prompt` param (≤500 chars).
LEGO_NEGATIVE_PROMPT = (
    "melting, morphing, deforming plastic, smooth organic motion, realistic humans, "
    "cinematic camera drift, base plate levitation, teleporting figures, disappearing minifigs, "
    "new characters appearing, minifigs walking smoothly, cars drifting sideways, "
    "objects phasing through each other, scale inconsistency, extra limbs, blur, low quality, "
    "dialogue mouth movement, text overlays, subtitles"
)


NOLAN_FORBIDDEN = """
FORBIDDEN — do NOT do any of these:
- Flying, floating, levitating anything
- Walking or running minifigs (stop-motion minifigs do NOT walk)
- Morphing or transforming Lego pieces
- New characters or objects appearing that aren't in the reference photo
- Pieces disappearing from the scene
- Camera clipping through walls or vehicles
- Extreme zooms that don't match the reference perspective
- Cuts within the clip (this is ONE continuous shot)
- Impossible perspectives (top-down when reference is side-on, etc.)
- Animals not in the reference
- Humans (real people) — only Lego minifigs
- Text overlays, subtitles, captions
- Dialogue or character mouth movement
- Cinematic distortion that breaks the physical-Lego look
"""


def _find_subject_in_bible(subject: str, scene_bible: dict) -> str | None:
    """Match shot.subject against scene_bible.cast to pull exact visual_details.
    Returns a descriptive string like 'Marcus (dark blue jacket, yellow face, black hair)'
    or None if no match."""
    if not subject:
        return None
    subject_lower = subject.lower()
    for cast_member in scene_bible.get("cast", []):
        name = str(cast_member.get("name", "")).lower()
        desc = str(cast_member.get("description", "")).lower()
        if name and (name in subject_lower or subject_lower in name):
            visuals = cast_member.get("visual_details") or cast_member.get("description")
            if visuals:
                display_name = cast_member.get("name") or cast_member.get("description", subject)
                return f"{display_name} ({visuals})"
        if desc and desc in subject_lower:
            visuals = cast_member.get("visual_details") or desc
            return f"{cast_member.get('description', subject)} ({visuals})"
    return None


def build_nolan_shot_prompt(
    shot: dict,
    scene_bible: dict,
    photo_filename: str | None = None,
) -> str:
    """Build a TIGHT prompt for a single shot. LEGO physics preamble + Nolan-style constraints.
    Works with either Kling or Veo3; the negative prompt is passed separately via the API."""

    subject = shot.get("subject", "the scene")
    motion = shot.get("motion", "static hold")
    camera = shot.get("camera", "static")
    description = shot.get("description", "")
    duration = shot.get("duration_seconds", 5)

    # Subject lock-in: pull exact visual_details from scene_bible.cast if subject matches
    subject_locked = _find_subject_in_bible(subject, scene_bible) or subject

    # Scene lighting — if the scene_bible specifies it, pipe it through
    setting = scene_bible.get("setting", {}) or {}
    lighting_hint = setting.get("lighting") or ""

    # Build visual anchor from scene bible (brief — photo conditioning handles details)
    visual_anchor = []
    if setting.get("description"):
        visual_anchor.append(f"Scene setting: {setting['description']}.")

    vehicles = scene_bible.get("vehicles", [])
    if vehicles:
        v_list = ", ".join(f"{v.get('color','')} {v.get('type','vehicle')}" for v in vehicles[:5])
        visual_anchor.append(f"Vehicles in scene: {v_list}.")

    cast = scene_bible.get("cast", [])
    if cast:
        visual_anchor.append(
            f"Minifigs in scene: {len(cast)} characters including "
            f"{', '.join(c.get('description','') for c in cast[:3])}."
        )

    visual_text = "\n".join(visual_anchor)

    prompt = f"""[LEGO PHYSICS]
{LEGO_PHYSICS_PREAMBLE}

[SUBJECT]
A SINGLE SHOT, {duration} seconds, MINIMAL motion.
Focus: {subject_locked}.
{subject_locked} stays in the same position throughout this shot unless the ALLOWED MOTION section says otherwise.
{description}

[EXACT VISUAL MATCH — DO NOT DEVIATE]
The frame shows exactly what is in the reference photo. Same Lego pieces, same colors,
same positions, same baseplate. Do NOT add, remove, or change any elements.
{visual_text}

[ALLOWED MOTION — ONLY THIS]
{motion}.
Nothing else in the frame moves. The baseplate, buildings, vehicles, and props are STATIC
unless the motion above specifies otherwise.

[CAMERA]
{camera}.
No shake, no swoop, no impossible angles. Camera stays fixed unless this line says otherwise.

[STYLE]
Stop-motion Lego aesthetic. Real Lego bricks on a real baseplate.
{f'Lighting: {lighting_hint}.' if lighting_hint else 'Warm cinematic lighting matching the reference photo.'}
Shallow depth of field with focus on {subject_locked}.
Film grain. 24fps. 16:9 aspect ratio.
{NOLAN_FORBIDDEN}
"""

    return prompt


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


def _is_kling_model(model: str) -> bool:
    return model.lower().startswith("kling")


async def _submit_video_generation(
    prompt: str,
    image_urls: list[str],
    negative_prompt: str | None = None,
    cfg_scale: float | None = None,
) -> tuple[str, str]:
    """Submit image-to-video task to Kie.ai.

    Returns (task_id, backend) where backend is 'kling' or 'veo' — the poller
    needs it to pick the right status endpoint and response shape."""
    model = KIE_VIDEO_MODEL
    if not image_urls:
        raise RuntimeError("No reference photos available for image-to-video submission")

    async with httpx.AsyncClient(timeout=60) as client:
        if _is_kling_model(model):
            # Kling 2.1 Pro: takes a single image_url + optional tail_image_url.
            # Passing the same URL as tail forces near-static output — the key
            # trick for stop-motion fidelity per the 2026-04-17 research.
            image_url = image_urls[0]
            kling_model_id = {
                "kling-v2-1-pro": "kling/v2-1-pro",
                "kling-v2-1-standard": "kling/v2-1-standard",
                "kling-v2-1-master": "kling/v2-1-master",
            }.get(model, "kling/v2-1-pro")

            effective_cfg = cfg_scale if cfg_scale is not None else KLING_CFG_SCALE
            payload = {
                "model": kling_model_id,
                "input": {
                    "prompt": prompt[:5000],
                    "image_url": image_url,
                    "tail_image_url": image_url,  # same photo both ends → near-static
                    "duration": str(CLIP_DURATION_SECONDS),
                    "cfg_scale": effective_cfg,
                },
            }
            if negative_prompt:
                payload["input"]["negative_prompt"] = negative_prompt[:500]

            res = await client.post(
                f"{KIE_BASE}/api/v1/jobs/createTask",
                headers={"Authorization": f"Bearer {KIE_API_KEY}"},
                json=payload,
            )
            data = res.json()
            if data.get("code") != 200:
                raise RuntimeError(f"Kie.ai Kling submit failed: {data.get('msg', data)}")
            return data["data"]["taskId"], "kling"

        # Veo3 fallback — original path
        res = await client.post(
            f"{KIE_BASE}/api/v1/veo/generate",
            headers={"Authorization": f"Bearer {KIE_API_KEY}"},
            json={
                "prompt": prompt,
                "model": "veo3_fast",
                "aspect_ratio": "16:9",
                "generationType": "FIRST_AND_LAST_FRAMES_2_VIDEO",
                "imageUrls": image_urls,
                "seeds": 81422,
                "enableTranslation": False,
                "enableFallback": False,
            },
        )
        data = res.json()
        if data.get("code") != 200:
            raise RuntimeError(f"Kie.ai Veo submit failed: {data.get('msg', data)}")
        return data["data"]["taskId"], "veo"


async def _poll_video(task_id: str, backend: str = "veo") -> str:
    """Poll Kie.ai until video is ready, return download URL.

    Kling uses the common /jobs/recordInfo endpoint with a different response
    shape; Veo uses /veo/record-info."""
    async with httpx.AsyncClient(timeout=30) as client:
        for attempt in range(1, MAX_POLL_ATTEMPTS + 1):
            await asyncio.sleep(POLL_INTERVAL)

            if backend == "kling":
                res = await client.get(
                    f"{KIE_BASE}/api/v1/jobs/recordInfo",
                    params={"taskId": task_id},
                    headers={"Authorization": f"Bearer {KIE_API_KEY}"},
                )
                data = res.json()
                if data.get("code") != 200:
                    if attempt % 4 == 0:
                        logger.info(f"  Poll #{attempt} [kling]: code={data.get('code')}")
                    continue

                r = data["data"] or {}
                # Kie common jobs API: state = "waiting" | "queuing" | "generating" | "success" | "fail"
                state = str(r.get("state", "")).lower()
                if state == "success":
                    result_json = r.get("resultJson") or {}
                    # resultJson is usually a JSON string; handle both shapes
                    if isinstance(result_json, str):
                        try:
                            import json as _json
                            result_json = _json.loads(result_json)
                        except Exception:
                            result_json = {}
                    urls = (
                        result_json.get("resultUrls")
                        or result_json.get("videoUrls")
                        or ([result_json["videoUrl"]] if result_json.get("videoUrl") else [])
                    )
                    if urls:
                        return urls[0]
                    raise RuntimeError(f"Kling success but no resultUrls: {r}")
                if state == "fail":
                    raise RuntimeError(
                        f"Kling generation failed: {r.get('failMsg') or r.get('errorMessage') or r}"
                    )
                if attempt % 4 == 0:
                    logger.info(
                        f"  Still generating [kling]... state={state} "
                        f"({attempt * POLL_INTERVAL // 60}min)"
                    )
                continue

            # Veo3 path
            res = await client.get(
                f"{KIE_BASE}/api/v1/veo/record-info",
                params={"taskId": task_id},
                headers={"Authorization": f"Bearer {KIE_API_KEY}"},
            )
            data = res.json()
            if data.get("code") != 200:
                if attempt % 4 == 0:
                    logger.info(f"  Poll #{attempt} [veo]: code={data.get('code')}")
                continue

            r = data["data"]
            if r.get("successFlag") == 1 and r.get("response", {}).get("resultUrls"):
                return r["response"]["resultUrls"][0]
            if r.get("successFlag") == 0 and r.get("errorMessage"):
                raise RuntimeError(f"Kie.ai generation failed: {r['errorMessage']}")
            if attempt % 4 == 0:
                logger.info(f"  Still generating [veo]... ({attempt * POLL_INTERVAL // 60}min)")

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
            model="claude-opus-4-7",
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
            task_id, backend = await _submit_video_generation(
                prompt, photo_urls, negative_prompt=LEGO_NEGATIVE_PROMPT
            )
            video_url = await _poll_video(task_id, backend=backend)

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


async def _generate_trailer_speech(text: str) -> bytes:
    """Generate speech with trailer-voice settings. Deep, dramatic, Brian voice."""
    settings = TRAILER_NARRATOR_SETTINGS
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{TRAILER_NARRATOR_VOICE}",
            headers={
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": settings,
            },
        )
        if res.status_code != 200:
            raise RuntimeError(f"ElevenLabs narrator error {res.status_code}: {res.text[:200]}")
        return res.content


async def generate_trailer_narration(
    scene_id: str,
    shot_list: dict,
) -> dict:
    """Generate trailer-voice narration for each narrator line.
    Returns dict mapping line index → storage path."""
    narrator_paths = {}
    lines = shot_list.get("narrator_lines", [])

    # Resume: skip regen of narrator lines that already exist in storage
    sb = get_supabase()
    existing_audio_files = set()
    try:
        listing = sb.storage.from_(SUPABASE_STORAGE_BUCKET).list(
            f"scenes/{scene_id}/production/audio"
        )
        existing_audio_files = {f["name"] for f in (listing or [])}
    except Exception:
        pass

    for i, line_data in enumerate(lines):
        text = line_data.get("line", "")
        if not text:
            continue

        path = f"scenes/{scene_id}/production/audio/narrator_{i:02d}.mp3"
        filename = f"narrator_{i:02d}.mp3"

        if filename in existing_audio_files:
            logger.info(f"[{scene_id}] Narrator line {i+1}/{len(lines)} already exists, skipping regen")
        else:
            logger.info(f"[{scene_id}] Narrator line {i+1}/{len(lines)}: \"{text[:60]}...\"")
            audio = await _generate_trailer_speech(text)
            _storage_upload(path, audio, "audio/mpeg")

        narrator_paths[f"narrator_{i:02d}"] = {
            "path": path,
            "time_seconds": line_data.get("time_seconds", i * 8),
            "line": text,
        }

    logger.info(f"[{scene_id}] Generated {len(narrator_paths)} narrator lines")
    return narrator_paths


async def generate_shot_list_videos(
    scene_id: str,
    shot_list: dict,
    scene_bible: dict,
    on_progress: callable = None,
) -> list[str]:
    """Generate video clips for a TRAILER-style shot list with Nolan-tight prompts.
    One reference photo per shot. Short duration. Strict motion constraints."""
    photo_urls = await _get_photo_urls(scene_id)
    if not photo_urls:
        raise ValueError("No photos found for video generation")

    storage_paths = []
    shots = shot_list.get("shots", [])

    # Check which shots already exist in storage (resume support — avoids
    # re-paying Kie.ai for already-generated shots on pipeline retry).
    sb = get_supabase()
    existing_shot_files = set()
    try:
        listing = sb.storage.from_(SUPABASE_STORAGE_BUCKET).list(
            f"scenes/{scene_id}/production/video"
        )
        existing_shot_files = {f["name"] for f in (listing or [])}
    except Exception:
        pass

    # Continuity lock: first time we see a given subject, we pin which
    # reference_photo_index it uses. Subsequent shots with the same subject
    # reuse it so the character doesn't flip-flop between takes.
    subject_photo_lock: dict[str, int] = {}

    def _lock_ref_idx(shot: dict) -> int:
        key = str(shot.get("subject", "")).strip().lower()
        claimed = shot.get("reference_photo_index", 0)
        if claimed is None or claimed >= len(photo_urls) or claimed < 0:
            claimed = 0
        if not key:
            return claimed
        if key in subject_photo_lock:
            return subject_photo_lock[key]
        subject_photo_lock[key] = claimed
        return claimed

    for shot in shots:
        num = shot.get("shot_number", len(storage_paths) + 1)
        storage_path = f"scenes/{scene_id}/production/video/shot_{num:02d}.mp4"
        filename = f"shot_{num:02d}.mp4"

        if filename in existing_shot_files:
            logger.info(f"[{scene_id}] Shot {num}/{len(shots)} already exists, skipping regen")
            storage_paths.append(storage_path)
            if on_progress:
                on_progress(num, len(shots))
            continue

        logger.info(f"[{scene_id}] Generating shot {num}/{len(shots)} ({shot.get('type', '?')})...")

        base_prompt = build_nolan_shot_prompt(shot, scene_bible)

        # Pick the reference photo via the subject-continuity lock so the
        # same character/location doesn't flip between different photos.
        ref_idx = _lock_ref_idx(shot)
        ref_photos = [photo_urls[ref_idx]]
        # Also include one more photo as context
        if len(photo_urls) > 1 and ref_idx != 0:
            ref_photos.append(photo_urls[0])

        # Generate + QA drift-check loop. On QA fail we re-submit with a
        # stricter suffix (lock everything except the named motion) and a
        # bumped cfg_scale for stronger first-frame adherence.
        prompt = base_prompt
        shot_cfg: float | None = None  # None → use KLING_CFG_SCALE default
        qa_result = None
        video_bytes = b""
        for attempt in range(SHOT_QA_MAX_RETRIES + 1):
            task_id, backend = await _submit_video_generation(
                prompt, ref_photos,
                negative_prompt=LEGO_NEGATIVE_PROMPT,
                cfg_scale=shot_cfg,
            )
            video_url = await _poll_video(task_id, backend=backend)
            video_bytes = await _download_bytes(video_url)

            if not SHOT_QA_ENABLED:
                break

            try:
                qa_result = await qa_shot(shot, video_bytes, ref_photos[0])
            except Exception as qa_err:
                logger.warning(
                    f"[{scene_id}] Shot {num} QA errored ({qa_err}); accepting clip as-is"
                )
                break

            if qa_result["pass"] or attempt == SHOT_QA_MAX_RETRIES:
                if not qa_result["pass"]:
                    logger.warning(
                        f"[{scene_id}] Shot {num} still failing QA after "
                        f"{SHOT_QA_MAX_RETRIES} retries — accepting: {qa_result['feedback']}"
                    )
                break

            # QA failed — tighten prompt and bump cfg_scale for next try
            logger.info(
                f"[{scene_id}] Shot {num} QA fail (attempt {attempt+1}): "
                f"{qa_result['feedback']}. Retrying with stricter constraints."
            )
            worst = min(qa_result["scores"], key=qa_result["scores"].get)
            stricter_suffix = (
                "\n\n[STRICTER — retry after drift detected]\n"
                f"Previous attempt failed on '{worst}' (score={qa_result['scores'][worst]}). "
                f"Issue: {qa_result['feedback']}. "
                "Lock EVERY element from the reference photo. Nothing moves except what is "
                "explicitly allowed in the ALLOWED MOTION section. No new objects, no "
                "disappearing pieces, no sliding, no morphing. Treat this as a near-still photo."
            )
            prompt = base_prompt + stricter_suffix
            shot_cfg = 0.9  # crank adherence for retry

        _storage_upload(storage_path, video_bytes, "video/mp4")
        storage_paths.append(storage_path)
        qa_note = ""
        if qa_result:
            qa_note = (
                f" [QA perm={qa_result['scores']['object_permanence']} "
                f"phys={qa_result['scores']['physics']} id={qa_result['scores']['identity']} "
                f"{'PASS' if qa_result['pass'] else 'FAIL'}]"
            )
        logger.info(f"[{scene_id}] Shot {num} uploaded ({len(video_bytes)} bytes){qa_note}")

        if on_progress:
            on_progress(num, len(shots))

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
