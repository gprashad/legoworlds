import logging
from datetime import datetime, timezone
from src.supabase_client import get_supabase
from src.config import SUPABASE_STORAGE_BUCKET
from src.stages.scene_analysis import analyze_scene
from src.stages.screenplay import generate_screenplay
from src.stages.shot_list import generate_shot_list
from src.stages.production import (
    generate_scene_videos, generate_scene_audio, cleanup_production_files,
    generate_shot_list_videos, generate_trailer_narration,
)
from src.stages.assembly import assemble_movie, assemble_trailer
from src.utils.music_library import pick_music_mood

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _update_scene(scene_id: str, **fields):
    sb = get_supabase()
    sb.table("scenes").update(fields).eq("id", scene_id).execute()


def _update_job(job_id: str, **fields):
    sb = get_supabase()
    sb.table("jobs").update(fields).eq("id", job_id).execute()


async def run_analysis_and_shot_list(scene_id: str, job_id: str):
    """NEW NOLAN FLOW: scene analysis + shot list generation.

    1. Claude Vision analyzes photos/video → scene_bible
    2. Claude generates shot list (6-10 shots) + trailer narration lines
    """
    sb = get_supabase()

    try:
        scene = sb.table("scenes").select("*").eq("id", scene_id).execute().data[0]
        backstory = scene.get("backstory", "")
        structured_description = scene.get("structured_description") or {}
        director_name = scene.get("director_name", "Cary")

        # Count photos for shot list generator
        media = sb.table("scene_media").select("id").eq("scene_id", scene_id).eq("file_type", "photo").execute()
        num_photos = len(media.data)

        # Stage 1: Scene Analysis
        _update_scene(scene_id, status="analyzing")
        _update_job(job_id, status="analyzing", current_stage="scene_analysis", progress_pct=10)
        logger.info(f"[{scene_id}] Starting scene analysis...")
        scene_bible = await analyze_scene(scene_id, backstory)

        _update_scene(scene_id, scene_bible=scene_bible)
        _update_job(job_id, progress_pct=45, stages_completed=["scene_analysis"])
        logger.info(f"[{scene_id}] Scene analysis complete")

        # Stage 2: Shot list + trailer narration
        _update_job(job_id, status="writing", current_stage="shot_list", progress_pct=50)
        logger.info(f"[{scene_id}] Generating shot list + trailer narration...")
        shot_list = await generate_shot_list(
            scene_bible=scene_bible,
            structured_description=structured_description,
            backstory=backstory,
            director_name=director_name,
            num_photos=num_photos,
        )

        _update_scene(
            scene_id,
            shot_list=shot_list,
            shot_list_version=scene.get("shot_list_version", 0) + 1,
            music_track=shot_list.get("music_mood", "tension_build"),
            status="screenplay_review",
        )
        _update_job(
            job_id, status="awaiting_approval", current_stage="screenplay_review",
            progress_pct=100,
            stages_completed=["scene_analysis", "shot_list"],
            completed_at=_now(),
        )
        logger.info(f"[{scene_id}] Shot list ready: {shot_list.get('title', '?')} — {len(shot_list.get('shots', []))} shots")

    except Exception as e:
        logger.error(f"[{scene_id}] Pipeline failed: {e}")
        _update_scene(scene_id, status="failed")
        _update_job(job_id, status="failed", error=str(e))
        raise


