import os
import logging
import subprocess
import shutil
from pathlib import Path
from src.supabase_client import get_supabase
from src.config import SUPABASE_STORAGE_BUCKET

logger = logging.getLogger(__name__)

TEMP_BASE = os.getenv("TEMP_DIR", "/tmp/legoworlds")
FPS = 24
RESOLUTION = "1920x1080"


def _ensure_dir(path: str):
    Path(path).mkdir(parents=True, exist_ok=True)


def _run_ffmpeg(args: list[str], desc: str = ""):
    """Run ffmpeg command, raise on failure."""
    cmd = ["ffmpeg", "-y"] + args
    logger.info(f"FFmpeg [{desc}]: {' '.join(cmd[:10])}...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.error(f"FFmpeg failed [{desc}]: {result.stderr[-500:]}")
        raise RuntimeError(f"FFmpeg failed ({desc}): {result.stderr[-200:]}")


async def _download_from_storage(storage_path: str, local_path: str):
    """Download a file from Supabase Storage to local disk."""
    sb = get_supabase()
    data = sb.storage.from_(SUPABASE_STORAGE_BUCKET).download(storage_path)
    with open(local_path, "wb") as f:
        f.write(data)


async def _download_photos(scene_id: str, work_dir: str) -> list[str]:
    """Download all input photos."""
    sb = get_supabase()
    folder = f"scenes/{scene_id}/input"
    files = sb.storage.from_(SUPABASE_STORAGE_BUCKET).list(folder)
    photo_paths = []

    for f in files:
        name = f["name"]
        if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            local = os.path.join(work_dir, "photos", name)
            _ensure_dir(os.path.dirname(local))
            await _download_from_storage(f"{folder}/{name}", local)
            photo_paths.append(local)

    return photo_paths


def _escape_drawtext(text: str) -> str:
    """Escape text for FFmpeg drawtext filter."""
    return text.replace("\\", "\\\\").replace("'", "'\\\\\\''").replace(":", "\\:").replace("%", "%%")


def _create_title_card(text: str, output_path: str, duration: float = 3.0):
    """Create a title card video with text on dark background."""
    escaped = _escape_drawtext(text)
    _run_ffmpeg([
        "-f", "lavfi",
        "-i", f"color=c=0x1A1A1A:s={RESOLUTION}:d={duration}:r={FPS}",
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=stereo",
        "-t", str(duration),
        "-vf", f"drawtext=text='{escaped}':fontcolor=white:fontsize=60:x=(w-text_w)/2:y=(h-text_h)/2:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "-c:v", "libx264", "-c:a", "aac",
        "-shortest",
        output_path,
    ], desc=f"title card: {text[:30]}")


def _create_photo_slideshow(photo_paths: list[str], output_path: str, duration_per_photo: float = 4.0):
    """Create Ken Burns slideshow from photos."""
    if not photo_paths:
        return None

    # Create a concat file for the slideshow
    total_dur = duration_per_photo * len(photo_paths)
    concat_dir = os.path.dirname(output_path)

    # Use ffmpeg to create slideshow with zoompan
    inputs = []
    filters = []
    for i, photo in enumerate(photo_paths):
        inputs.extend(["-loop", "1", "-t", str(duration_per_photo), "-i", photo])
        filters.append(
            f"[{i}:v]scale={RESOLUTION}:force_original_aspect_ratio=decrease,"
            f"pad={RESOLUTION}:(ow-iw)/2:(oh-ih)/2:color=0x1A1A1A,"
            f"zoompan=z='min(zoom+0.0015,1.3)':d={int(duration_per_photo * FPS)}:s={RESOLUTION}:fps={FPS}[v{i}]"
        )

    concat_parts = "".join(f"[v{i}]" for i in range(len(photo_paths)))
    filters.append(f"{concat_parts}concat=n={len(photo_paths)}:v=1:a=0[slideshow]")

    _run_ffmpeg(
        inputs + [
            "-filter_complex", ";".join(filters),
            "-map", "[slideshow]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-t", str(total_dur),
            output_path,
        ],
        desc="photo slideshow",
    )
    return output_path


def _concat_videos(video_paths: list[str], output_path: str):
    """Concatenate video files with crossfade transitions."""
    if len(video_paths) == 1:
        shutil.copy(video_paths[0], output_path)
        return

    # Write concat list
    list_file = output_path + ".txt"
    with open(list_file, "w") as f:
        for path in video_paths:
            f.write(f"file '{path}'\n")

    _run_ffmpeg([
        "-f", "concat", "-safe", "0", "-i", list_file,
        "-c:v", "libx264", "-c:a", "aac",
        "-pix_fmt", "yuv420p",
        output_path,
    ], desc="concat videos")
    os.remove(list_file)


def _overlay_audio(video_path: str, audio_path: str, output_path: str):
    """Overlay audio onto video, mixing with any existing audio."""
    _run_ffmpeg([
        "-i", video_path,
        "-i", audio_path,
        "-filter_complex",
        "[0:a]volume=0.3[bg];[1:a]volume=1.0[fg];[bg][fg]amix=inputs=2:duration=first[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac",
        "-shortest",
        output_path,
    ], desc="overlay audio")


def _add_silent_audio(video_path: str, output_path: str):
    """Add silent audio track to a video that has none."""
    _run_ffmpeg([
        "-i", video_path,
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
        "-c:v", "copy", "-c:a", "aac", "-shortest",
        output_path,
    ], desc="add silent audio")


def _extract_thumbnail(video_path: str, output_path: str):
    """Extract a thumbnail from a video at 5 seconds."""
    _run_ffmpeg([
        "-i", video_path,
        "-ss", "5", "-vframes", "1",
        "-vf", f"scale={RESOLUTION}",
        output_path,
    ], desc="thumbnail")


async def assemble_movie(
    scene_id: str,
    screenplay: dict,
    video_paths: list[str],
    audio_paths: dict,
) -> tuple[str, str]:
    """
    Assemble the final movie from production assets.
    Returns (final_video_storage_path, thumbnail_storage_path).
    """
    sb = get_supabase()
    work_dir = os.path.join(TEMP_BASE, scene_id)
    _ensure_dir(work_dir)
    _ensure_dir(os.path.join(work_dir, "segments"))

    try:
        # Download all production assets locally
        logger.info(f"[{scene_id}] Downloading production assets...")

        local_videos = []
        for sp in video_paths:
            local = os.path.join(work_dir, os.path.basename(sp))
            await _download_from_storage(sp, local)
            local_videos.append(local)

        local_audio = {}
        for key, sp in audio_paths.items():
            local = os.path.join(work_dir, f"{key}.mp3")
            await _download_from_storage(sp, local)
            local_audio[key] = local

        # Download photos for slideshow
        photo_paths = await _download_photos(scene_id, work_dir)

        segments = []
        director = screenplay.get("credits", {}).get("directed_by", "Cary")

        # --- Title cards ---
        logger.info(f"[{scene_id}] Creating title cards...")
        title1 = os.path.join(work_dir, "segments", "01_presents.mp4")
        _create_title_card("LEGO WORLDS presents...", title1, duration=3.0)
        segments.append(title1)

        title2 = os.path.join(work_dir, "segments", "02_director.mp4")
        _create_title_card(f"A film by {director}", title2, duration=3.0)
        segments.append(title2)

        title3 = os.path.join(work_dir, "segments", "03_title.mp4")
        _create_title_card(screenplay.get("title", "Untitled"), title3, duration=3.0)
        segments.append(title3)

        # --- Behind the scenes slideshow ---
        if photo_paths:
            logger.info(f"[{scene_id}] Creating photo slideshow...")
            slideshow = os.path.join(work_dir, "segments", "04_slideshow.mp4")
            result = _create_photo_slideshow(photo_paths, slideshow, duration_per_photo=3.0)
            if result:
                # Overlay narrator intro audio on slideshow
                if "narrator_intro" in local_audio:
                    slideshow_with_audio = os.path.join(work_dir, "segments", "04_slideshow_audio.mp4")
                    slideshow_silent = os.path.join(work_dir, "segments", "04_slideshow_silent.mp4")
                    _add_silent_audio(slideshow, slideshow_silent)
                    _overlay_audio(slideshow_silent, local_audio["narrator_intro"], slideshow_with_audio)
                    segments.append(slideshow_with_audio)
                else:
                    slideshow_silent = os.path.join(work_dir, "segments", "04_slideshow_silent.mp4")
                    _add_silent_audio(slideshow, slideshow_silent)
                    segments.append(slideshow_silent)

        # --- Scene videos with dialogue ---
        logger.info(f"[{scene_id}] Assembling scene videos with dialogue...")
        for i, video_local in enumerate(local_videos):
            scene_num = i + 1
            segment_base = os.path.join(work_dir, "segments", f"scene_{scene_num}")

            # Ensure video has audio track
            video_with_audio = f"{segment_base}_base.mp4"
            _add_silent_audio(video_local, video_with_audio)

            # Layer dialogue audio onto video
            current = video_with_audio
            scene_dialogue_keys = [k for k in local_audio if k.startswith(f"dialogue_{scene_num}_")]
            for j, dk in enumerate(sorted(scene_dialogue_keys)):
                next_path = f"{segment_base}_dial{j}.mp4"
                _overlay_audio(current, local_audio[dk], next_path)
                current = next_path

            segments.append(current)

        # --- Credits ---
        logger.info(f"[{scene_id}] Creating credits...")
        credits_text = f"Directed by {director}"
        credits = os.path.join(work_dir, "segments", "99_credits.mp4")
        _create_title_card(credits_text, credits, duration=4.0)

        # Overlay narrator outro on credits if available
        if "narrator_outro" in local_audio:
            credits_with_audio = os.path.join(work_dir, "segments", "99_credits_audio.mp4")
            _overlay_audio(credits, local_audio["narrator_outro"], credits_with_audio)
            segments.append(credits_with_audio)
        else:
            segments.append(credits)

        # --- Final concat ---
        logger.info(f"[{scene_id}] Final concatenation ({len(segments)} segments)...")
        final_local = os.path.join(work_dir, "final.mp4")
        _concat_videos(segments, final_local)

        # Extract thumbnail
        thumb_local = os.path.join(work_dir, "thumbnail.jpg")
        _extract_thumbnail(final_local, thumb_local)

        # Upload to Supabase Storage
        logger.info(f"[{scene_id}] Uploading final movie...")
        final_storage = f"scenes/{scene_id}/output/final.mp4"
        thumb_storage = f"scenes/{scene_id}/output/thumbnail.jpg"

        with open(final_local, "rb") as f:
            sb.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
                final_storage, f.read(), {"content-type": "video/mp4", "upsert": "true"}
            )
        with open(thumb_local, "rb") as f:
            sb.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
                thumb_storage, f.read(), {"content-type": "image/jpeg", "upsert": "true"}
            )

        logger.info(f"[{scene_id}] Movie assembled and uploaded!")
        return final_storage, thumb_storage

    finally:
        # Clean up temp directory
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)
            logger.info(f"[{scene_id}] Cleaned up temp directory")
