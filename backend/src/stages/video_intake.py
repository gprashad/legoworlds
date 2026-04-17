"""
Video intake: full intelligence extraction from walkthrough videos.

When a kid records a walkthrough video with narration, we extract:
1. Key frames at narration-matched timestamps (not just even intervals)
2. Timestamped transcript with segment data
3. Narration intelligence: character names, personalities, conflicts, story beats
4. Camera movement analysis: pan direction, pauses, focus areas
5. The original video reference for Claude Vision scene analysis

The kid's voice is NEVER used in the final movie — only as intelligence.
"""

import os
import json
import logging
import subprocess
import shutil
import httpx
import anthropic
from pathlib import Path
from src.supabase_client import get_supabase
from src.config import SUPABASE_STORAGE_BUCKET
from src.utils.json_repair import repair_and_parse_json

logger = logging.getLogger(__name__)

TEMP_BASE = os.getenv("TEMP_DIR", "/tmp/legoworlds")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MAX_FRAMES = 8
MAX_VIDEO_DURATION = 120


def _ensure_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)


def _get_video_duration(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        return 30.0
    data = json.loads(result.stdout)
    return float(data.get("format", {}).get("duration", 30.0))


def _extract_frame_at(video_path: str, timestamp: float, output_path: str) -> bool:
    """Extract a single frame at a specific timestamp."""
    result = subprocess.run(
        ["ffmpeg", "-y", "-ss", str(timestamp), "-i", video_path,
         "-vframes", "1", "-q:v", "2", "-vf", "scale='min(1920,iw)':-2", output_path],
        capture_output=True, text=True, timeout=15,
    )
    return result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000


def _extract_audio(video_path: str, audio_path: str) -> bool:
    """Extract audio track from video as WAV with volume normalization."""
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn",
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,highpass=f=80,lowpass=f=8000",
         "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
         "-t", str(MAX_VIDEO_DURATION), audio_path],
        capture_output=True, text=True, timeout=60,
    )
    return os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000


# --- Phase 2: Narration Intelligence ---

async def _transcribe_verbose(audio_path: str) -> dict:
    """Transcribe audio with Whisper verbose mode — returns timestamped segments.
    Retries on rate limit (429)."""
    if not OPENAI_API_KEY:
        return {"text": "", "segments": []}

    import asyncio
    max_retries = 3

    for attempt in range(max_retries):
        async with httpx.AsyncClient(timeout=120) as client:
            with open(audio_path, "rb") as f:
                res = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                    files={"file": ("audio.wav", f, "audio/wav")},
                    data={
                        "model": "whisper-1",
                        "language": "en",
                        "response_format": "verbose_json",
                        "timestamp_granularities[]": "segment",
                        "prompt": "A kid showing their Lego scene and narrating the backstory.",
                    },
                )

        if res.status_code == 429:
            wait = (attempt + 1) * 10  # 10s, 20s, 30s
            logger.warning(f"Whisper rate limited, retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(wait)
            continue

        break

    if res.status_code != 200:
        logger.warning(f"Whisper failed: {res.status_code}")
        return {"text": "", "segments": []}

    data = res.json()
    return {
        "text": data.get("text", ""),
        "segments": [
            {"start": s["start"], "end": s["end"], "text": s["text"]}
            for s in data.get("segments", [])
        ],
    }


NARRATION_INTELLIGENCE_TOOL = {
    "name": "save_narration_intelligence",
    "description": "Save structured intelligence extracted from the kid's narration.",
    "input_schema": {
        "type": "object",
        "properties": {
            "characters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "personality": {"type": "string"},
                        "role": {"type": "string"},
                    },
                    "required": ["name", "description"],
                },
            },
            "key_moments": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "timestamp": {"type": "number"},
                        "description": {"type": "string"},
                    },
                    "required": ["timestamp", "description"],
                },
            },
            "story_beats": {
                "type": "object",
                "properties": {
                    "setup": {"type": "string"},
                    "conflict": {"type": "string"},
                    "stakes": {"type": "string"},
                },
            },
            "camera_notes": {"type": "array", "items": {"type": "string"}},
            "backstory": {"type": "string"},
        },
        "required": ["characters", "key_moments", "story_beats", "camera_notes", "backstory"],
    },
}


