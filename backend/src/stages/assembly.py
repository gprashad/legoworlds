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
    return text.replace("\\", "\\\\").replace("'", "\u2019").replace(":", "\\:").replace("%", "%%").replace('"', '\\"')


def _create_title_card(text: str, output_path: str, duration: float = 3.0):
    """Create a title card video with text on dark background."""
    escaped = _escape_drawtext(text)
    _run_ffmpeg([
        "-f", "lavfi", "-i", f"color=c=0x1A1A1A:s={RESOLUTION}:r={FPS}:d={duration}",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
        "-filter_complex",
        f"[0:v]format=yuv420p,drawtext=text='{escaped}':fontcolor=white:fontsize=60:x=(w-text_w)/2:y=(h-text_h)/2:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf[v]",
        "-map", "[v]", "-map", "1:a",
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
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


def _overlay_audio(video_path: str, audio_path: str, output_path: str, audio_volume: float = 1.0, bg_volume: float = 0.3):
    """Overlay audio onto video, mixing with existing audio."""
    _run_ffmpeg([
        "-i", video_path,
        "-i", audio_path,
        "-filter_complex",
        f"[0:a]volume={bg_volume}[bg];[1:a]volume={audio_volume}[fg];[bg][fg]amix=inputs=2:duration=first[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac",
        "-shortest",
        output_path,
    ], desc="overlay audio")


def _mix_scene_audio(video_path: str, dialogue_paths: list[str], sfx_paths: list[str], output_path: str):
    """Mix dialogue and SFX onto a video scene.
    IGNORES the video's original audio entirely to prevent double voices from Kie.ai."""
    if not dialogue_paths and not sfx_paths:
        _add_silent_audio(video_path, output_path)
        return

    # Generate silent audio for video + mix ONLY our dialogue/sfx on top
    inputs = [
        "-i", video_path,
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
    ]

    for d in dialogue_paths:
        inputs.extend(["-i", d])
    for s in sfx_paths:
        inputs.extend(["-i", s])

    filters = []
    mix_inputs = []

    # Silent base (from anullsrc at index 1) — this replaces ANY built-in audio
    filters.append(f"[1:a]volume=0[bg]")
    mix_inputs.append("[bg]")

    # Dialogue starts at input index 2 (0=video, 1=silence)
    # Space dialogue sequentially so lines don't overlap
    idx = 2
    current_delay_ms = 500  # start 0.5s into the scene
    for d_path in dialogue_paths:
        # Get duration of this dialogue line
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", d_path],
            capture_output=True, text=True, timeout=5,
        )
        try:
            import json as _j
            line_duration = float(_j.loads(probe.stdout).get("format", {}).get("duration", 2.0))
        except Exception:
            line_duration = 2.0

        filters.append(f"[{idx}:a]volume=1.5,adelay={current_delay_ms}|{current_delay_ms}[d{idx}]")
        mix_inputs.append(f"[d{idx}]")

        current_delay_ms += int(line_duration * 1000) + 300  # 0.3s gap between lines
        idx += 1

    for _ in sfx_paths:
        filters.append(f"[{idx}:a]volume=0.4[s{idx}]")
        mix_inputs.append(f"[s{idx}]")
        idx += 1

    mix_str = "".join(mix_inputs)
    filters.append(f"{mix_str}amix=inputs={len(mix_inputs)}:duration=longest:dropout_transition=0:normalize=0[aout]")

    _run_ffmpeg(
        inputs + [
            "-filter_complex", ";".join(filters),
            "-map", "0:v:0", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_path,
        ],
        desc="mix scene audio",
    )


def _add_silent_audio(video_path: str, output_path: str):
    """Replace video's audio with a silent track (mutes any built-in audio from Kie.ai)."""
    # Get video duration first so we generate exactly the right amount of silence
    probe = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path],
        capture_output=True, text=True, timeout=10,
    )
    import json as _json
    duration = 10.0
    if probe.returncode == 0:
        try:
            duration = float(_json.loads(probe.stdout).get("format", {}).get("duration", 10))
        except Exception:
            pass

    _run_ffmpeg([
        "-i", video_path,
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac",
        "-shortest",
        output_path,
    ], desc="replace with silent audio")


def _trim_video(video_path: str, duration: float, output_path: str):
    """Trim a video to exact duration with silent audio."""
    _run_ffmpeg([
        "-i", video_path,
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
        "-map", "0:v:0", "-map", "1:a:0",
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "ultrafast",
        "-c:a", "aac",
        output_path,
    ], desc=f"trim to {duration}s")


def _concat_shots_hard_cuts(shot_paths: list[str], output_path: str):
    """Concatenate shots with hard cuts (no crossfades — trailer style)."""
    list_file = output_path + ".txt"
    with open(list_file, "w") as f:
        for path in shot_paths:
            f.write(f"file '{path}'\n")

    _run_ffmpeg([
        "-f", "concat", "-safe", "0", "-i", list_file,
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        output_path,
    ], desc="concat shots (hard cuts)")
    os.remove(list_file)


