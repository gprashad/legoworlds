# LEGO Worlds — Movie Quality Plan

> Living document. Started **2026-04-17** after the "Brick City Blaze" trailer
> came back at a 1/10. Target: **8/10**.
>
> **Latest pivot (2026-04-17):** Kie.ai carries Kling 2.1 Pro with the exact
> three knobs we need (`negative_prompt`, `cfg_scale`, `tail_image_url`) at
> **$0.25/5s — cheaper than our current Veo3**. The model swap is now a
> ~1-hour endpoint change, not a 1-day port to Fal. This reorders the sprints.

---

## Current state — what's broken

After shipping the Nolan-style rebuild, the first trailer ("Brick City Blaze",
`scene_id e8b6d840-cbe9-477d-b010-1532d066c526`) exposed two core failures.

### 1. Narration is too sparse

- 7 narrator lines across 60s video
- Only ~12s of speech = **~20% coverage**
- Largest gap: **11 seconds of dead air**
- Real trailers run 50–70% narration coverage

Current shot list narration:
```
t=3s:  "A city. Alive. Unsuspecting."           (4 words)
t=12s: "Then everything changed."                (3 words)
t=22s: "One fire. One road. No way through."    (8 words)
t=33s: "Heroes blocked. Innocents left behind." (5 words)
t=44s: "Some ran. Some stood."                   (4 words)
t=52s: "Not all make it out."                    (5 words)
t=57s: "BRICK CITY BLAZE. A film by Cary."      (7 words)
```

### 2. Video coherence is broken

Observed failure modes in the generated Kie.ai / VEO3 shots:

| Failure | Likely root cause |
|---|---|
| Minifigs disappear mid-shot | Model doesn't track identity; no "do not remove X" constraint |
| Base plates fly around the table | Prompt says "subtle motion" — model takes liberties |
| Cars move sideways | No directional constraint; LEGO cars only roll forward |
| Things teleport | Shots too long (5s); more time = more drift |
| Doesn't look like the physical build | Weak reference photo conditioning; prompt overrides photo |

**Root cause (per research agent, 2026-04-17):** VEO3 is architecturally wrong
for stop-motion. It optimizes for cinematic motion and photoreal plausibility,
NOT first-frame lockdown. It will reinterpret a static LEGO scene as "a scene
that should move realistically" and invent physics. Our prompts are also too
loose, shots are too long, we don't use negative prompts, and we don't verify
output quality — but even perfect prompts won't save Veo3 for this use case.

---

## The plan

Three tracks:
- **Track A** — prompt/pipeline tightening (helps regardless of model)
- **Track B** — model swap (Kling 2.1 Pro via Kie.ai — now ~1 hr)
- **Track C** — post-generation QA loop

---

### Track A — Tighten the prompt pipeline

#### A1. Narration density (`backend/src/stages/shot_list.py`)

Update `SYSTEM_PROMPT` rules:
- **12–16 narrator lines** (currently 5–7)
- Each line **8–20 words** (currently 3–8)
- **Gaps ≤ 2 seconds** between consecutive lines
- Explicit rule: "narration covers 55–70% of the 60s runtime"
- Include a cadence example in the prompt so Claude doesn't regress

Add post-generation validation + auto-retry:
- Compute `coverage = sum(len(line.split())/2.5 for line in lines) / 60`
  (2.5 words/sec ≈ trailer-voice speech rate)
- If `< 0.45`, call Claude again with feedback: *"Previous draft had X% coverage — too sparse. Fill the gap at [timestamp] with another line."*
- Max 2 retries (reuses the existing `feedback` param in `generate_shot_list`)

**File:** `backend/src/stages/shot_list.py`
**Effort:** ~1 hr · **Impact:** 1/10 → 3/10 on narration alone

#### A2. ElevenLabs voice settings (`backend/src/stages/production.py`)

Adjust `TRAILER_NARRATOR_SETTINGS`:
- Lower `stability` 0.65 → **0.40** for more Jeff-Bridges texture variation
- `style` stays ~0.70–0.80 for dramatic cadence
- Test SSML `<prosody rate="90%">` wrap for deliberate trailer-voice pacing

**Effort:** 30 min · **Impact:** subtle but compounds

