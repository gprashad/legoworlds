from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from src.api.auth import get_current_user
from src.supabase_client import get_supabase
from src.pipeline import run_analysis_and_screenplay, run_screenplay_revision

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
    """Trigger scene analysis + screenplay generation."""
    scene = _get_scene_or_404(scene_id, user["sub"])

    if scene["status"] not in ("draft", "ready", "failed"):
        raise HTTPException(status_code=400, detail=f"Cannot analyze scene in '{scene['status']}' status")

    # Check requirements: 2+ photos, backstory 20+ chars
    sb = get_supabase()
    media = sb.table("scene_media").select("id").eq("scene_id", scene_id).eq("file_type", "photo").execute()
    if len(media.data) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 photos")
    if not scene.get("backstory") or len(scene["backstory"]) < 20:
        raise HTTPException(status_code=400, detail="Backstory must be at least 20 characters")

    job_id = _create_job(scene_id)
    background_tasks.add_task(run_analysis_and_screenplay, scene_id, job_id)

    return {"job_id": job_id, "status": "started"}


@router.post("/revise")
async def revise_screenplay(
    scene_id: str,
    body: ReviseRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Revise screenplay with director feedback."""
    scene = _get_scene_or_404(scene_id, user["sub"])

    if scene["status"] != "screenplay_review":
        raise HTTPException(status_code=400, detail="Scene must be in screenplay_review status")
    if not scene.get("scene_bible"):
        raise HTTPException(status_code=400, detail="No scene bible — run analysis first")

    job_id = _create_job(scene_id)
    background_tasks.add_task(run_screenplay_revision, scene_id, job_id, body.feedback)

    return {"job_id": job_id, "status": "revising"}


@router.post("/greenlight")
async def greenlight_screenplay(
    scene_id: str,
    user: dict = Depends(get_current_user),
):
    """Approve screenplay and mark scene as approved for production."""
    scene = _get_scene_or_404(scene_id, user["sub"])

    if scene["status"] != "screenplay_review":
        raise HTTPException(status_code=400, detail="Scene must be in screenplay_review status")
    if not scene.get("screenplay"):
        raise HTTPException(status_code=400, detail="No screenplay to approve")

    sb = get_supabase()
    sb.table("scenes").update({"status": "approved"}).eq("id", scene_id).execute()

    return {"status": "approved", "message": "Screenplay approved! Production will begin soon."}


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
