import json
import logging
from pathlib import Path
import anthropic

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

    prompt += f"""
Write a screenplay for a 60-90 second animated short film.

Use this exact JSON schema:
{SCREENPLAY_SCHEMA}

Important:
- Use cast IDs from the scene bible for dialogue character fields
- Reference actual photo filenames in camera.reference_photo
- 3-5 scenes total
- Make the dialogue fun, punchy, and age-appropriate
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

    # Strip markdown fences if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response_text = "\n".join(lines)

    screenplay = json.loads(response_text)
    logger.info(f"Screenplay generated: {screenplay.get('title', 'untitled')} — {screenplay.get('total_scenes', 0)} scenes")
    return screenplay