#### A3. LEGO physics preamble + negative prompt

Rewrite `build_nolan_shot_prompt` so every Kie-bound prompt gets a fixed LEGO
physics rules block:

```
This is stop-motion LEGO animation. RULES:
- Every object is a hard plastic LEGO piece. Pieces do not deform,
  stretch, or morph.
- Minifigures have stiff bodies. They rotate only at head, arms, and
  waist. They do NOT walk smoothly — they glide or stay still.
- Vehicles roll on their wheels in their facing direction only. No
  sideways sliding.
- Base plates are fixed to the table. They DO NOT move, rotate, or lift.
- Nothing disappears. Every minifig and piece visible at frame 0 is
  visible at frame N.
- No new objects appear that were not in the reference photo.
- Lighting and camera are locked unless explicitly specified.
- Style: plastic sheen, matte table surface, home-made stop-motion feel.
```

Plus an explicit negative-prompt block (passed via the Kling `negative_prompt`
param once A3 + B1 ship together):

```
melting, morphing, smooth organic motion, realistic humans,
cinematic camera drift, base plate levitation, teleporting figures,
new characters appearing, minifigs walking, cars drifting sideways,
objects phasing through each other, scale inconsistency,
deforming plastic, extra limbs, blur, low quality
```

**File:** `backend/src/stages/production.py` (`build_nolan_shot_prompt`)
**Effort:** ~2 hrs · **Impact:** 3/10 → 5–6/10

#### A4. Subject lock-in

Every shot prompt must name the subject with exact `visual_details` from
`scene_bible.cast`, not just "the minifig":

```
Subject: Marcus (dark blue jacket, yellow face, black hair, standing by
the red fire truck). Marcus remains in the same position throughout this
shot — only his head tilts left.
```

Pull `visual_details` by matching `shot.subject` against `scene_bible.cast[].description`.

**File:** `backend/src/stages/production.py`
**Effort:** rolled into A3 · **Impact:** large on identity consistency

#### A5. Shot duration + motion type

Edit the shot_list generation prompt so output shots are:
- **2–3 seconds** each (currently 4–6s)
- **70% pure static** — `motion: "static hold"` + `camera: "static"`
- **20% tiny dolly** — 5–10% push-in/push-out only
- **10% single-axis subject motion** — e.g., "car rolls forward 2 studs"
- **Ban:** pan, tilt, orbit, handheld, whip, zoom >15%

Result: 18–25 shots for a 60s trailer instead of 10. More variety, less
per-shot drift risk. Faster cuts = trailer feel anyway.

**File:** `backend/src/stages/shot_list.py`
**Effort:** 30 min · **Impact:** 5/10 → 7/10

---

### Track B — Model swap to Kling 2.1 Pro (via Kie.ai)

**Why Kling 2.1 Pro:** Research agent + follow-up confirmed Kie.ai carries
Kling at the exact spec we need:

| Model | negative_prompt | cfg_scale | tail_image (end frame) | Price (5s) |
|---|---|---|---|---|
| **Kling 2.1 Pro** | ✓ | ✓ (0-1, default 0.5) | ✓ | **$0.25** |
| Kling 2.1 Master | ✓ | ✓ | ✓ | $0.80 |
| Kling 2.6 | ✗ | ✗ | ✗ | $0.28-$1.10 |
| Veo3 (current) | ✗ | ✗ | ✗ | ~$0.30 |

Kling 2.1 Pro gives us the three knobs the research flagged as essential AND
it's **cheaper** than our current Veo3 bill. No new vendor, no Fal account,
no refactor — just an endpoint + body-shape change in one function.

#### B1. Swap Kie.ai endpoint in `_submit_video_generation`

Current (Veo3):
```python
POST https://api.kie.ai/api/v1/veo/generate
{
  "prompt": ..., "model": "veo3_fast",
  "aspect_ratio": "16:9",
  "generationType": "FIRST_AND_LAST_FRAMES_2_VIDEO",
  "imageUrls": [url1, url2], "seeds": 81422, ...
}
```

