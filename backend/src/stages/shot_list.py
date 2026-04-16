"""
Nolan Rebuild — Shot List Generator

Takes the kid's structured description + scene bible + photos and generates
a TRAILER-style shot list: 6-10 shots with narrator lines in cinematic voice.

No character dialogue. Just narrator. Think movie trailer.
"""

import json
import logging
from pathlib import Path
import anthropic
from src.utils.json_repair import repair_and_parse_json

logger = logging.getLogger(__name__)


SHOT_LIST_SCHEMA = """{
  "title": "string — the movie title (cinematic, 1-4 words)",
  "tagline": "string — a single dramatic line, trailer style",
  "genre": "string (action/drama/comedy/adventure/mystery/thriller)",
  "mood": "string (tense/epic/sneaky/heroic/playful)",
  "total_duration_seconds": 60,
  "music_mood": "string — one of: tension_build, action_drive, mystery, comedy_bounce, epic_reveal",
  "narrator_lines": [
    {
      "time_seconds": 5,
      "line": "string — trailer-voice narration, short, evocative, NOT explaining plot literally"
    }
  ],
  "shots": [
    {
      "shot_number": 1,
      "duration_seconds": 5,
      "type": "establishing | character_intro | action | tension | reveal | hero_shot | title",
      "description": "string — what's shown in this shot",
      "reference_photo_index": 0,
      "subject": "string — the specific thing in focus",
      "motion": "string — ONE specific micro-motion OR 'static hold'",
      "camera": "string — ONE specific move OR 'static'",
      "sfx_keyword": "string or null — single SFX like 'engine' or 'crowd' or null"
    }
  ]
}"""

SYSTEM_PROMPT = """You are the editor of a 60-second blockbuster movie trailer. Your job:

1. Turn the builder's description into trailer narration — CINEMATIC, not literal.
   - Use dramatic trailer cadence: "In a world...", "One man...", "But fate...", "Now..."
   - 5-7 narrator lines total. Each line is 3-8 words. Nothing explains plot literally.
   - The FINAL line is always the title reveal ("THE HEIST. A film by [name].")

2. Build a shot list of 6-10 shots:
   - Each 3-6 seconds
   - Each shot is ONE idea, ONE motion
   - Motion must be subtle: head tilts, arm shifts, vehicle drifts, crowd sways
   - NO walking minifigs, NO flying, NO impossible motion
   - Prefer STATIC hero shots — they're the most reliable

3. Match shots to photos by index (use reference_photo_index: 0, 1, 2, etc.)

4. Pick ONE music mood that matches the genre.

5. Keep it TIGHT. 60 seconds. Every shot earns its place.

Think Christopher Nolan trailer. Dark Knight. Inception. Dunkirk.
Show, don't tell. Visual storytelling. Minimal narration with MAXIMUM weight.

Output ONLY valid JSON matching the schema. No markdown fences."""


def _format_structured_description(sd: dict) -> str:
    """Format the structured description for the prompt."""
    parts = []
    if sd.get("title"):
        parts.append(f"Working title: {sd['title']}")
    if sd.get("one_liner"):
        parts.append(f"One-liner: {sd['one_liner']}")
    if sd.get("characters"):
        parts.append("Characters:")
        for c in sd["characters"]:
            if isinstance(c, dict):
                parts.append(f"  - {c.get('name', '?')}: {c.get('description', '')}")
            else:
                parts.append(f"  - {c}")
    if sd.get("what_happens"):
        parts.append(f"What happens: {sd['what_happens']}")
    if sd.get("mood"):
        parts.append(f"Mood: {sd['mood']}")
    return "\n".join(parts) if parts else "(no description provided)"


async def generate_shot_list(
    scene_bible: dict,
    structured_description: dict,
    backstory: str,
    director_name: str,
    num_photos: int,
    feedback: str | None = None,
) -> dict:
    """Generate a trailer-style shot list + narrator lines."""

    description_text = _format_structured_description(structured_description or {})

    prompt = f"""THE BUILDER'S BRIEF:
{description_text}

{f"Additional context: {backstory}" if backstory and not structured_description else ""}

SCENE BIBLE (what's physically in the Lego scene):
{json.dumps(scene_bible, indent=2, default=str)[:3000]}

REFERENCE PHOTOS AVAILABLE: {num_photos} photos (index 0 to {num_photos - 1})

DIRECTOR: {director_name}

"""

    if feedback:
        prompt += f"""PREVIOUS DRAFT FEEDBACK:
{feedback}

Revise based on this feedback.

"""

    prompt += f"""Generate a shot list for a 60-second blockbuster trailer.

Schema:
{SHOT_LIST_SCHEMA}

Remember:
- 5-7 narrator lines, short and cinematic (NOT the builder's words verbatim — translate to trailer voice)
- 6-10 shots, 3-6 seconds each
- Motion: static or ONE subtle micro-motion per shot
- Match shots to photos by index
- Pick music_mood from: tension_build, action_drive, mystery, comedy_bounce, epic_reveal
- FINAL narrator line is the title reveal

Output ONLY JSON, no markdown fences."""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()
    shot_list = repair_and_parse_json(response_text)

    # Validate basics
    if "shots" not in shot_list or "narrator_lines" not in shot_list:
        raise ValueError("Shot list missing required fields")

    logger.info(
        f"Shot list generated: {shot_list.get('title', 'untitled')} — "
        f"{len(shot_list.get('shots', []))} shots, {len(shot_list.get('narrator_lines', []))} narrator lines"
    )
    return shot_list
