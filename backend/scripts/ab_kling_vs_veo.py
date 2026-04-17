"""Local A/B test: regenerate N shots from an existing scene on Kling 2.1 Pro
for side-by-side comparison against the Veo3 originals.

Does NOT touch Supabase Storage. Does NOT trigger the full pipeline.
Writes output to /tmp/ab_<scene_short>/{veo3,kling}/shot_NN.mp4.

Usage (from repo root):
    export KIE_API_KEY=...  # already in .env for the backend
    python backend/scripts/ab_kling_vs_veo.py <scene_id> [shot_numbers]

Examples:
    python backend/scripts/ab_kling_vs_veo.py e8b6d840-cbe9-477d-b010-1532d066c526
    python backend/scripts/ab_kling_vs_veo.py e8b6d840-...  1,2,3

Cost: $0.25 per shot on Kling 2.1 Pro. Default runs 3 shots = $0.75.
"""

import asyncio
import os
import sys
from pathlib import Path

# Make backend src importable when run from repo root
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

import httpx  # noqa: E402
from src.supabase_client import get_supabase  # noqa: E402
from src.config import SUPABASE_STORAGE_BUCKET  # noqa: E402
from src.stages.production import (  # noqa: E402
    _submit_video_generation,
    _poll_video,
    _download_bytes,
    build_nolan_shot_prompt,
    LEGO_NEGATIVE_PROMPT,
    KIE_VIDEO_MODEL,
    KLING_CFG_SCALE,
)


async def _get_scene_photo_urls(scene_id: str) -> list[str]:
    """Duplicate of production._get_photo_urls so we don't run under its event loop."""
    sb = get_supabase()
    folder = f"scenes/{scene_id}/input"
    files = sb.storage.from_(SUPABASE_STORAGE_BUCKET).list(folder)
    urls = []
    for f in files:
        name = f["name"]
        if name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
            url = sb.storage.from_(SUPABASE_STORAGE_BUCKET).get_public_url(f"{folder}/{name}")
            urls.append(url)
    return urls


async def _download_existing_veo3_shot(scene_id: str, shot_num: int, out_path: Path) -> bool:
    """Pull the existing Veo3-generated shot from Supabase Storage for comparison."""
    sb = get_supabase()
    storage_path = f"scenes/{scene_id}/production/video/shot_{shot_num:02d}.mp4"
    try:
        data = sb.storage.from_(SUPABASE_STORAGE_BUCKET).download(storage_path)
    except Exception as e:
        print(f"  [veo3] shot_{shot_num:02d}.mp4 not in storage: {e}")
        return False
    out_path.write_bytes(data)
    print(f"  [veo3] saved {out_path.name} ({len(data)} bytes)")
    return True


async def regen_on_kling(
    shot: dict,
    scene_bible: dict,
    photo_urls: list[str],
    out_path: Path,
) -> dict:
    """Submit one shot to Kling, download, save. Return stats."""
    shot_num = shot.get("shot_number", "?")
    prompt = build_nolan_shot_prompt(shot, scene_bible)

    ref_idx = shot.get("reference_photo_index", 0)
    if ref_idx is None or ref_idx >= len(photo_urls) or ref_idx < 0:
        ref_idx = 0
    ref_photos = [photo_urls[ref_idx]]
    if len(photo_urls) > 1 and ref_idx != 0:
        ref_photos.append(photo_urls[0])

    print(f"  [kling] submitting shot_{shot_num:02d} (ref photo idx {ref_idx}, cfg_scale {KLING_CFG_SCALE})...")
    task_id, backend = await _submit_video_generation(
        prompt, ref_photos, negative_prompt=LEGO_NEGATIVE_PROMPT
    )
    print(f"  [kling] task_id={task_id} backend={backend} — polling...")
    video_url = await _poll_video(task_id, backend=backend)
    print(f"  [kling] ready: {video_url[:80]}...")
    video_bytes = await _download_bytes(video_url)
    out_path.write_bytes(video_bytes)
    print(f"  [kling] saved {out_path.name} ({len(video_bytes)} bytes)")
    return {"shot_number": shot_num, "bytes": len(video_bytes), "url": video_url}


async def main(scene_id: str, shot_numbers: list[int]):
    sb = get_supabase()
    row = sb.table("scenes").select("shot_list,scene_bible,director_name").eq("id", scene_id).execute()
    if not row.data:
        raise SystemExit(f"Scene {scene_id} not found in DB")
    scene = row.data[0]
    shot_list = scene["shot_list"]
    scene_bible = scene["scene_bible"]

    if not shot_list or not scene_bible:
        raise SystemExit(f"Scene {scene_id} has no shot_list or scene_bible")

    shots_by_num = {s.get("shot_number", i + 1): s for i, s in enumerate(shot_list["shots"])}
    print(f"Scene {scene_id[:8]}… has {len(shots_by_num)} shots, director={scene.get('director_name')}")
    print(f"Using KIE_VIDEO_MODEL={KIE_VIDEO_MODEL}, KLING_CFG_SCALE={KLING_CFG_SCALE}")
    print()

    short_id = scene_id[:8]
    out_root = Path(f"/tmp/ab_{short_id}")
    veo3_dir = out_root / "veo3"
    kling_dir = out_root / "kling"
    veo3_dir.mkdir(parents=True, exist_ok=True)
    kling_dir.mkdir(parents=True, exist_ok=True)

    photo_urls = await _get_scene_photo_urls(scene_id)
    if not photo_urls:
        raise SystemExit("No input photos found for this scene")
    print(f"Found {len(photo_urls)} reference photos.\n")

    results = []
    for num in shot_numbers:
        shot = shots_by_num.get(num)
        if not shot:
            print(f"Shot {num}: not in shot_list, skipping")
            continue
        print(f"=== Shot {num}: {shot.get('type', '?')} — {shot.get('subject', '?')} ===")

        veo_path = veo3_dir / f"shot_{num:02d}.mp4"
        kling_path = kling_dir / f"shot_{num:02d}.mp4"

        await _download_existing_veo3_shot(scene_id, num, veo_path)
        try:
            stats = await regen_on_kling(shot, scene_bible, photo_urls, kling_path)
            results.append(stats)
        except Exception as e:
            print(f"  [kling] FAILED shot_{num:02d}: {e}")
        print()

    print("=" * 60)
    print(f"A/B output in: {out_root}")
    print(f"  Veo3 originals: {veo3_dir}")
    print(f"  Kling regens:   {kling_dir}")
    print()
    print("Compare side-by-side with (macOS):")
    print(f"  open {veo3_dir} {kling_dir}")
    print(f"\nEstimated Kling spend: ${len(results) * 0.25:.2f}")


def _parse_shot_numbers(arg: str) -> list[int]:
    return [int(x.strip()) for x in arg.split(",") if x.strip()]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    scene_id = sys.argv[1]
    shot_numbers = _parse_shot_numbers(sys.argv[2]) if len(sys.argv) > 2 else [1, 2, 3]
    asyncio.run(main(scene_id, shot_numbers))