async def run_shot_list_revision(scene_id: str, job_id: str, feedback: str):
    """Revise shot list with director feedback."""
    sb = get_supabase()
    try:
        scene = sb.table("scenes").select("*").eq("id", scene_id).execute().data[0]
        scene_bible = scene.get("scene_bible")
        structured_description = scene.get("structured_description") or {}
        backstory = scene.get("backstory", "")
        director_name = scene.get("director_name", "Cary")

        if not scene_bible:
            raise ValueError("No scene bible — run analysis first")

        media = sb.table("scene_media").select("id").eq("scene_id", scene_id).eq("file_type", "photo").execute()
        num_photos = len(media.data)

        _update_scene(scene_id, status="analyzing", screenplay_feedback=feedback)
        _update_job(job_id, status="writing", current_stage="shot_list_revision", progress_pct=30)

        shot_list = await generate_shot_list(
            scene_bible=scene_bible,
            structured_description=structured_description,
            backstory=backstory,
            director_name=director_name,
            num_photos=num_photos,
            feedback=feedback,
        )

        _update_scene(
            scene_id,
            shot_list=shot_list,
            shot_list_version=scene.get("shot_list_version", 0) + 1,
            music_track=shot_list.get("music_mood", "tension_build"),
            status="screenplay_review",
        )
        _update_job(
            job_id, status="awaiting_approval", current_stage="screenplay_review",
            progress_pct=100, completed_at=_now(),
        )
    except Exception as e:
        logger.error(f"[{scene_id}] Revision failed: {e}")
        _update_scene(scene_id, status="failed")
        _update_job(job_id, status="failed", error=str(e))
        raise


async def run_trailer_production(scene_id: str, job_id: str):
    """NEW NOLAN FLOW: shot videos + narrator + music → trailer.

    1. Generate video for each shot (Kie.ai with Nolan-tight prompts)
    2. Generate trailer narration (single deep voice)
    3. Assemble trailer (quick cuts + music + narration)
    """
    sb = get_supabase()
    try:
        scene = sb.table("scenes").select("*").eq("id", scene_id).execute().data[0]
        shot_list = scene.get("shot_list")
        scene_bible = scene.get("scene_bible")
        director_name = scene.get("director_name", "Cary")

        if not shot_list or not scene_bible:
            raise ValueError("Missing shot_list or scene_bible")

        await cleanup_production_files(scene_id)

        shots = shot_list.get("shots", [])

        # --- Stage 1: Shot videos ---
        _update_scene(scene_id, status="producing")
        _update_job(job_id, status="producing", current_stage="video_generation", progress_pct=5)
        logger.info(f"[{scene_id}] Generating {len(shots)} shot videos (Nolan-tight)...")

        def on_video_progress(done: int, total: int):
            pct = 5 + int((done / total) * 50)  # 5-55%
            _update_job(job_id, progress_pct=pct, current_stage=f"video_scene_{done}_of_{total}")

        shot_videos = await generate_shot_list_videos(
            scene_id, shot_list, scene_bible, on_progress=on_video_progress,
        )
        _update_job(job_id, progress_pct=55, stages_completed=["video_generation"])
        logger.info(f"[{scene_id}] {len(shot_videos)} shot videos done")

        # --- Stage 2: Trailer narration ---
        _update_job(job_id, current_stage="narrator", progress_pct=60)
        logger.info(f"[{scene_id}] Generating trailer narration...")
        narrator_paths = await generate_trailer_narration(scene_id, shot_list)
        _update_job(
            job_id, progress_pct=75,
            stages_completed=["video_generation", "narrator"],
        )

        # --- Stage 3: Assembly ---
        _update_scene(scene_id, status="assembling")
        _update_job(job_id, status="assembling", current_stage="assembly", progress_pct=80)
        logger.info(f"[{scene_id}] Assembling trailer...")

        music_mood = pick_music_mood(shot_list.get("genre", ""), shot_list.get("mood", ""))

        final_video_path, _thumb = await assemble_trailer(
            scene_id=scene_id,
            shot_list=shot_list,
            shot_video_paths=shot_videos,
            narrator_paths=narrator_paths,
            music_mood=music_mood,
            director_name=director_name,
        )

        final_url = sb.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(final_video_path)

        _update_scene(scene_id, status="complete", final_video_url=final_url)
        _update_job(
            job_id, status="complete", current_stage="complete", progress_pct=100,
            stages_completed=["video_generation", "narrator", "assembly"],
            completed_at=_now(),
        )
        logger.info(f"[{scene_id}] Trailer complete! {final_url}")

    except Exception as e:
        logger.error(f"[{scene_id}] Trailer production failed: {e}")
        _update_scene(scene_id, status="failed")
        _update_job(job_id, status="failed", error=str(e))
        raise


