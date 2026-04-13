import os
import subprocess
import shutil
import time
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from src.api.auth import get_current_user
from src.supabase_client import get_supabase
from src.models import MediaRegister, MediaReorder
from src.config import SUPABASE_STORAGE_BUCKET
from src.stages.video_intake import process_video_intake
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scenes/{scene_id}/media", tags=["media"])

TEMP_BASE = os.getenv("TEMP_DIR", "/tmp/legoworlds")
MAX_STORAGE_SIZE = 45 * 1024 * 1024  # 45MB — under Supabase 50MB limit


def _verify_scene_ownership(scene_id: str, uid: str):
    sb = get_supabase()
    check = sb.table("scenes").select("id").eq("id", scene_id).eq("user_id", uid).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="Scene not found")


def _compress_video(input_path: str, output_path: str, target_size_mb: int = 40) -> bool:
    """Compress video to fit within storage limits. Keeps first 120s max."""
    try:
        # Get duration
        probe = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", input_path],
            capture_output=True, text=True, timeout=10,
        )
        import json
        duration = float(json.loads(probe.stdout).get("format", {}).get("duration", 60))
        duration = min(duration, 120)  # cap at 2 min

        # Target bitrate = target_size * 8 / duration (in bits/s)
        target_bitrate = int((target_size_mb * 8 * 1024 * 1024) / duration)
        video_bitrate = max(target_bitrate - 128000, 500000)  # reserve 128kbps for audio

        result = subprocess.run(
            ["ffmpeg", "-y", "-i", input_path,
             "-t", str(duration),
             "-c:v", "libx264", "-preset", "fast", "-b:v", str(video_bitrate),
             "-c:a", "aac", "-b:a", "128k",
             "-vf", "scale='min(1280,iw)':-2",
             "-movflags", "+faststart",
             output_path],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0 and os.path.exists(output_path):
            size = os.path.getsize(output_path)
            logger.info(f"Compressed video: {os.path.getsize(input_path)} → {size} bytes")
            return True
        else:
            logger.warning(f"Video compression failed: {result.stderr[-200:]}")
            return False
    except Exception as e:
        logger.warning(f"Video compression error: {e}")
        return False


@router.post("", status_code=201)
async def register_media(scene_id: str, body: MediaRegister, user: dict = Depends(get_current_user)):
    """Register media metadata after frontend uploads to Supabase Storage."""
    uid = user["sub"]
    _verify_scene_ownership(scene_id, uid)

    sb = get_supabase()
    result = sb.table("scene_media").insert({
        "scene_id": scene_id,
        "file_url": body.file_url,
        "file_type": body.file_type,
        "file_name": body.file_name,
        "file_size_bytes": body.file_size_bytes,
        "sort_order": body.sort_order,
        "source": body.source,
    }).execute()
    return result.data[0]


@router.post("/upload", status_code=201)
async def upload_media(
    scene_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    """Upload a file to Supabase Storage via the backend.
    Large videos are automatically compressed to fit storage limits.
    Videos are auto-processed: frames extracted + narration transcribed."""
    uid = user["sub"]
    _verify_scene_ownership(scene_id, uid)

    content = await file.read()
    if len(content) > 500 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 500MB)")

    content_type = file.content_type or "application/octet-stream"
    is_video = content_type.startswith("video/") or (
        file.filename and file.filename.lower().endswith((".mov", ".mp4", ".m4v", ".webm"))
    )
    file_type = "video" if is_video else "photo"

    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else ("mp4" if is_video else "jpg")
    base_name = file.filename or f"file.{ext}"

    # Compress large videos to fit Supabase storage limit
    if is_video and len(content) > MAX_STORAGE_SIZE:
        logger.info(f"[{scene_id}] Video {base_name} is {len(content)} bytes, compressing...")
        work_dir = os.path.join(TEMP_BASE, f"{scene_id}_compress")
        Path(work_dir).mkdir(parents=True, exist_ok=True)
        try:
            input_path = os.path.join(work_dir, f"original.{ext}")
            output_path = os.path.join(work_dir, "compressed.mp4")
            with open(input_path, "wb") as f:
                f.write(content)

            if _compress_video(input_path, output_path):
                with open(output_path, "rb") as f:
                    content = f.read()
                content_type = "video/mp4"
                ext = "mp4"
                base_name = base_name.rsplit(".", 1)[0] + ".mp4"
                logger.info(f"[{scene_id}] Compressed to {len(content)} bytes")
            else:
                logger.warning(f"[{scene_id}] Compression failed, trying original")
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    storage_path = f"scenes/{scene_id}/input/{int(time.time())}_{base_name}"

    sb = get_supabase()
    sb.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
        storage_path, content, {"content-type": content_type}
    )

    public_url = sb.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(storage_path)

    existing = sb.table("scene_media").select("id").eq("scene_id", scene_id).execute()
    sort_order = len(existing.data)

    result = sb.table("scene_media").insert({
        "scene_id": scene_id,
        "file_url": public_url,
        "file_type": file_type,
        "file_name": file.filename,
        "file_size_bytes": len(content),
        "sort_order": sort_order,
        "source": "upload",
    }).execute()

    media_record = result.data[0]

    # Auto-process videos: extract frames + transcribe narration
    if is_video:
        background_tasks.add_task(process_video_intake, scene_id, storage_path)
        media_record["processing"] = True

    return media_record


@router.delete("/{media_id}", status_code=204)
async def delete_media(scene_id: str, media_id: str, user: dict = Depends(get_current_user)):
    uid = user["sub"]
    _verify_scene_ownership(scene_id, uid)

    sb = get_supabase()
    sb.table("scene_media").delete().eq("id", media_id).eq("scene_id", scene_id).execute()
    return None


@router.patch("/reorder")
async def reorder_media(scene_id: str, body: MediaReorder, user: dict = Depends(get_current_user)):
    uid = user["sub"]
    _verify_scene_ownership(scene_id, uid)

    sb = get_supabase()
    for i, media_id in enumerate(body.media_ids):
        sb.table("scene_media").update({"sort_order": i}).eq("id", media_id).eq("scene_id", scene_id).execute()

    result = sb.table("scene_media").select("*").eq("scene_id", scene_id).order("sort_order").execute()
    return result.data