New (Kling 2.1 Pro):
```python
POST https://api.kie.ai/api/v1/jobs/createTask
{
  "model": "kling/v2-1-pro",
  "callBackUrl": None,
  "input": {
    "prompt": "<LEGO physics preamble + shot prompt, ≤5000 chars>",
    "image_url": <first photo URL>,           # single, not array
    "tail_image_url": <same URL>,             # force near-static
    "duration": "5",                          # or "10"
    "negative_prompt": "<LEGO negatives, ≤500 chars>",
    "cfg_scale": 0.8                          # crank for strict adherence
  }
}
```

Poll changes too: `_poll_video` should hit the common task-detail endpoint
(`/api/v1/jobs/recordInfo` or equivalent per Kie docs) and read `resultUrls`
from the new response shape.

Gate behind env var so we can fall back:
```python
KIE_VIDEO_MODEL = os.getenv("KIE_VIDEO_MODEL", "kling-v2-1-pro")  # or "veo3_fast"
```

**File:** `backend/src/stages/production.py` (`_submit_video_generation`, `_poll_video`)
**Effort:** ~1 hr · **Impact:** 5/10 → 7+/10 (the big one)

#### B2. A/B regenerate 3 "Brick City Blaze" shots

Pick 3 shots from `scene_id e8b6d840…`, regenerate each via Kling with
`cfg_scale=0.8`, `tail_image_url = image_url`, LEGO negative prompt. Line
them up next to the Veo3 originals. Decision gate:

- Kling wins ≥2/3 → set `KIE_VIDEO_MODEL=kling-v2-1-pro` as default.
- Kling loses or draws → try `cfg_scale=0.9` and/or Kling 2.1 Master at $0.80/5s.
- Still losing → Track D (runner-up model, see below).

**Effort:** 30 min of clip time · **Impact:** decides everything downstream

---

### Track C — Post-generation QA loop

#### C1. Claude Vision drift check per shot

After each Kie shot lands:
1. Extract frame 0 and frame N (last) with ffmpeg.
2. Send both to Claude Opus 4.7 with a 1–10 rubric:
   - **Object permanence** — same LEGO pieces in both frames?
   - **Physics** — real stop-motion or morphing?
   - **Identity** — same minifigs recognizable?
3. If any score < 6, regenerate with stricter prompt: *"STRICTER: no motion except [X]. Lock all other elements. cfg_scale bumped to 0.9."*
4. Cap retries at 2 per shot.

**Cost bound:** 2 retries × ~18 shots × $0.25/shot = **~$9** worst-case per trailer.

**File:** new `backend/src/stages/shot_qa.py`; wired into `production.py`
**Effort:** 2–3 hrs · **Impact:** 7/10 → 8/10

#### C2. Continuity across shots

- Force shots with the same `location_id` / `subject` to use the **same reference photo** (currently Claude picks per-shot and flip-flops).
- Pipe exact `visual_details` from `scene_bible.cast` into every shot prompt mentioning that character (shares code with A4).
- Pull scene lighting (e.g., "warm overhead kitchen light, slight yellow cast") from `scene_bible` into every prompt.

**File:** `backend/src/stages/production.py`
**Effort:** ~1 hr · **Impact:** 7/10 → 8/10

---

### Track D — Fallback models (only if Kling disappoints)

Research-agent ranking, in order:

1. **Runner-up: Runway Gen-4 Turbo** — #1 Artificial Analysis Elo Dec 2025, $0.05/s, best camera-motion discipline. **Not on Kie.ai** — requires Fal client (~1 day port).
2. **Wild card: Hailuo MiniMax i2v-01-director** — literal `[Static shot]` camera tag in prompt grammar. **Not on Kie.ai** — requires Fal or Replicate.
3. **Bookmark: Seedance 2.0 (ByteDance)** — launched April 2026 on Fal, start+end frames, $0.24/s. Too new for production.
4. **Avoid:** Veo (any wrapper/direct), Sora 2 (API deprecating Sept 2026, EU-blocked), LTX-Video (hallucinates geometry).

Do not start Track D unless Sprint 2 (Kling A/B) stalls below 7/10.

---

## Ordered work plan

