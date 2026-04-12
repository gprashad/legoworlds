"""
Video intake: extract key frames + transcribe narration from uploaded video.
One video → reference photos + backstory, ready for the pipeline.
"""

import os
import logging
import subprocess
import shutil
import httpx
from pathlib import Path
from src.supabase_client import get_supabase
from src.config import SUPABASE_STORAGE_BUCKET

logger = logging.getLogger(__name__)

TEMP_BASE = os.getenv("TEMP_DIR", "/tmp/legoworlds")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MAX_FRAMES = 6
MAX_VIDEO_DURATION = 120  # seconds — only process first 2 min


def _ensure_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)


def _get_video_duration(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path],
        capture_output=True, text=True, timeout=10,
    )
    if result.returncode != 0:
        return 30.0  # fallback
    import json
    data = json.loads(result.stdout)
    return float(data.get("format", {}).get("duration", 30.0))


def _extract_key_frames(video_path: str, output_dir: str, max_frames: int = MAX_FRAMES) -> list[str]:
    """Extract evenly-spaced key frames from video, skipping shaky start/end."""
    _ensure_dir(output_dir)

    duration = _get_video_duration(video_path)
    duration = min(duration, MAX_VIDEO_DURATION)

    if duration < 3:
        # Very short video — just grab one frame from the middle
        output = os.path.join(output_dir, "frame_00.jpg")
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(duration / 2), "-i", video_path,
             "-vframes", "1", "-q:v", "2", output],
            capture_output=True, timeout=10,
        )
        return [output] if os.path.exists(output) else []

    # Skip first/last 10% (usually shaky)
    start = duration * 0.10
    end = duration * 0.90
    usable = end - start

    # Space frames evenly across the usable portion
    num_frames = min(max_frames, max(2, int(usable / 4)))  # at least 1 frame per 4 seconds
    interval = usable / (num_frames + 1)

    frames = []
    for i in range(num_frames):
        timestamp = start + interval * (i + 1)
        output = os.path.join(output_dir, f"frame_{i:02d}.jpg")
        result = subprocess.run(
            ["ffmpeg", "-y", "-ss", str(timestamp), "-i", video_path,
             "-vframes", "1", "-q:v", "2", "-vf", "scale='min(1920,iw)':-2", output],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0 and os.path.exists(output) and os.path.getsize(output) > 1000:
            frames.append(output)

    logger.info(f"Extracted {len(frames)} frames from {duration:.1f}s video")
    return frames


def _extract_audio(video_path: str, audio_path: str) -> bool:
    """Extract audio track from video as WAV for transcription."""
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn",
         "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
         "-t", str(MAX_VIDEO_DURATION), audio_path],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        logger.warning(f"Audio extraction failed: {result.stderr[-200:]}")
        return False
    # Check if audio file has any content
    return os.path.exists(audio_path) and os.path.getsize(audio_path) > 1000


async def _transcribe_audio(audio_path: str) -> str:
    """Transcribe audio using OpenAI Whisper API."""
    if not OPENAI_API_KEY:
        logger.warning("No OPENAI_API_KEY set, skipping transcription")
        return ""

    async with httpx.AsyncClient(timeout=60) as client:
        with open(audio_path, "rb") as f:
            res = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                files={"file": ("audio.wav", f, "audio/wav")},
                data={
                    "model": "whisper-1",
                    "language": "en",
                    "prompt": "A kid describing their Lego scene and the backstory of what's happening.",
                },
            )

    if res.status_code != 200:
        logger.warning(f"Whisper transcription failed: {res.status_code} {res.text[:200]}")
        return ""

    text = res.json().get("text", "").strip()
    logger.info(f"Transcribed {len(text)} characters from audio")
    return text


async def process_video_intake(scene_id: str, video_storage_path: str) -> dict:
    """
    Process an uploaded video: extract frames + transcribe narration.
    Returns {"frames": [storage_paths], "backstory": "transcribed text"}.
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

        # Extract key frames
        logger.info(f"[{scene_id}] Extracting key frames...")
        frame_paths = _extract_key_frames(video_local, frames_dir)

        # Upload frames as scene photos
        uploaded_frames = []
        for i, frame_path in enumerate(frame_paths):
            storage_path = f"scenes/{scene_id}/input/vframe_{i:02d}.jpg"
            with open(frame_path, "rb") as f:
                sb.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
                    storage_path, f.read(),
                    {"content-type": "image/jpeg", "upsert": "true"},
                )

            public_url = sb.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(storage_path)

            # Check how many media already exist for sort order
            existing = sb.table("scene_media").select("id").eq("scene_id", scene_id).execute()
            sort_order = len(existing.data)

            sb.table("scene_media").insert({
                "scene_id": scene_id,
                "file_url": public_url,
                "file_type": "photo",
                "file_name": f"frame_{i + 1}.jpg",
                "file_size_bytes": os.path.getsize(frame_path),
                "sort_order": sort_order,
                "source": "video_extract",
            }).execute()

            uploaded_frames.append(storage_path)

        logger.info(f"[{scene_id}] Uploaded {len(uploaded_frames)} frames")

        # Transcribe narration
        backstory = ""
        audio_path = os.path.join(work_dir, "audio.wav")
        if _extract_audio(video_local, audio_path):
            logger.info(f"[{scene_id}] Transcribing narration...")
            backstory = await _transcribe_audio(audio_path)

            if backstory:
                # Update scene with transcribed backstory (only if scene doesn't already have one)
                scene = sb.table("scenes").select("backstory").eq("id", scene_id).execute().data[0]
                if not scene.get("backstory"):
                    sb.table("scenes").update({"backstory": backstory}).eq("id", scene_id).execute()
                    logger.info(f"[{scene_id}] Backstory auto-filled from narration")
                else:
                    # Append transcription to existing backstory
                    existing = scene["backstory"]
                    combined = f"{existing}\n\n[From video narration]: {backstory}"
                    sb.table("scenes").update({"backstory": combined}).eq("id", scene_id).execute()
                    logger.info(f"[{scene_id}] Narration appended to existing backstory")
        else:
            logger.info(f"[{scene_id}] No audio track in video, skipping transcription")

        return {
            "frames": uploaded_frames,
            "backstory": backstory,
            "frame_count": len(uploaded_frames),
        }

    finally:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)