def _apply_trailer_narrator_mix(
    video_path: str,
    music_path: str,
    narrator_lines: list[dict],
    narrator_files: dict,
    output_path: str,
):
    """Mix the final trailer: video + music (ducked) + narrator lines at timestamps.

    narrator_lines: [{"time_seconds": N, "line": "..."}]
    narrator_files: dict[key → {"path": local_path, ...}]
    """
    inputs = [
        "-i", video_path,
        "-i", music_path,
    ]
    narrator_paths_ordered = []
    for i, line in enumerate(narrator_lines):
        key = f"narrator_{i:02d}"
        if key in narrator_files:
            narrator_paths_ordered.append((line, narrator_files[key]["path"]))
            inputs.extend(["-i", narrator_files[key]["path"]])

    if not narrator_paths_ordered:
        # No narrator — just add music over video (muted original audio)
        _run_ffmpeg([
            "-i", video_path, "-i", music_path,
            "-filter_complex",
            "[1:a]volume=0.5[music]",
            "-map", "0:v:0", "-map", "[music]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", output_path,
        ], desc="mix music only")
        return

    # Build filter:
    # 1. Music at 40% baseline, ducked to 12% when narrator speaks
    # 2. Each narrator line delayed to its timestamp
    filters = []

    # Delayed narrator tracks
    narrator_mix_inputs = []
    for i, (line, _) in enumerate(narrator_paths_ordered):
        delay_ms = int(line.get("time_seconds", i * 8) * 1000)
        idx = 2 + i
        filters.append(f"[{idx}:a]volume=1.8,adelay={delay_ms}|{delay_ms}[n{i}]")
        narrator_mix_inputs.append(f"[n{i}]")

    # Combine all narrator tracks
    narrator_mix_str = "".join(narrator_mix_inputs)
    filters.append(f"{narrator_mix_str}amix=inputs={len(narrator_mix_inputs)}:duration=longest:normalize=0[narration]")

    # Music ducks under narration using sidechaincompress
    filters.append(
        "[1:a]volume=0.4[music_pre];"
        "[music_pre][narration]sidechaincompress=threshold=0.05:ratio=8:attack=5:release=300[music_ducked]"
    )

    # Final mix: ducked music + narration
    filters.append("[music_ducked][narration]amix=inputs=2:duration=longest:normalize=0[final_audio]")

    # Apply reverb + loudness normalize on final audio
    filters.append("[final_audio]aecho=0.8:0.7:60:0.25,loudnorm=I=-14:TP=-1.5:LRA=11[mixed]")

    _run_ffmpeg(
        inputs + [
            "-filter_complex", ";".join(filters),
            "-map", "0:v:0", "-map", "[mixed]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", output_path,
        ],
        desc="trailer final mix",
    )


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

        segments = []

        # --- Scene videos with dialogue + SFX mixed ---
        logger.info(f"[{scene_id}] Mixing scene audio (dialogue + SFX)...")
        for i, video_local in enumerate(local_videos):
            scene_num = i + 1
            segment_base = os.path.join(work_dir, "segments", f"scene_{scene_num}")

            # Ensure video has audio track
            video_with_audio = f"{segment_base}_base.mp4"
            _add_silent_audio(video_local, video_with_audio)

            # Collect dialogue and SFX files for this scene
            dialogue_keys = sorted(k for k in local_audio if k.startswith(f"dialogue_{scene_num}_"))
            sfx_keys = sorted(k for k in local_audio if k.startswith(f"sfx_{scene_num}_"))
            dialogue_files = [local_audio[k] for k in dialogue_keys]
            sfx_files = [local_audio[k] for k in sfx_keys]

            if dialogue_files or sfx_files:
                mixed_path = f"{segment_base}_mixed.mp4"
                try:
                    _mix_scene_audio(video_with_audio, dialogue_files, sfx_files, mixed_path)
                    segments.append(mixed_path)
                except RuntimeError as e:
                    logger.warning(f"[{scene_id}] Mix failed for scene {scene_num}, falling back: {e}")
                    # Fallback: just overlay dialogue one at a time
                    current = video_with_audio
                    for j, dk in enumerate(dialogue_keys):
                        next_path = f"{segment_base}_dial{j}.mp4"
                        try:
                            _overlay_audio(current, local_audio[dk], next_path)
                            current = next_path
                        except RuntimeError:
                            pass
                    segments.append(current)
            else:
                segments.append(video_with_audio)

        if not segments:
            raise RuntimeError("No video segments to assemble")

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