async def _extract_narration_intelligence(transcript: dict) -> dict:
    """Use Claude tool-use to extract structured intelligence. Never raises — returns {} on failure."""
    text = transcript.get("text", "")
    if not text or len(text) < 10:
        return {}

    segments_text = "\n".join(
        f"[{s['start']:.1f}s - {s['end']:.1f}s] {s['text']}"
        for s in transcript.get("segments", [])
    )

    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=2000,
            tools=[NARRATION_INTELLIGENCE_TOOL],
            tool_choice={"type": "tool", "name": "save_narration_intelligence"},
            messages=[{
                "role": "user",
                "content": f"""A kid just recorded a walkthrough video of their Lego build and narrated it. Here's the timestamped transcript:

{segments_text}

Analyze this narration and call save_narration_intelligence with:

1. **characters**: Any characters the kid mentions — names, nicknames, descriptions, personalities, roles (hero/villain/etc). Use the kid's exact words.
2. **key_moments**: Timestamps where the kid introduces something important (a character, a vehicle, a building, a conflict). These are the best frames to extract.
3. **story_beats**: The narrative structure — what's the setup, conflict, and stakes?
4. **camera_notes**: Based on when the kid pauses or lingers (longer segments), what areas are most important to show?
5. **backstory**: A clean version of what the kid said, organized into a coherent backstory paragraph."""
            }],
        )

        for block in message.content:
            if getattr(block, "type", None) == "tool_use":
                return block.input or {}

        # No tool_use block — fall back to legacy text parse
        for block in message.content:
            if getattr(block, "type", None) == "text":
                try:
                    return repair_and_parse_json(block.text)
                except Exception:
                    pass
        logger.warning("Narration intelligence: no tool_use or parseable text in response")
        return {}
    except Exception as e:
        logger.warning(f"Narration intelligence extraction failed: {e}")
        return {}


# --- Phase 3: Smart Frame Extraction ---

def _extract_smart_frames(
    video_path: str,
    output_dir: str,
    key_moments: list[dict],
    duration: float,
) -> list[dict]:
    """Extract frames at key narration moments + regular intervals for coverage."""
    _ensure_dir(output_dir)
    frames = []

    # Extract at key moments first
    for i, moment in enumerate(key_moments[:6]):
        ts = moment.get("timestamp", 0)
        if ts < 0 or ts > duration:
            continue
        output = os.path.join(output_dir, f"key_{i:02d}.jpg")
        if _extract_frame_at(video_path, ts, output):
            frames.append({
                "path": output,
                "timestamp": ts,
                "label": moment.get("description", f"key moment at {ts:.1f}s"),
                "source": "narration_match",
            })

    # Fill remaining slots with regular interval frames for coverage
    remaining = MAX_FRAMES - len(frames)
    if remaining > 0 and duration > 3:
        start = duration * 0.1
        end = duration * 0.9
        interval = (end - start) / (remaining + 1)
        for i in range(remaining):
            ts = start + interval * (i + 1)
            # Skip if too close to an existing key frame
            if any(abs(ts - f["timestamp"]) < 2.0 for f in frames):
                continue
            output = os.path.join(output_dir, f"reg_{i:02d}.jpg")
            if _extract_frame_at(video_path, ts, output):
                frames.append({
                    "path": output,
                    "timestamp": ts,
                    "label": f"coverage frame at {ts:.1f}s",
                    "source": "interval",
                })

    frames.sort(key=lambda f: f["timestamp"])
    logger.info(f"Extracted {len(frames)} frames ({sum(1 for f in frames if f['source']=='narration_match')} from narration, rest coverage)")
    return frames


# --- Main Processing Function ---

