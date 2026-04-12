import re
import json
import logging

logger = logging.getLogger(__name__)


def repair_and_parse_json(text: str) -> dict:
    """Attempt to parse JSON, with common repairs for LLM output."""
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

    # Extract JSON object if surrounded by other text
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        text = match.group(0)

    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # Remove single-line comments
    text = re.sub(r'//[^\n]*', '', text)

    # Fix unescaped newlines in strings (replace with \\n)
    # This is a heuristic — won't catch all cases
    text = re.sub(r'(?<=": ")(.*?)(?="[,\s\n}])', lambda m: m.group(0).replace('\n', '\\n'), text)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"JSON repair failed: {e}\nText: {text[:500]}")
        raise