| # | Task | File(s) | Effort | Quality impact |
|---|------|---------|--------|----------------|
| 1 | Narration density + validation retry | `shot_list.py` | 1 hr | 1 → 3 |
| 2 | ElevenLabs voice tuning | `production.py` | 30 min | subtle |
| 3 | LEGO physics preamble + negative prompt | `production.py` | 2 hrs | 3 → 5 |
| 4 | Subject lock-in from scene_bible | `production.py` | in #3 | identity ✓ |
| 5 | Shot duration 2–3s + force static | `shot_list.py` | 30 min | 5 → 6 |
| 6 | **Swap Kie endpoint to Kling 2.1 Pro** | `production.py` | 1 hr | 6 → 7+ |
| 7 | Regenerate 3 shots, A/B vs Veo3 | clip time | 30 min | gate |
| 8 | Claude Vision per-shot QA loop | new `shot_qa.py` | 2–3 hrs | 7 → 8 |
| 9 | Continuity (same photo, character lock) | `production.py` | 1 hr | 7 → 8 |
| 10 | (conditional) Track D fallback models | new Fal client | 1 day | only if needed |

### Recommended sprint order

**Sprint 1 (today, ~4 hrs):** #1 #2 #3 #4 #5
→ something noticeably better tonight; 1/10 → ~5/10, still on Veo3.

**Sprint 2 (~1.5 hrs):** #6 #7
→ the big unlock. Kling with strict `cfg_scale` + tail-frame lock + negatives.
Expected jump: 5/10 → 7+/10. Cost per trailer **drops** from ~$5 to ~$4.

**Sprint 3 (~4 hrs):** #8 #9
→ target 8/10.

**Sprint 4 (conditional):** #10 — only if Sprint 2 underwhelms.

---

## Decision log

- **2026-04-17** — Rejected "live-and-let-live" Sprint (keep VEO3, tweak prompts only). Current output was called 1/10; model swap explicitly requested.
- **2026-04-17** — Shipped audio pipeline fixes (narration audible, no clipping, no duration mismatch). Video is now the limiting factor.
- **2026-04-17** — Research agent returned. Veo (any wrapper) is architecturally wrong for stop-motion. Top pick = **Kling 2.1/2.6 Pro** with `negative_prompt` + `cfg_scale` + start/end-frame conditioning. Runner-up = Runway Gen-4 Turbo. Wild card = Hailuo i2v-01-director.
- **2026-04-17** — Discovered **Kie.ai carries Kling 2.1 Pro** at the full spec (negative_prompt + cfg_scale + tail_image_url) for $0.25/5s — cheaper than current Veo3. Model swap collapses from a Fal port (1 day) to a Kie endpoint change (~1 hr). Sprint order reshuffled.
- **2026-04-17** — Shipped all of Sprints 1, 2.1, 3.1, and 3.2. Ready for live A/B run (#55). Knobs live behind env: `KIE_VIDEO_MODEL=kling-v2-1-pro` (default), `KLING_CFG_SCALE=0.8`, `SHOT_QA_ENABLED=true`, `SHOT_QA_MAX_RETRIES=2`.

## Open questions

- Does Kling 2.1 Pro on Kie expect `image_url` (single string) or `image_urls` (array)? Standard variant docs say singular; Pro may differ. Test with one call first.
- What does the task-detail response shape look like for Kling vs Veo? Expect `resultUrls` array similar to Veo.
- Does `tail_image_url = image_url` (same photo both ends) genuinely force near-static, or does the model interpolate weird drift in the middle? Test on a simple shot.
- Do we want per-character voice casting for the narrator, or single voice (current: single Brian TTS)?

## References

- Scene that exposed all this: `e8b6d840-cbe9-477d-b010-1532d066c526` ("Brick City Blaze")
- Pipeline entry: `backend/src/pipeline.py` `run_trailer_production`
- Shot list generator: `backend/src/stages/shot_list.py`
- Video generation: `backend/src/stages/production.py` (`generate_shot_list_videos`, `build_nolan_shot_prompt`, `_submit_video_generation`, `_poll_video`)
- Assembly + audio mix: `backend/src/stages/assembly.py`
- Kie.ai Kling 2.1 API: https://kie.ai/kling/v2-1
- Kie.ai Kling 2.1 Standard spec: https://docs.kie.ai/market/kling/v2-1-standard
- Research agent transcript: task `a8d0085d434f86c5b` (2026-04-17)
