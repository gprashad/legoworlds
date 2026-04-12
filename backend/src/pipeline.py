import logging
from datetime import datetime, timezone
from src.supabase_client import get_supabase
from src.stages.scene_analysis import analyze_scene
from src.stages.screenplay import generate_screenplay

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _update_scene(scene_id: str, **fields):
    sb = get_supabase()
    sb.table("scenes").update(fields).eq("id", scene_id).execute()


def _update_job(job_id: str, **fields):
    sb = get_supabase()
    sb.table("jobs").update(fields).eq("id", job_id).execute()


async def run_analysis_and_screenplay(scene_id: str, job_id: str):
    """Run scene analysis + screenplay generation as a background task."""
    sb = get_supabase()

    try:
        # Get scene data
        scene = sb.table("scenes").select("*").eq("id", scene_id).execute().data[0]
        backstory = scene.get("backstory", "")
        director_name = scene.get("director_name", "Jackson")

        # --- Stage 1: Scene Analysis ---
        _update_scene(scene_id, status="analyzing")
        _update_job(job_id, status="analyzing", current_stage="scene_analysis", progress_pct=10)
        logger.info(f"[{scene_id}] Starting scene analysis...")

        scene_bible = await analyze_scene(scene_id, backstory)

        _update_scene(scene_id, scene_bible=scene_bible)
        _update_job(job_id, progress_pct=40, stages_completed=["scene_analysis"])
        logger.info(f"[{scene_id}] Scene analysis complete")

        # --- Stage 2: Screenplay ---
        _update_job(job_id, status="writing", current_stage="screenplay", progress_pct=50)
        logger.info(f"[{scene_id}] Generating screenplay...")

        screenplay = await generate_screenplay(scene_bible, backstory, director_name)

        _update_scene(
            scene_id,
            screenplay=screenplay,
            screenplay_version=scene.get("screenplay_version", 0) + 1,
            status="screenplay_review",
        )
        _update_job(
            job_id,
            status="awaiting_approval",
            current_stage="screenplay_review",
            progress_pct=100,
            stages_completed=["scene_analysis", "screenplay"],
            completed_at=_now(),
        )
        logger.info(f"[{scene_id}] Screenplay ready for review")

    except Exception as e:
        logger.error(f"[{scene_id}] Pipeline failed: {e}")
        _update_scene(scene_id, status="failed")
        _update_job(job_id, status="failed", error=str(e))
        raise


async def run_screenplay_revision(scene_id: str, job_id: str, feedback: str):
    """Re-generate screenplay with director feedback."""
    sb = get_supabase()

    try:
        scene = sb.table("scenes").select("*").eq("id", scene_id).execute().data[0]
        backstory = scene.get("backstory", "")
        director_name = scene.get("director_name", "Jackson")
        scene_bible = scene.get("scene_bible")

        if not scene_bible:
            raise ValueError("No scene bible found — run analysis first")

        _update_scene(scene_id, status="analyzing", screenplay_feedback=feedback)
        _update_job(job_id, status="writing", current_stage="screenplay_revision", progress_pct=30)
        logger.info(f"[{scene_id}] Revising screenplay with feedback...")

        screenplay = await generate_screenplay(scene_bible, backstory, director_name, feedback=feedback)

        _update_scene(
            scene_id,
            screenplay=screenplay,
            screenplay_version=scene.get("screenplay_version", 0) + 1,
            status="screenplay_review",
        )
        _update_job(
            job_id,
            status="awaiting_approval",
            current_stage="screenplay_review",
            progress_pct=100,
            stages_completed=["scene_analysis", "screenplay", "screenplay_revision"],
            completed_at=_now(),
        )
        logger.info(f"[{scene_id}] Revised screenplay ready for review")

    except Exception as e:
        logger.error(f"[{scene_id}] Revision failed: {e}")
        _update_scene(scene_id, status="failed")
        _update_job(job_id, status="failed", error=str(e))
        raise
