import json
import logging
from pathlib import Path
import anthropic
from src.utils.json_repair import repair_and_parse_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "screenplay.txt").read_text()

SCREENPLAY_SCHEMA = """{
  "title": "string",
  "total_scenes": number,
  "estimated_duration_seconds": number (60-90),
  "scenes": [{
    "scene_number": number,
    "title": "string",
    "duration_seconds": number,
    "location": "string (matching a location id from the scene bible)",
    "camera": {
      "angle": "string",
      "movement": "string",
      "reference_photo": "string (filename from input photos)"
    },
    "action": "string (vivid but brief description of what happens)",
    "dialogue": [{
      "character": "string (cast id from scene bible)",
      "line": "string",
      "emotion": "string"
    }],
    "sound_effects": ["string"],
    "music_mood": "string"
  }],
  "narrator_intro": "string (cinematic but playful)",
  "narrator_outro": "string",
  "credits": {
    "directed_by": "string (the kid's name)",
    "built_by": "string (the kid's name)",
    "produced_by": "Lego Worlds AI"
  }
}"""


async def generate_screenplay(
    scene_bible: dict,
    backstory: str,
    director_name: str,
    feedback: str | None = None,
) -> dict:
    """Generate a structured screenplay from the scene bible."""

    prompt = f"""Here is the scene bible (analysis of the physical Lego build):
{json.dumps(scene_bible, indent=2)}

Original backstory from the builder:
{backstory}

Director credit name: {director_name}
"""

    if feedback:
        prompt += f"""
The director reviewed a previous draft and has this feedback:
{feedback}

Please revise the screenplay based on this feedback.
"""

    # Add enriched data from video walkthrough if available
    story_beats = scene_bible.get("story_beats", {})
    if story_beats:
        prompt += f"""
The builder described this story structure in their walkthrough:
- Setup: {story_beats.get('setup', '')}
- Conflict: {story_beats.get('conflict', '')}
- Stakes: {story_beats.get('stakes', '')}
Follow this structure closely — it's what the builder wants.
"""

    camera_notes = scene_bible.get("setting", {}).get("key_angles", [])
    if camera_notes:
        prompt += f"""
Best camera angles from the builder's walkthrough: {', '.join(camera_notes)}
Use these as reference for camera directions — these are the angles that show the scene best.
"""

    prompt += f"""
Write a screenplay for a 60-90 second animated short film.

Use this exact JSON schema:
{SCREENPLAY_SCHEMA}

Important:
- Use cast IDs from the scene bible for dialogue character fields
- Use the builder's own character names and personality descriptions
- Reference actual photo filenames in camera.reference_photo
- 3-5 scenes total
- Make the dialogue fun, punchy, and age-appropriate
- If the builder gave characters specific personalities, reflect that in dialogue
- The narrator should be cinematic but playful

Return ONLY the JSON object, no markdown fences or explanation."""

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()
    screenplay = repair_and_parse_json(response_text)
    logger.info(f"Screenplay generated: {screenplay.get('title', 'untitled')} — {screenplay.get('total_scenes', 0)} scenes")
    return screenplay