async def run_analysis_and_screenplay(scene_id: str, job_id: str):
    """Run scene analysis + screenplay generation as a background task."""
    sb = get_supabase()

    try:
        scene = sb.table("scenes").select("*").eq("id", scene_id).execute().data[0]
        backstory = scene.get("backstory", "")
        director_name = scene.get("director_name", "Cary")

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
        director_name = scene.get("director_name", "Cary")
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


async def run_production(scene_id: str, job_id: str):
    """Run video generation + voice generation + assembly as a background task."""
    sb = get_supabase()

    try:
        scene = sb.table("scenes").select("*").eq("id", scene_id).execute().data[0]
        screenplay = scene.get("screenplay")
        scene_bible = scene.get("scene_bible")

        if not screenplay or not scene_bible:
            raise ValueError("Missing screenplay or scene bible")

        # Clean up any leftover files from previous attempts
        await cleanup_production_files(scene_id)

        total_scenes = len(screenplay.get("scenes", []))

        # --- Stage 3: Video Generation ---
        _update_scene(scene_id, status="producing")
        _update_job(job_id, status="producing", current_stage="video_generation", progress_pct=5)
        logger.info(f"[{scene_id}] Starting video generation...")

        def on_video_progress(done: int, total: int):
            pct = 5 + int((done / total) * 45)  # 5-50%
            _update_job(job_id, progress_pct=pct, current_stage=f"video_scene_{done}_of_{total}")

        video_paths = await generate_scene_videos(scene_id, screenplay, scene_bible=scene_bible, on_progress=on_video_progress)
        _update_job(job_id, progress_pct=50, stages_completed=["scene_analysis", "screenplay", "video_generation"])
        logger.info(f"[{scene_id}] Video generation complete ({len(video_paths)} clips)")

        # --- Stage 4: Voice Generation ---
        _update_job(job_id, current_stage="voice_generation", progress_pct=55)
        logger.info(f"[{scene_id}] Starting voice generation...")

        audio_paths = await generate_scene_audio(scene_id, screenplay, scene_bible)
        _update_job(
            job_id, progress_pct=75,
            stages_completed=["scene_analysis", "screenplay", "video_generation", "voice_generation"],
        )
        logger.info(f"[{scene_id}] Voice generation complete ({len(audio_paths)} files)")

        # --- Stage 5: Assembly ---
        _update_scene(scene_id, status="assembling")
        _update_job(job_id, status="assembling", current_stage="assembly", progress_pct=80)
        logger.info(f"[{scene_id}] Starting assembly...")

        final_video_path, thumbnail_path = await assemble_movie(
            scene_id, screenplay, video_paths, audio_paths,
        )

        # Get public URL for the final video
        final_url = sb.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(final_video_path)

        _update_scene(
            scene_id,
            status="complete",
            final_video_url=final_url,
        )
        _update_job(
            job_id,
            status="complete",
            current_stage="complete",
            progress_pct=100,
            stages_completed=[
                "scene_analysis", "screenplay", "video_generation",
                "voice_generation", "assembly",
            ],
            completed_at=_now(),
        )
        logger.info(f"[{scene_id}] Movie complete! URL: {final_url}")

    except Exception as e:
        logger.error(f"[{scene_id}] Production failed: {e}")
        _update_scene(scene_id, status="failed")
        _update_job(job_id, status="failed", error=str(e))
        raise


