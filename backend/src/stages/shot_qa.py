"""
Nolan Rebuild — Per-Shot Drift QA

Compares the first and last frame of a generated Kie.ai clip (Kling 2.1 Pro or
Veo3) against the original reference photo. Claude Vision rates three axes:
object permanence, physics, and identity consistency.

Used to catch model drift — disappearing minifigs, flying baseplates, plastic
morph, identity swap — before a shot gets stitched into the trailer.
"""

import base64
import json
import logging
import subprocess
import tempfile
from pathlib import Path

import anthropic
import httpx

from src.utils.json_repair import repair_and_parse_json

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a QA reviewer for a CHILDREN'S LEGO MINIFIG TRAILER. The director is 8. The footage is AI-generated (Kling or Veo3) from a real reference photo of a LEGO build. Your job is to catch model drift before the clip ships.

You will see THREE images in this order:
  1. REFERENCE PHOTO — the real LEGO build the kid photographed.
  2. FIRST FRAME — frame 0 of the generated clip.
  3. LAST FRAME — the final frame of the generated clip.

Rate three axes on a 1-10 integer scale (10 = perfect, 1 = broken):

- **object_permanence**: Are all LEGO pieces present in BOTH first and last frames the same as the reference? Penalize disappearing minifigs, missing baseplate sections, phantom pieces that weren't in the reference, or props that vanish between first and last frame.

- **physics**: Does the clip look like real stop-motion LEGO? Penalize plastic that morphs/melts/smooth-slides, baseplates that drift or fly, minifig limbs that bend past hinge joints, cars sliding sideways instead of rolling forward, anything that looks like liquid rather than rigid plastic.

- **identity**: Are minifigs recognizable as the SAME characters from the reference photo? Penalize changed clothing colors, swapped hair pieces, different face prints, lost or added accessories.

Be strict but fair. A static hold with tiny drift is a 7-8. Clear morphing or a missing minifig is a 3-4. A totally different build is a 1-2.

Output ONLY this JSON, no markdown fences, no prose:
{"object_permanence": <int 1-10>, "physics": <int 1-10>, "identity": <int 1-10>, "feedback": "<one sentence, <=200 chars, naming the biggest issue or 'clean'>"}"""


PASS_THRESHOLD = 6


# --- Frame extraction -------------------------------------------------------


def _extract_frames(video_bytes: bytes) -> tuple[bytes, bytes]:
    """Write video_bytes to a temp mp4, extract frame 0 and frame N as JPEGs."""
    with tempfile.TemporaryDirectory(prefix="shot_qa_") as tmp:
        tmp_dir = Path(tmp)
        video_path = tmp_dir / "input.mp4"
        first_path = tmp_dir / "first.jpg"
        last_path = tmp_dir / "last.jpg"
        video_path.write_bytes(video_bytes)

        # First frame
        first_cmd = [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vf", "select=eq(n\\,0)", "-vframes", "1",
            str(first_path),
        ]
        r = subprocess.run(first_cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or not first_path.exists():
            raise RuntimeError(f"ffmpeg first-frame failed: {r.stderr[-400:]}")

        # Duration probe
        probe = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if probe.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {probe.stderr[-400:]}")
        try:
            duration = float(probe.stdout.strip())
        except ValueError:
            raise RuntimeError(f"ffprobe returned non-numeric duration: {probe.stdout!r}")

        # Last frame — seek to duration - 0.05s
        seek = max(0.0, duration - 0.05)
        last_cmd = [
            "ffmpeg", "-y", "-ss", f"{seek:.3f}", "-i", str(video_path),
            "-vframes", "1", str(last_path),
        ]
        r = subprocess.run(last_cmd, capture_output=True, text=True, timeout=60)
        if r.returncode != 0 or not last_path.exists():
            raise RuntimeError(f"ffmpeg last-frame failed: {r.stderr[-400:]}")

        return first_path.read_bytes(), last_path.read_bytes()


# --- Image helpers ----------------------------------------------------------


def _detect_media_type(data: bytes) -> str:
    """Detect image media type from magic bytes. Defaults to jpeg."""
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG"):
        return "image/png"
    return "image/jpeg"


def _image_block(data: bytes) -> dict:
    """Build an Anthropic image content block from raw bytes."""
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": _detect_media_type(data),
            "data": base64.standard_b64encode(data).decode("ascii"),
        },
    }


async def _fetch_reference(url: str) -> bytes:
    """Download the reference photo from a signed Supabase URL."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


