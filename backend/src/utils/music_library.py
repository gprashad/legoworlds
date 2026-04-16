"""
Trailer music library — FFmpeg-synthesized cinematic music loops.

Generates simple but evocative trailer music tracks matching different moods.
No external API, no licensing issues — pure FFmpeg audio synthesis.
"""

import os
import subprocess
import logging

logger = logging.getLogger(__name__)


# Each recipe generates a layered trailer-style music bed
# Uses multiple sine waves + noise shaping to create orchestral-feeling loops
MUSIC_RECIPES = {
    "tension_build": {
        "description": "slow-building tension, low strings + percussion hits",
        "duration": 60,
        "filter": (
            # Low drone
            "sine=f=55:d=60[bass];"
            "sine=f=82.5:d=60[bass2];"
            # Middle pulse
            "sine=f=165:d=60,tremolo=f=0.5:d=0.3[pulse];"
            # Rising tension
            "sine=f=220:d=60,tremolo=f=0.25:d=0.5[tension];"
            # Percussion hits every 4s
            "anoisesrc=c=brown:a=0.4:d=60,lowpass=f=100,afade=t=in:d=0.05:st=0,afade=t=out:d=0.3:st=0.3[hit];"
            "[bass][bass2][pulse][tension]amix=inputs=4:duration=longest,volume=0.3[bed]"
        ),
        "out": "[bed]",
    },
    "action_drive": {
        "description": "driving action, fast percussion + brass stabs",
        "duration": 60,
        "filter": (
            # Fast pulse bass
            "sine=f=82.5:d=60,tremolo=f=4:d=0.6[bass];"
            # Mid brass-like
            "sine=f=220:d=60,tremolo=f=2:d=0.4[brass];"
            "sine=f=330:d=60,tremolo=f=2:d=0.4[brass2];"
            # High stabs
            "sine=f=440:d=60,tremolo=f=1:d=0.8[stab];"
            "[bass][brass][brass2][stab]amix=inputs=4:duration=longest,volume=0.25[bed]"
        ),
        "out": "[bed]",
    },
    "mystery": {
        "description": "mysterious, sparse, piano-like chimes",
        "duration": 60,
        "filter": (
            # Deep drone
            "sine=f=65:d=60[bass];"
            # Sparse chimes
            "sine=f=523:d=60,tremolo=f=0.3:d=0.7[chime1];"
            "sine=f=784:d=60,tremolo=f=0.2:d=0.8[chime2];"
            # Ambient pad
            "sine=f=196:d=60,tremolo=f=0.15:d=0.5[pad];"
            "[bass][chime1][chime2][pad]amix=inputs=4:duration=longest,volume=0.25[bed]"
        ),
        "out": "[bed]",
    },
    "comedy_bounce": {
        "description": "light, bouncy, playful",
        "duration": 60,
        "filter": (
            # Bouncy bass
            "sine=f=130:d=60,tremolo=f=3:d=0.7[bass];"
            # Bright melody
            "sine=f=392:d=60,tremolo=f=2:d=0.5[mel];"
            "sine=f=523:d=60,tremolo=f=2.5:d=0.5[mel2];"
            # Light percussion
            "sine=f=784:d=60,tremolo=f=4:d=0.3[perc];"
            "[bass][mel][mel2][perc]amix=inputs=4:duration=longest,volume=0.2[bed]"
        ),
        "out": "[bed]",
    },
    "epic_reveal": {
        "description": "big, epic, orchestral swell",
        "duration": 60,
        "filter": (
            # Deep low
            "sine=f=55:d=60[sub];"
            "sine=f=82.5:d=60[bass];"
            # Middle brass
            "sine=f=165:d=60,tremolo=f=0.5:d=0.4[brass1];"
            "sine=f=220:d=60,tremolo=f=0.5:d=0.4[brass2];"
            # Soaring high
            "sine=f=330:d=60,tremolo=f=0.25:d=0.6[soar];"
            "sine=f=440:d=60,tremolo=f=0.3:d=0.5[soar2];"
            "[sub][bass][brass1][brass2][soar][soar2]amix=inputs=6:duration=longest,volume=0.28[bed]"
        ),
        "out": "[bed]",
    },
}


def generate_music_track(mood: str, output_path: str, duration: float = 60) -> bool:
    """Generate a trailer music track for a given mood."""
    recipe = MUSIC_RECIPES.get(mood, MUSIC_RECIPES["tension_build"])

    # Build the filter with duration adjustment
    filter_expr = recipe["filter"].replace("d=60", f"d={duration}")
    # Add final fade in/out for smooth loop
    final_filter = (
        f"{filter_expr};"
        f"{recipe['out']}afade=t=in:d=1.5,afade=t=out:st={duration - 2}:d=2[final]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=stereo",
        "-filter_complex", final_filter,
        "-map", "[final]",
        "-t", str(duration),
        "-c:a", "libmp3lame", "-q:a", "4",
        output_path,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and os.path.exists(output_path):
            logger.info(f"Generated music track '{mood}' ({os.path.getsize(output_path)} bytes)")
            return True
        else:
            logger.warning(f"Music generation failed for '{mood}': {result.stderr[-300:]}")
            return False
    except Exception as e:
        logger.warning(f"Music generation error for '{mood}': {e}")
        return False


def pick_music_mood(genre: str, mood: str) -> str:
    """Map genre/mood to available music track."""
    g = (genre or "").lower()
    m = (mood or "").lower()

    if "mystery" in g or "suspense" in m or "thriller" in g:
        return "mystery"
    if "comedy" in g or "fun" in m or "playful" in m:
        return "comedy_bounce"
    if "action" in g or "chase" in m or "drive" in m:
        return "action_drive"
    if "epic" in m or "triumph" in m or "reveal" in m or "adventure" in g:
        return "epic_reveal"
    return "tension_build"
