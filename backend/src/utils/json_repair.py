import re
import json
import logging

logger = logging.getLogger(__name__)


def repair_and_parse_json(text: str) -> dict:
    """Parse LLM-generated JSON with robust repair via the json_repair library."""
    # Strip markdown fences
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Try parsing as-is first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract the outermost JSON object if surrounded by prose
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        text = match.group(0)

    # Use the json_repair library — handles unclosed strings, missing commas,
    # unescaped quotes, and most malformations that LLMs produce.
    try:
        from json_repair import repair_json
        repaired = repair_json(text, return_objects=True)
        if isinstance(repaired, (dict, list)):
            return repaired
        # Fall through if it came back as a string
        text = repair_json(text)
        return json.loads(text)
    except Exception as e:
        logger.error(f"JSON repair failed: {e}\nText: {text[:500]}")
        raise