async def process_video_intake(scene_id: str, video_storage_path: str) -> dict:
    """
    Full video intelligence extraction:
    1. Transcribe with timestamps
    2. Extract narration intelligence (characters, beats, moments)
    3. Smart frame extraction at key moments
    4. Store everything for the pipeline

    Returns dict with processing results.
    """
    sb = get_supabase()
    work_dir = os.path.join(TEMP_BASE, f"{scene_id}_video")
    frames_dir = os.path.join(work_dir, "frames")
    _ensure_dir(work_dir)

    try:
        # Download video
        logger.info(f"[{scene_id}] Downloading video for processing...")
        video_local = os.path.join(work_dir, "video.mp4")
        data = sb.storage.from_(SUPABASE_STORAGE_BUCKET).download(video_storage_path)
        with open(video_local, "wb") as f:
            f.write(data)

        duration = _get_video_duration(video_local)
        logger.info(f"[{scene_id}] Video duration: {duration:.1f}s")

        # --- Step 1: Transcribe with timestamps ---
        transcript = {"text": "", "segments": []}
        audio_path = os.path.join(work_dir, "audio.wav")
        if _extract_audio(video_local, audio_path):
            logger.info(f"[{scene_id}] Transcribing narration (verbose)...")
            transcript = await _transcribe_verbose(audio_path)
            logger.info(f"[{scene_id}] Transcribed: {len(transcript['text'])} chars, {len(transcript['segments'])} segments")

        # --- Step 2: Extract narration intelligence (never fatal) ---
        intelligence = {}
        if transcript["text"]:
            logger.info(f"[{scene_id}] Extracting narration intelligence...")
            try:
                intelligence = await _extract_narration_intelligence(transcript) or {}
            except Exception as e:
                logger.warning(f"[{scene_id}] Narration intelligence skipped: {e}")
                intelligence = {}
            logger.info(f"[{scene_id}] Found {len(intelligence.get('characters', []))} characters, {len(intelligence.get('key_moments', []))} key moments")

        # --- Step 3: Smart frame extraction ---
        key_moments = intelligence.get("key_moments", [])
        logger.info(f"[{scene_id}] Extracting frames ({len(key_moments)} key moments)...")
        frames = _extract_smart_frames(video_local, frames_dir, key_moments, duration)

        # Upload frames
        uploaded_frames = []
        for i, frame in enumerate(frames):
            storage_path = f"scenes/{scene_id}/input/vframe_{i:02d}.jpg"
            with open(frame["path"], "rb") as f:
                sb.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
                    storage_path, f.read(),
                    {"content-type": "image/jpeg", "upsert": "true"},
                )

            public_url = sb.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(storage_path)
            existing = sb.table("scene_media").select("id").eq("scene_id", scene_id).execute()

            sb.table("scene_media").insert({
                "scene_id": scene_id,
                "file_url": public_url,
                "file_type": "photo",
                "file_name": f"frame_{i + 1}.jpg",
                "file_size_bytes": os.path.getsize(frame["path"]),
                "sort_order": len(existing.data),
                "source": "video_extract",
            }).execute()
            uploaded_frames.append(storage_path)

        # --- Step 4: Update scene with intelligence ---
        backstory = intelligence.get("backstory", transcript.get("text", ""))

        # Store the original video path for Claude Vision to use in scene analysis
        # Store narration intelligence as metadata
        update_fields = {}
        existing_scene = sb.table("scenes").select("backstory,structured_description").eq("id", scene_id).execute().data[0]
        if backstory and not existing_scene.get("backstory"):
            update_fields["backstory"] = backstory

        # Auto-populate the Brief from narration intelligence (only if user hasn't filled it in)
        existing_sd = existing_scene.get("structured_description") or {}
        if intelligence and not any(existing_sd.get(k) for k in ("one_liner", "characters", "what_happens")):
            chars = intelligence.get("characters", [])
            char_lines = []
            for c in chars:
                name = c.get("name", "").strip()
                desc = c.get("description", "").strip()
                personality = c.get("personality", "").strip()
                if name:
                    line = name
                    if desc:
                        line += f" — {desc}"
                    if personality:
                        line += f" ({personality})"
                    char_lines.append(line)

            beats = intelligence.get("story_beats") or {}
            setup = (beats.get("setup") or "").strip()
            conflict = (beats.get("conflict") or "").strip()
            stakes = (beats.get("stakes") or "").strip()
            what_happens = " ".join(p for p in [setup, conflict, stakes] if p)

            # Pull a one-liner: prefer conflict, fall back to first sentence of backstory
            one_liner = ""
            if conflict:
                one_liner = conflict.split(". ")[0].strip().rstrip(".")
            elif backstory:
                one_liner = backstory.split(". ")[0].strip().rstrip(".")

            auto_sd = {
                **existing_sd,
                "one_liner": one_liner or existing_sd.get("one_liner", ""),
                "characters": "\n".join(char_lines) if char_lines else existing_sd.get("characters", ""),
                "what_happens": what_happens or existing_sd.get("what_happens", ""),
                "mood": existing_sd.get("mood", ""),
            }
            update_fields["structured_description"] = auto_sd

        # Store video intelligence in scene_bible temporarily
        # (will be overwritten by proper scene analysis, but enriches it)
        video_intel = {
            "_video_intelligence": True,
            "_transcript": transcript,
            "_narration_intelligence": intelligence,
            "_video_storage_path": video_storage_path,
            "_camera_notes": intelligence.get("camera_notes", []),
            "_story_beats": intelligence.get("story_beats", {}),
            "_character_hints": intelligence.get("characters", []),
        }
        update_fields["scene_bible"] = video_intel

        if update_fields:
            sb.table("scenes").update(update_fields).eq("id", scene_id).execute()

        logger.info(f"[{scene_id}] Video processing complete: {len(uploaded_frames)} frames, backstory={'yes' if backstory else 'no'}")

        return {
            "frames": uploaded_frames,
            "frame_count": len(uploaded_frames),
            "backstory": backstory,
            "intelligence": intelligence,
            "transcript_segments": len(transcript.get("segments", [])),
        }

    finally:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)