async def run_assembly_only(scene_id: str, job_id: str):
    """Re-run just the assembly step using existing production files in Storage."""
    sb = get_supabase()

    try:
        scene = sb.table("scenes").select("*").eq("id", scene_id).execute().data[0]
        screenplay = scene.get("screenplay")
        if not screenplay:
            raise ValueError("No screenplay found")

        # Discover existing production files in Storage
        video_files = sb.storage.from_(SUPABASE_STORAGE_BUCKET).list(f"scenes/{scene_id}/production/video")
        video_paths = [f"scenes/{scene_id}/production/video/{f['name']}" for f in video_files if f["name"].endswith(".mp4")]
        video_paths.sort()

        audio_files = sb.storage.from_(SUPABASE_STORAGE_BUCKET).list(f"scenes/{scene_id}/production/audio")
        audio_paths = {}
        for f in audio_files:
            name = f["name"]
            if name.endswith(".mp3"):
                key = name.replace(".mp3", "")
                audio_paths[key] = f"scenes/{scene_id}/production/audio/{name}"

        logger.info(f"[{scene_id}] Assembly retry: {len(video_paths)} videos, {len(audio_paths)} audio files")

        _update_scene(scene_id, status="assembling")
        _update_job(job_id, status="assembling", current_stage="assembly", progress_pct=80)

        final_video_path, thumbnail_path = await assemble_movie(
            scene_id, screenplay, video_paths, audio_paths,
        )

        final_url = sb.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(final_video_path)

        _update_scene(scene_id, status="complete", final_video_url=final_url)
        _update_job(
            job_id, status="complete", current_stage="complete", progress_pct=100,
            stages_completed=["video_generation", "voice_generation", "assembly"],
            completed_at=_now(),
        )
        logger.info(f"[{scene_id}] Assembly complete! URL: {final_url}")

    except Exception as e:
        logger.error(f"[{scene_id}] Assembly retry failed: {e}")
        _update_scene(scene_id, status="failed")
        _update_job(job_id, status="failed", error=str(e))
        raise


async def run_audio_and_assembly(scene_id: str, job_id: str):
    """Re-generate voices + SFX, then re-assemble using existing video clips."""
    sb = get_supabase()

    try:
        scene = sb.table("scenes").select("*").eq("id", scene_id).execute().data[0]
        screenplay = scene.get("screenplay")
        scene_bible = scene.get("scene_bible")
        if not screenplay or not scene_bible:
            raise ValueError("Missing screenplay or scene bible")

        # Find existing video clips
        video_files = sb.storage.from_(SUPABASE_STORAGE_BUCKET).list(f"scenes/{scene_id}/production/video")
        video_paths = [f"scenes/{scene_id}/production/video/{f['name']}" for f in video_files if f["name"].endswith(".mp4")]
        video_paths.sort()

        if not video_paths:
            raise ValueError("No video clips found — run full production first")

        # --- Re-generate all audio ---
        _update_scene(scene_id, status="producing")
        _update_job(job_id, status="producing", current_stage="voice_generation", progress_pct=10)
        logger.info(f"[{scene_id}] Re-generating voices + SFX...")

        # Clean old audio files
        try:
            old_audio = sb.storage.from_(SUPABASE_STORAGE_BUCKET).list(f"scenes/{scene_id}/production/audio")
            if old_audio:
                paths = [f"scenes/{scene_id}/production/audio/{f['name']}" for f in old_audio]
                sb.storage.from_(SUPABASE_STORAGE_BUCKET).remove(paths)
        except Exception:
            pass

        audio_paths = await generate_scene_audio(scene_id, screenplay, scene_bible)
        _update_job(job_id, progress_pct=60, current_stage="voice_generation",
                    stages_completed=["voice_generation"])
        logger.info(f"[{scene_id}] Audio re-generated ({len(audio_paths)} files)")

        # --- Re-assemble ---
        _update_scene(scene_id, status="assembling")
        _update_job(job_id, status="assembling", current_stage="assembly", progress_pct=70)
        logger.info(f"[{scene_id}] Re-assembling with new audio...")

        final_video_path, thumbnail_path = await assemble_movie(
            scene_id, screenplay, video_paths, audio_paths,
        )

        final_url = sb.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(final_video_path)

        _update_scene(scene_id, status="complete", final_video_url=final_url)
        _update_job(
            job_id, status="complete", current_stage="complete", progress_pct=100,
            stages_completed=["voice_generation", "assembly"],
            completed_at=_now(),
        )
        logger.info(f"[{scene_id}] Audio + assembly complete! URL: {final_url}")

    except Exception as e:
        logger.error(f"[{scene_id}] Audio retry failed: {e}")
        _update_scene(scene_id, status="failed")
        _update_job(job_id, status="failed", error=str(e))
        raise
