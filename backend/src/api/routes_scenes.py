from fastapi import APIRouter, Depends, HTTPException
from src.api.auth import get_current_user
from src.supabase_client import get_supabase
from src.models import SceneCreate, SceneUpdate, SceneResponse

router = APIRouter(prefix="/api/scenes", tags=["scenes"])


@router.get("")
async def list_scenes(user: dict = Depends(get_current_user)):
    sb = get_supabase()
    uid = user["sub"]
    result = sb.table("scenes").select("*, scene_media(*)").eq("user_id", uid).order("updated_at", desc=True).execute()
    scenes = []
    for row in result.data:
        media = row.pop("scene_media", [])
        row["media"] = media
        scenes.append(row)
    return scenes


@router.post("", status_code=201)
async def create_scene(body: SceneCreate, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    uid = user["sub"]
    result = sb.table("scenes").insert({
        "user_id": uid,
        "title": body.title,
        "backstory": body.backstory,
        "director_name": body.director_name,
        "movie_style": body.movie_style,
    }).execute()
    return result.data[0]


@router.get("/{scene_id}")
async def get_scene(scene_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    uid = user["sub"]
    result = sb.table("scenes").select("*, scene_media(*)").eq("id", scene_id).eq("user_id", uid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Scene not found")
    row = result.data[0]
    row["media"] = row.pop("scene_media", [])
    return row


@router.patch("/{scene_id}")
async def update_scene(scene_id: str, body: SceneUpdate, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    uid = user["sub"]

    # Verify ownership
    check = sb.table("scenes").select("id").eq("id", scene_id).eq("user_id", uid).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="Scene not found")

    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = sb.table("scenes").update(updates).eq("id", scene_id).execute()
    return result.data[0]


@router.delete("/{scene_id}", status_code=204)
async def delete_scene(scene_id: str, user: dict = Depends(get_current_user)):
    sb = get_supabase()
    uid = user["sub"]

    # Verify ownership
    check = sb.table("scenes").select("id").eq("id", scene_id).eq("user_id", uid).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="Scene not found")

    # Delete related jobs first (no cascade on FK)
    sb.table("jobs").delete().eq("scene_id", scene_id).execute()
    # scene_media has ON DELETE CASCADE, but delete explicitly to be safe
    sb.table("scene_media").delete().eq("scene_id", scene_id).execute()
    sb.table("scenes").delete().eq("id", scene_id).execute()
    return None