async def assemble_trailer(
    scene_id: str,
    shot_list: dict,
    shot_video_paths: list[str],
    narrator_paths: dict,
    music_mood: str,
    director_name: str,
) -> tuple[str, str]:
    """
    Assemble the TRAILER-style final movie.

    1. Download all shot videos
    2. Trim each to its shot duration
    3. Concat shots with hard cuts
    4. Generate music track matching mood
    5. Generate title card + end card
    6. Mix music (ducked) + narrator lines at timestamps
    7. Final video with title/end cards bookending
    """
    from src.utils.music_library import generate_music_track

    sb = get_supabase()
    work_dir = os.path.join(TEMP_BASE, f"{scene_id}_trailer")
    _ensure_dir(work_dir)
    _ensure_dir(os.path.join(work_dir, "shots"))

    try:
        shots = shot_list.get("shots", [])
        narrator_lines = shot_list.get("narrator_lines", [])

        # --- 1. Download shot videos ---
        logger.info(f"[{scene_id}] Downloading {len(shot_video_paths)} shot videos...")
        local_shots = []
        for sp in shot_video_paths:
            local = os.path.join(work_dir, os.path.basename(sp))
            await _download_from_storage(sp, local)
            local_shots.append(local)

        # --- 2. Download narrator audio ---
        logger.info(f"[{scene_id}] Downloading narrator audio...")
        narrator_files = {}
        for key, info in narrator_paths.items():
            local = os.path.join(work_dir, f"{key}.mp3")
            await _download_from_storage(info["path"], local)
            narrator_files[key] = {"path": local, "time_seconds": info.get("time_seconds", 0), "line": info.get("line", "")}

        # --- 3. Trim each shot to its specified duration ---
        logger.info(f"[{scene_id}] Trimming shots to specified durations...")
        trimmed_shots = []
        for i, video_local in enumerate(local_shots):
            shot_data = shots[i] if i < len(shots) else {}
            duration = shot_data.get("duration_seconds", 5)
            trimmed = os.path.join(work_dir, "shots", f"trim_{i:02d}.mp4")
            _trim_video(video_local, duration, trimmed)
            trimmed_shots.append(trimmed)

        # --- 4. Concat shots with hard cuts ---
        logger.info(f"[{scene_id}] Concatenating {len(trimmed_shots)} shots...")
        action_sequence = os.path.join(work_dir, "action.mp4")
        if len(trimmed_shots) == 1:
            shutil.copy(trimmed_shots[0], action_sequence)
        else:
            _concat_shots_hard_cuts(trimmed_shots, action_sequence)

        # --- 5. Generate music track ---
        logger.info(f"[{scene_id}] Generating music track ({music_mood})...")
        # Get action sequence duration
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", action_sequence],
            capture_output=True, text=True, timeout=10,
        )
        import json as _json
        try:
            action_duration = float(_json.loads(probe.stdout).get("format", {}).get("duration", 60))
        except Exception:
            action_duration = 60.0

        music_path = os.path.join(work_dir, "music.mp3")
        music_ok = generate_music_track(music_mood, music_path, duration=action_duration + 2)
        if not music_ok:
            # Fallback: silent music
            _run_ffmpeg([
                "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={action_duration + 2}",
                "-c:a", "libmp3lame", "-q:a", "4", music_path,
            ], desc="silent music fallback")

        # --- 6. Mix video + music + narrator ---
        logger.info(f"[{scene_id}] Final trailer mix...")
        mixed = os.path.join(work_dir, "mixed.mp4")
        _apply_trailer_narrator_mix(action_sequence, music_path, narrator_lines, narrator_files, mixed)

        # --- 7. Add title + end title cards ---
        title_text = shot_list.get("title", "Untitled")
        tagline = shot_list.get("tagline", "")

        logger.info(f"[{scene_id}] Creating title cards...")
        title_card = os.path.join(work_dir, "title.mp4")
        end_card = os.path.join(work_dir, "end.mp4")
        _create_title_card(f"LEGO WORLDS presents\\n\\n{title_text}", title_card, duration=3.5)
        _create_title_card(f"{title_text}\\n\\nA film by {director_name}", end_card, duration=4.0)

        # --- 8. Final concat: title → mixed → end ---
        logger.info(f"[{scene_id}] Final assembly...")
        final_local = os.path.join(work_dir, "final.mp4")
        _concat_shots_hard_cuts([title_card, mixed, end_card], final_local)

        # --- 9. Thumbnail ---
        thumb_local = os.path.join(work_dir, "thumbnail.jpg")
        _extract_thumbnail(final_local, thumb_local)

        # --- 10. Upload ---
        logger.info(f"[{scene_id}] Uploading final trailer...")
        final_storage = f"scenes/{scene_id}/output/final.mp4"
        thumb_storage = f"scenes/{scene_id}/output/thumbnail.jpg"

        sb = get_supabase()
        with open(final_local, "rb") as f:
            sb.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
                final_storage, f.read(), {"content-type": "video/mp4", "upsert": "true"}
            )
        with open(thumb_local, "rb") as f:
            sb.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
                thumb_storage, f.read(), {"content-type": "image/jpeg", "upsert": "true"}
            )

        logger.info(f"[{scene_id}] Trailer complete!")
        return final_storage, thumb_storage

    finally:
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)
