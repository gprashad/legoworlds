from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from src.api.auth import get_current_user
from src.supabase_client import get_supabase
from src.pipeline import (
    run_analysis_and_screenplay, run_screenplay_revision, run_production,
    run_assembly_only, run_audio_and_assembly,
    run_analysis_and_shot_list, run_shot_list_revision, run_trailer_production,
)

router = APIRouter(prefix="/api/scenes/{scene_id}", tags=["pipeline"])


class ReviseRequest(BaseModel):
    feedback: str


def _get_scene_or_404(scene_id: str, uid: str) -> dict:
    sb = get_supabase()
    result = sb.table("scenes").select("*").eq("id", scene_id).eq("user_id", uid).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Scene not found")
    return result.data[0]


def _create_job(scene_id: str) -> str:
    sb = get_supabase()
    result = sb.table("jobs").insert({
        "scene_id": scene_id,
        "status": "pending",
        "current_stage": "queued",
        "progress_pct": 0,
    }).execute()
    return result.data[0]["id"]


@router.post("/analyze")
async def trigger_analysis(
    scene_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Trigger scene analysis + shot list generation (Nolan flow)."""
    scene = _get_scene_or_404(scene_id, user["sub"])

    if scene["status"] not in ("draft", "ready", "failed"):
        raise HTTPException(status_code=400, detail=f"Cannot analyze scene in '{scene['status']}' status")

    # Check requirements: 2+ photos, and EITHER structured_description OR backstory 20+ chars
    sb = get_supabase()
    media = sb.table("scene_media").select("id").eq("scene_id", scene_id).eq("file_type", "photo").execute()
    if len(media.data) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 photos")

    has_structured = bool(scene.get("structured_description"))
    has_backstory = scene.get("backstory") and len(scene["backstory"]) >= 20
    if not has_structured and not has_backstory:
        raise HTTPException(status_code=400, detail="Need a description (what's the movie about, who's in it, what happens)")

    job_id = _create_job(scene_id)
    background_tasks.add_task(run_analysis_and_shot_list, scene_id, job_id)

    return {"job_id": job_id, "status": "started"}


@router.post("/revise")
async def revise_shot_list(
    scene_id: str,
    body: ReviseRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Revise shot list with director feedback."""
    scene = _get_scene_or_404(scene_id, user["sub"])

    if scene["status"] != "screenplay_review":
        raise HTTPException(status_code=400, detail="Scene must be in screenplay_review status")
    if not scene.get("scene_bible"):
        raise HTTPException(status_code=400, detail="No scene bible — run analysis first")

    job_id = _create_job(scene_id)
    background_tasks.add_task(run_shot_list_revision, scene_id, job_id, body.feedback)

    return {"job_id": job_id, "status": "revising"}


@router.post("/greenlight")
async def greenlight_shot_list(
    scene_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Approve shot list and trigger trailer production."""
    scene = _get_scene_or_404(scene_id, user["sub"])

    if scene["status"] != "screenplay_review":
        raise HTTPException(status_code=400, detail="Scene must be in screenplay_review status")
    if not scene.get("shot_list"):
        raise HTTPException(status_code=400, detail="No shot list to approve")

    sb = get_supabase()
    sb.table("scenes").update({"status": "approved"}).eq("id", scene_id).execute()

    job_id = _create_job(scene_id)
    background_tasks.add_task(run_trailer_production, scene_id, job_id)

    return {"job_id": job_id, "status": "producing", "message": "Rolling camera — trailer in production."}


@router.post("/retry-audio")
async def retry_audio(
    scene_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Re-generate voices + SFX and re-assemble, keeping existing video clips."""
    _get_scene_or_404(scene_id, user["sub"])
    job_id = _create_job(scene_id)
    background_tasks.add_task(run_audio_and_assembly, scene_id, job_id)
    return {"job_id": job_id, "status": "producing"}


@router.post("/retry-assembly")
async def retry_assembly(
    scene_id: str,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Re-run just the assembly step using existing production assets."""
    scene = _get_scene_or_404(scene_id, user["sub"])
    job_id = _create_job(scene_id)
    sb = get_supabase()
    sb.table("scenes").update({"status": "assembling"}).eq("id", scene_id).execute()
    background_tasks.add_task(run_assembly_only, scene_id, job_id)
    return {"job_id": job_id, "status": "assembling"}


@router.get("/status")
async def get_pipeline_status(
    scene_id: str,
    user: dict = Depends(get_current_user),
):
    """Get current pipeline status for a scene."""
    _get_scene_or_404(scene_id, user["sub"])

    sb = get_supabase()
    # Get the most recent job
    result = sb.table("jobs").select("*").eq("scene_id", scene_id).order("created_at", desc=True).limit(1).execute()

    if not result.data:
        return {"job": None, "status": "no_jobs"}

    job = result.data[0]
    # Also get current scene status
    scene = sb.table("scenes").select("status, screenplay").eq("id", scene_id).execute().data[0]

    return {
        "job": job,
        "scene_status": scene["status"],
        "has_screenplay": scene.get("screenplay") is not None,
    }
