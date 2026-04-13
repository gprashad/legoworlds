from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from src.api.auth import get_current_user
from src.supabase_client import get_supabase
from src.models import MediaRegister, MediaReorder
from src.config import SUPABASE_STORAGE_BUCKET
from src.stages.video_intake import process_video_intake
import time

router = APIRouter(prefix="/api/scenes/{scene_id}/media", tags=["media"])


def _verify_scene_ownership(scene_id: str, uid: str):
    sb = get_supabase()
    check = sb.table("scenes").select("id").eq("id", scene_id).eq("user_id", uid).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="Scene not found")


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
    """Upload a file to Supabase Storage via the backend (bypasses RLS).
    Videos are auto-processed: frames extracted + narration transcribed."""
    uid = user["sub"]
    _verify_scene_ownership(scene_id, uid)

    content = await file.read()
    if len(content) > 500 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 500MB)")

    content_type = file.content_type or "application/octet-stream"
    is_video = content_type.startswith("video/")
    file_type = "video" if is_video else "photo"

    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else ("mp4" if is_video else "jpg")
    storage_path = f"scenes/{scene_id}/input/{int(time.time())}_{file.filename or f'file.{ext}'}"

    sb = get_supabase()
    sb.storage.from_(SUPABASE_STORAGE_BUCKET).upload(
        storage_path, content, {"content-type": content_type}
    )

    public_url = sb.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(storage_path)

    # Get current media count for sort order
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
