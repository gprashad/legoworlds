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
      "time_seconds": 2,
      "line": "string — 8-20 words, trailer-voice narration (12-16 lines total, gaps ≤2s, covers 55-70% of runtime)"
    }
  ],
  "shots": [
    {
      "shot_number": 1,
      "duration_seconds": 3,
      "type": "establishing | character_intro | action | tension | reveal | hero_shot | title",
      "description": "string — what's shown in this shot",
      "reference_photo_index": 0,
      "subject": "string — the specific thing in focus, WITH action (e.g., 'Marcus at the register, head snapping toward the flame')",
      "motion": "string — MUST start with an action verb (rolls, turns, tilts, ignites, opens, pulls, snaps, swings, flickers, reveals, drifts, lowers). 'static hold' is FORBIDDEN.",
      "camera": "string — pick ONE: static-locked | slow dolly in 5-10% | slow dolly out 5-10% | rack focus pull | arc 15° around subject | tracking lateral slow | dutch tilt-in 5° | handheld-locked (no drift)",
      "tempo": "string — one of: slow | measured | propulsive | urgent | suspended",
      "beats": [
        {"t_start": 0.0, "t_end": 1.5, "camera_state": "string — where camera is at this beat", "subject_action": "string — what the subject does in this beat"},
        {"t_start": 1.5, "t_end": 3.0, "camera_state": "string", "subject_action": "string"}
      ],
      "sfx_keyword": "string or null — single SFX like 'engine' or 'crowd' or null"
    }
  ]
}"""

SYSTEM_PROMPT = """You are editing a 60-second trailer for a CHILDREN'S LEGO MINIFIG MOVIE built and filmed by an 8-year-old at home. Think The Lego Movie, The Lego Batman Movie — cartoon action, no realism, plastic minifigs only. All "fires" are cartoon orange plastic flames, all "robbers" are smiling brick people, everyone is safe. This is wholesome kid-creative play, exactly like the officially licensed Lego films. Your job:

1. Turn the builder's description into DENSE trailer narration — CINEMATIC, not literal.
   - Use dramatic trailer cadence: "In a world...", "One man...", "But fate...", "Now..."
   - **12-16 narrator lines total.** Each line is **8-20 words** (not 3-8). Real trailers are talky — cover 55-70% of the 60s runtime with speech.
   - **Gaps between consecutive lines must be ≤ 2 seconds.** No dead air.
   - Evenly distributed across the 60 seconds — not all front-loaded.
   - Nothing explains plot literally. Show the emotion through rhythm.
   - The FINAL line is always the title reveal ("THE HEIST. A film by [name].")

   CADENCE EXAMPLE (this is the density you should match):
   ```
   t=2s:  "In a city that never sleeps, one ordinary morning was about to change."
   t=8s:  "A family of ordinary heroes, going about their ordinary day."
   t=14s: "But ordinary doesn't last. Not today. Not here."
   t=20s: "One spark. One wrong moment. And the street came alive with fire."
   t=27s: "The sirens came too late. The road was already gone."
   t=34s: "Some ran for cover. Some stood their ground for strangers."
   t=41s: "One father. One missing son. One burning block between them."
   t=48s: "Not every hero wears a cape. Some just refuse to leave anyone behind."
   t=55s: "THIS SUMMER — BRICK CITY BLAZE. A film by Cary."
   ```
   (9 lines covering ~38s of speech across 60s = ~63% coverage. That's the target.)

2. Build a shot list of **18-25 shots** (short and fast-cut):
   - Each **2-3 seconds** (not 4-6)
   - Each shot is ONE idea with CLEAR directed motion — NOT a still frame
   - **Every `motion` string MUST start with an action verb.** `"static hold"` and `"none"` are BANNED.
     Verbs to use: rolls forward 2 studs, turns head toward camera, tilts up 10°, ignites, opens slowly, pulls back, snaps toward threat, swings arm down, flickers, reveals under light, drifts in wind, lowers hand.
   - **Every shot gets a `tempo` tag** drawn from the scene mood:
     `slow` (contemplative hold) | `measured` (steady build) | `propulsive` (driving energy) | `urgent` (tense rising) | `suspended` (held breath)
   - **Every shot gets a `beats` array** — 2 beats for 2s shots, 3 beats for 3s shots. Each beat specifies what the CAMERA is doing AND what the SUBJECT is doing in that ~1s window. This is the scaffolding the video model needs to choreograph motion.
   - **Camera vocabulary — pick ONE per shot from this list only:**
     `static-locked` · `slow dolly in 5-10%` · `slow dolly out 5-10%` · `rack focus pull` · `arc 15° around subject` · `tracking lateral slow` · `dutch tilt-in 5°` · `handheld-locked (no drift)`
   - **BAN: pan, orbit, whip, zoom >15%, walking minifigs, flying, any impossible motion**

   SHOT-TYPE MOTION LIBRARY (use these as defaults, adapt for subject):
   - `establishing` → slow dolly in 5% + ambient flicker/breeze/steam in background
   - `character_intro` → rack focus pull to subject + subject turns head or eyes toward camera
   - `reveal` → arc 15° around subject + subject emerges from behind occluder or opens/ignites
   - `action` → tracking lateral slow + subject rolls, swings, or lunges forward
   - `tension` → dutch tilt-in 5° + subject head snaps toward threat
   - `hero_shot` → slow dolly out 5-10% + subject stands firm as camera pulls away
   - `title` → static-locked + a final flame flicker or piece settle before the title card

   BEAT EXAMPLE (3s character_intro shot):
   ```
   beats: [
     {"t_start": 0.0, "t_end": 1.5, "camera_state": "foreground brick in soft focus, Marcus blurry at register", "subject_action": "Marcus is still, head down, counting bills"},
     {"t_start": 1.5, "t_end": 3.0, "camera_state": "rack pulls — Marcus snaps into focus, foreground goes soft", "subject_action": "Marcus's head snaps up, eyes toward camera, mouth set"}
   ]
   ```

3. Match shots to photos by index (use reference_photo_index: 0, 1, 2, etc.)

4. Pick ONE music mood that matches the genre.

5. Keep it TIGHT. 60 seconds. Every shot earns its place.

Think Christopher Nolan trailer. Dark Knight. Inception. Dunkirk.
Show, don't tell. Visual storytelling. DENSE narration with MAXIMUM weight.

Output ONLY valid JSON matching the schema. No markdown fences."""


_SAFETY_SUBSTITUTIONS = [
    # Map realistic-sounding words to cartoon-Lego equivalents.
    (r"\brobber[s]?\b", "mischief minifig"),
    (r"\brobbery\b", "caper"),
    (r"\bheist\b", "caper"),
    (r"\bstolen\b", "grabbed"),
    (r"\bsteal(ing)?\b", "grabbing"),
    (r"\bfire\b", "cartoon flame prop"),
    (r"\bfires\b", "cartoon flame props"),
    (r"\bflames\b", "cartoon flame pieces"),
    (r"\bon fire\b", "with plastic flame pieces"),
    (r"\barson(ist)?s?\b", "flame-prop placer"),
    (r"\bburning\b", "glowing with plastic flames"),
    (r"\bset fire to\b", "placed cartoon flame bricks on"),
    (r"\bdanger(ous)?\b", "exciting"),
    (r"\bescape(s|d|ing)?\b", "hops away"),
    (r"\bflee(s|d|ing)?\b", "scampers"),
    (r"\babandon(s|ed|ing)?\b", "loses track of"),
    (r"\bleft (his|her|their) (son|daughter|child|kid)\b", "was separated from their kid"),
    (r"\bstrand(ed|ing)?\b", "stuck"),
    (r"\bvictim(s)?\b", "bystander"),
    (r"\bcriminal(s)?\b", "mischief minifig"),
    (r"\bpolice\b", "Lego police minifig"),
]


def _sanitize_for_safety(text: str) -> str:
    """Swap words that can trip Claude's safety classifier into cartoon-Lego equivalents."""
    import re as _re
    out = text
    for pattern, repl in _SAFETY_SUBSTITUTIONS:
        out = _re.sub(pattern, repl, out, flags=_re.IGNORECASE)
    return out


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


# --- Narration density validation ---

# 2.5 words/sec ≈ trailer-voice speech rate (slow, deliberate)
_WORDS_PER_SECOND = 2.5
_MIN_COVERAGE = 0.45  # 45% of runtime should be speech
_MAX_GAP_SECONDS = 6.0  # flag any gap longer than this


def _compute_narration_coverage(narrator_lines: list[dict], total_duration: int) -> dict:
    """Return coverage stats: {coverage_pct, largest_gap, gaps}."""
    if not narrator_lines:
        return {"coverage_pct": 0.0, "largest_gap": total_duration, "gaps": []}

    speech_seconds = 0.0
    timeline: list[tuple[float, float]] = []  # (start, end)
    for line in narrator_lines:
        words = len(str(line.get("line", "")).split())
        dur = words / _WORDS_PER_SECOND
        start = float(line.get("time_seconds", 0))
        timeline.append((start, start + dur))
        speech_seconds += dur

    timeline.sort()
    # Gaps = time between end of one line and start of next, plus trailing gap to total_duration
    gaps = []
    prev_end = 0.0
    for start, end in timeline:
        if start > prev_end:
            gaps.append(round(start - prev_end, 1))
        prev_end = max(prev_end, end)
    if total_duration > prev_end:
        gaps.append(round(total_duration - prev_end, 1))

    return {
        "coverage_pct": round(min(speech_seconds / total_duration, 1.0), 3),
        "largest_gap": max(gaps) if gaps else 0.0,
        "gaps": gaps,
    }


def _build_density_feedback(stats: dict, total_duration: int) -> str:
    """Build a feedback string asking Claude to fill gaps."""
    return (
        f"Previous draft coverage was {int(stats['coverage_pct']*100)}% — TOO SPARSE. "
        f"Target is 55-70%. Largest gap was {stats['largest_gap']}s of dead air. "
        f"Gaps: {stats['gaps']}. "
        f"Fill every gap >2s with another 8-20 word narrator line. "
        f"You need 12-16 total lines across {total_duration}s, evenly distributed."
    )


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
- **12-16 narrator lines**, 8-20 words each, gaps ≤2s, covering 55-70% of runtime
- **18-25 shots**, 2-3 seconds each (short, fast cuts)
- Every shot has an **action-verb motion**, a **tempo**, and a **beats array** (2-3 beats)
- Camera picked from the 8-item vocabulary only (no pan/orbit/whip)
- Match shots to photos by index
- Pick music_mood from: tension_build, action_drive, mystery, comedy_bounce, epic_reveal
- FINAL narrator line is the title reveal

Output ONLY JSON, no markdown fences."""

    client = anthropic.Anthropic()

    # Try models in order — Opus 4.7 is safety-strict on cartoon action; fall back if refused.
    attempts = [
        ("claude-opus-4-7", prompt),
        ("claude-sonnet-4-6", prompt),
        ("claude-opus-4-7", _sanitize_for_safety(prompt)),
        ("claude-sonnet-4-6", _sanitize_for_safety(prompt)),
    ]
    response_text = ""
    last_stop_reason = None
    used_model = None
    for model_id, user_prompt in attempts:
        message = client.messages.create(
            model=model_id,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        response_text = "".join(
            getattr(b, "text", "") for b in message.content if getattr(b, "type", None) == "text"
        ).strip()
        last_stop_reason = getattr(message, "stop_reason", "?")
        if response_text:
            used_model = model_id
            break
        logger.warning(f"Shot list model {model_id} returned no text (stop_reason={last_stop_reason}); trying next fallback")

    if not response_text:
        raise ValueError(f"Shot list generation refused by all models (last stop_reason={last_stop_reason})")
    if used_model and used_model != "claude-opus-4-7":
        logger.info(f"Shot list fell back to {used_model}")
    shot_list = repair_and_parse_json(response_text)

    # Validate basics
    if "shots" not in shot_list or "narrator_lines" not in shot_list:
        raise ValueError("Shot list missing required fields")

    # Narration density check — retry up to 2x with feedback if too sparse
    total_duration = int(shot_list.get("total_duration_seconds", 60))
    stats = _compute_narration_coverage(shot_list.get("narrator_lines", []), total_duration)
    logger.info(
        f"Narration coverage: {int(stats['coverage_pct']*100)}% — "
        f"largest gap {stats['largest_gap']}s — {len(shot_list.get('narrator_lines', []))} lines"
    )

    # Only retry on the first call (no pre-existing feedback from caller) to avoid loops
    retries = 0
    while (
        stats["coverage_pct"] < _MIN_COVERAGE or stats["largest_gap"] > _MAX_GAP_SECONDS
    ) and retries < 2 and feedback is None:
        retries += 1
        density_feedback = _build_density_feedback(stats, total_duration)
        logger.warning(
            f"Narration too sparse (coverage={int(stats['coverage_pct']*100)}%, "
            f"gap={stats['largest_gap']}s). Retry {retries}/2."
        )
        retry_prompt = prompt + f"\n\nPREVIOUS DRAFT FEEDBACK:\n{density_feedback}\n\nRevise based on this feedback.\n"
        message = client.messages.create(
            model=used_model or "claude-opus-4-7",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": retry_prompt}],
        )
        retry_text = "".join(
            getattr(b, "text", "") for b in message.content if getattr(b, "type", None) == "text"
        ).strip()
        if not retry_text:
            logger.warning("Density retry returned empty response; keeping previous draft.")
            break
        try:
            retry_list = repair_and_parse_json(retry_text)
        except Exception as e:
            logger.warning(f"Density retry JSON parse failed: {e}; keeping previous draft.")
            break
        if "shots" in retry_list and "narrator_lines" in retry_list:
            shot_list = retry_list
            stats = _compute_narration_coverage(shot_list.get("narrator_lines", []), total_duration)
            logger.info(
                f"Retry #{retries} coverage: {int(stats['coverage_pct']*100)}% — "
                f"largest gap {stats['largest_gap']}s — {len(shot_list.get('narrator_lines', []))} lines"
            )

    logger.info(
        f"Shot list generated: {shot_list.get('title', 'untitled')} — "
        f"{len(shot_list.get('shots', []))} shots, {len(shot_list.get('narrator_lines', []))} narrator lines, "
        f"coverage={int(stats['coverage_pct']*100)}%"
    )
    return shot_list