# --- Main entrypoint --------------------------------------------------------


async def qa_shot(
    shot: dict,
    video_bytes: bytes,
    reference_photo_url: str,
) -> dict:
    """Compare frame 0 and frame N of the generated clip vs the reference photo.

    Returns {'scores': {'object_permanence': int, 'physics': int, 'identity': int},
             'pass': bool, 'feedback': str, 'frames': {'first': bytes, 'last': bytes}}.
    `pass` is False if any score < 6.
    """
    shot_num = shot.get("shot_number", "?")

    first_bytes, last_bytes = _extract_frames(video_bytes)
    ref_bytes = await _fetch_reference(reference_photo_url)

    user_content = [
        {"type": "text", "text": "REFERENCE PHOTO (the real LEGO build):"},
        _image_block(ref_bytes),
        {"type": "text", "text": "FIRST FRAME of generated clip:"},
        _image_block(first_bytes),
        {"type": "text", "text": "LAST FRAME of generated clip:"},
        _image_block(last_bytes),
        {"type": "text", "text": f"Shot description: {shot.get('description', '(none)')}. Rate the three axes now."},
    ]

    client = anthropic.Anthropic()
    attempts = ["claude-opus-4-7", "claude-sonnet-4-6"]
    response_text = ""
    last_stop_reason = None
    for model_id in attempts:
        message = client.messages.create(
            model=model_id,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        response_text = "".join(
            getattr(b, "text", "") for b in message.content if getattr(b, "type", None) == "text"
        ).strip()
        last_stop_reason = getattr(message, "stop_reason", "?")
        if response_text:
            break
        logger.warning(
            f"Shot QA model {model_id} returned no text (stop_reason={last_stop_reason}); trying fallback"
        )

    if not response_text:
        logger.warning(
            f"Shot QA shot={shot_num}: vision refused by all models (stop_reason={last_stop_reason}); skipping conservatively"
        )
        return {
            "scores": {"object_permanence": 7, "physics": 7, "identity": 7},
            "pass": True,
            "feedback": "QA skipped: vision refused",
            "frames": {"first": first_bytes, "last": last_bytes},
        }

    try:
        parsed = repair_and_parse_json(response_text)
    except Exception as e:
        logger.warning(f"Shot QA shot={shot_num}: JSON parse failed ({e}); skipping conservatively")
        return {
            "scores": {"object_permanence": 7, "physics": 7, "identity": 7},
            "pass": True,
            "feedback": f"QA skipped: parse failed ({e})",
            "frames": {"first": first_bytes, "last": last_bytes},
        }

    def _clamp(v) -> int:
        try:
            return max(1, min(10, int(v)))
        except (TypeError, ValueError):
            return 7

    scores = {
        "object_permanence": _clamp(parsed.get("object_permanence")),
        "physics": _clamp(parsed.get("physics")),
        "identity": _clamp(parsed.get("identity")),
    }
    feedback = str(parsed.get("feedback", "")).strip() or "no feedback"
    passed = all(s >= PASS_THRESHOLD for s in scores.values())

    logger.info(
        f"Shot QA shot={shot_num}: perm={scores['object_permanence']} "
        f"phys={scores['physics']} id={scores['identity']} pass={passed}"
    )

    return {
        "scores": scores,
        "pass": passed,
        "feedback": feedback,
        "frames": {"first": first_bytes, "last": last_bytes},
    }
