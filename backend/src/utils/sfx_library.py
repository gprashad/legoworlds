"""
Bundled SFX library — generates simple sound effects using FFmpeg's built-in
audio synthesis. No external API needed.

Each SFX is generated on-the-fly as a short audio clip using FFmpeg's lavfi
audio sources (sine waves, noise, etc.) shaped to match the description.
"""

import os
import subprocess
import logging

logger = logging.getLogger(__name__)


def _generate_ffmpeg_audio(filter_expr: str, duration: float, output_path: str) -> bool:
    """Generate audio using FFmpeg lavfi filter."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", filter_expr,
        "-t", str(duration),
        "-c:a", "libmp3lame", "-q:a", "4",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    return result.returncode == 0


# Keyword → FFmpeg audio filter mappings
# These create simple but recognizable sound effects
SFX_RECIPES = {
    # Vehicle sounds
    "engine": ("anoisesrc=c=brown:r=44100:a=0.3,lowpass=f=200,tremolo=f=15:d=0.3", 3.0),
    "engine idling": ("anoisesrc=c=brown:r=44100:a=0.2,lowpass=f=150,tremolo=f=8:d=0.4", 3.0),
    "engine revving": ("anoisesrc=c=brown:r=44100:a=0.4,lowpass=f=300,tremolo=f=20:d=0.5", 2.0),
    "horn": ("sine=f=400:d=0.8,sine=f=500:d=0.8,amix=inputs=2", 1.0),
    "truck": ("anoisesrc=c=brown:r=44100:a=0.3,lowpass=f=120,tremolo=f=10:d=0.3", 3.0),
    "beep": ("sine=f=1000:d=0.3,apad=pad_dur=0.2,sine=f=1000:d=0.3", 1.0),
    "siren": ("sine=f=600:d=2,vibrato=f=2:d=0.5", 3.0),

    # Crowd / people
    "crowd": ("anoisesrc=c=pink:r=44100:a=0.25,bandpass=f=800:w=400,tremolo=f=3:d=0.4", 3.0),
    "crowd murmuring": ("anoisesrc=c=pink:r=44100:a=0.15,bandpass=f=600:w=300,tremolo=f=2:d=0.3", 3.0),
    "crowd cheering": ("anoisesrc=c=pink:r=44100:a=0.4,bandpass=f=1000:w=500,tremolo=f=5:d=0.5", 3.0),
    "cheer": ("anoisesrc=c=pink:r=44100:a=0.4,bandpass=f=1000:w=500,tremolo=f=5:d=0.5", 3.0),
    "gasp": ("anoisesrc=c=white:r=44100:a=0.3,bandpass=f=2000:w=1000,afade=t=out:d=0.5", 0.5),
    "footsteps": ("sine=f=100:d=0.1,apad=pad_dur=0.3,sine=f=120:d=0.1,apad=pad_dur=0.3,sine=f=110:d=0.1", 2.0),
    "whisper": ("anoisesrc=c=white:r=44100:a=0.05,bandpass=f=3000:w=1000", 2.0),

    # Impact / action
    "crash": ("anoisesrc=c=white:r=44100:a=0.8,afade=t=out:d=1.0,lowpass=f=500", 1.0),
    "explosion": ("anoisesrc=c=brown:r=44100:a=0.9,afade=t=out:d=1.5,lowpass=f=200", 1.5),
    "slam": ("anoisesrc=c=white:r=44100:a=0.7,afade=t=out:d=0.3,lowpass=f=300", 0.5),
    "bang": ("anoisesrc=c=white:r=44100:a=0.8,afade=t=out:d=0.4,lowpass=f=400", 0.5),
    "scrape": ("anoisesrc=c=white:r=44100:a=0.3,bandpass=f=3000:w=2000,tremolo=f=10:d=0.5", 2.0),
    "metal": ("anoisesrc=c=white:r=44100:a=0.3,bandpass=f=4000:w=2000,tremolo=f=8:d=0.4", 2.0),

    # Environment
    "wind": ("anoisesrc=c=pink:r=44100:a=0.2,lowpass=f=400,tremolo=f=0.5:d=0.3", 3.0),
    "rain": ("anoisesrc=c=white:r=44100:a=0.15,bandpass=f=5000:w=3000", 3.0),
    "thunder": ("anoisesrc=c=brown:r=44100:a=0.7,afade=t=in:d=0.3,afade=t=out:d=1.5,lowpass=f=150", 2.0),
    "construction": ("anoisesrc=c=white:r=44100:a=0.3,bandpass=f=2000:w=1500,tremolo=f=6:d=0.6", 3.0),
    "traffic": ("anoisesrc=c=brown:r=44100:a=0.2,lowpass=f=300,tremolo=f=3:d=0.3", 3.0),
    "city": ("anoisesrc=c=pink:r=44100:a=0.15,bandpass=f=500:w=400", 3.0),

    # Comedy / cartoon
    "boing": ("sine=f=300:d=0.3,vibrato=f=10:d=1.0,afade=t=out:d=0.3", 0.5),
    "pop": ("sine=f=800:d=0.05,afade=t=out:d=0.1", 0.2),
    "whoosh": ("anoisesrc=c=white:r=44100:a=0.4,bandpass=f=2000:w=1500,afade=t=in:d=0.1,afade=t=out:d=0.3", 0.5),
    "squeak": ("sine=f=2000:d=0.2,vibrato=f=20:d=0.5", 0.3),

    # Lego specific
    "brick": ("sine=f=1200:d=0.05,apad=pad_dur=0.1,sine=f=1400:d=0.05", 0.3),
    "click": ("sine=f=1500:d=0.03,apad=pad_dur=0.15,sine=f=1600:d=0.03", 0.4),
    "building": ("sine=f=1200:d=0.05,apad=pad_dur=0.2,sine=f=1400:d=0.05,apad=pad_dur=0.2,sine=f=1100:d=0.05", 1.0),

    # Misc
    "alarm": ("sine=f=800:d=0.5,sine=f=600:d=0.5,amix=inputs=2,tremolo=f=4:d=0.8", 2.0),
    "door": ("anoisesrc=c=brown:r=44100:a=0.5,afade=t=out:d=0.3,lowpass=f=200", 0.4),
    "tense": ("sine=f=80:d=3,tremolo=f=1:d=0.3", 3.0),
    "dramatic": ("sine=f=60:d=3,tremolo=f=0.5:d=0.4", 3.0),
    "suspense": ("sine=f=100:d=3,vibrato=f=0.3:d=0.5,tremolo=f=1:d=0.2", 3.0),
    "relief": ("sine=f=400:d=1,afade=t=out:d=1.0", 1.5),
    "sigh": ("anoisesrc=c=white:r=44100:a=0.1,bandpass=f=1500:w=500,afade=t=out:d=0.8", 1.0),
    "power down": ("sine=f=400:d=1.5,vibrato=f=0.5:d=1.0,afade=t=out:d=1.5", 2.0),
}


def _match_recipe(description: str) -> tuple[str, float] | None:
    """Find the best matching SFX recipe for a description."""
    desc_lower = description.lower()

    # Exact match
    if desc_lower in SFX_RECIPES:
        return SFX_RECIPES[desc_lower]

    # Keyword match — find the recipe whose key appears in the description
    best_match = None
    best_len = 0
    for key, recipe in SFX_RECIPES.items():
        if key in desc_lower and len(key) > best_len:
            best_match = recipe
            best_len = len(key)

    if best_match:
        return best_match

    # Partial word match
    desc_words = set(desc_lower.split())
    for key, recipe in SFX_RECIPES.items():
        key_words = set(key.split())
        if key_words & desc_words:
            return recipe

    return None


def generate_sfx(description: str, output_path: str) -> bool:
    """Generate a sound effect matching the description. Returns True if successful."""
    recipe = _match_recipe(description)
    if not recipe:
        logger.info(f"No SFX recipe for '{description}', skipping")
        return False

    filter_expr, duration = recipe
    success = _generate_ffmpeg_audio(filter_expr, duration, output_path)
    if success:
        logger.info(f"SFX generated: '{description}' → {os.path.basename(output_path)}")
    else:
        logger.warning(f"SFX generation failed for '{description}'")
    return success
