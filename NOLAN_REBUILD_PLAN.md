# LEGO WORLDS — The Nolan Rebuild

> **Philosophy:** Christopher Nolan doesn't make movies that look pretty. He makes movies that feel *inevitable*. Every shot is planned. Every second of audio earns its place. Practical effects over CGI. The story is told through image and sound, not through characters explaining what's happening.
>
> **Our translation:** The kid's Lego scene is the "practical effect." The kid's description IS the movie. We don't add characters, add conflict, or reimagine anything. We animate what's there. We narrate what he wrote. We cut it like a trailer.

---

## Core Principle Shifts

### From "AI Original Short Film" → "Cinematic Trailer of HIS Scene"

| Old approach | New approach |
|---|---|
| AI invents characters and dialogue | Kid's words are the entire narrative |
| 4-5 dialogue-heavy scenes | 6-8 visual beats with deep narrator voice |
| Characters speak to each other | Narrator speaks OVER the footage |
| Scene bible → screenplay → production | Description + photos → visual shot list → production |
| Explain the story through lines | Show the story through cuts |

### The Trailer Format

Every movie becomes a 60-second blockbuster trailer:

```
0:00-0:05   TITLE CARD          "LEGO WORLDS presents..." (black, Hans Zimmer BRAAAM)
0:05-0:12   COLD OPEN           Wide establishing shot of the full build. Single narration line:
                                "In a world built brick by brick..."
0:12-0:30   THE SETUP           3-4 tight shots (3-4s each), each showing a different element.
                                Narrator lays out who is who and what's happening.
                                Music: building tension
0:30-0:42   THE TENSION         2-3 close-up dramatic shots. Narrator reveals the conflict.
                                Music: rises
0:42-0:52   THE STAKES          Fast cuts, each 1-2s. Narrator: one-word punches ("BETRAYAL.")
                                Music: peaks
0:52-0:55   SILENCE             One held shot. No music. No narration. Let it breathe.
0:55-0:60   TITLE + CREDITS     Big title card, music swell, "A FILM BY [KID NAME]"
```

**Total dialogue: ZERO.** Only narrator voiceover. Deep, dramatic, trailer-voice-guy.

---

## The New Workflow

### Stage 1: Create Scene (unchanged)
Kid opens app, taps "New Scene", gives it a name.

### Stage 2: Capture (simplified)
**Just photos OR just video — not both required.**
- **Option A:** 3-5 photos from different angles (wide, medium, close-up per subject)
- **Option B:** 30-60s video walkthrough
- If video: we extract frames AND transcribe (transcription is supplementary context, not primary)

### Stage 3: Description (THE MAIN INPUT)
**This is the most important step. We prompt the kid clearly.**

The backstory editor becomes a **guided brief form**:

```
┌──────────────────────────────────────────────────┐
│ Tell us about your scene — YOUR words become     │
│ the narrator's voice in the movie.               │
├──────────────────────────────────────────────────┤
│                                                   │
│ 🎬 What's this movie about? (one line)           │
│ [_________________________________]               │
│ Example: "A bank robbery that goes sideways"     │
│                                                   │
│ 👥 Who's in it? (each character on a new line)   │
│ [_________________________________]               │
│ Example:                                          │
│   - The bank robber (greedy, sneaky)             │
│   - The brave cop (fearless)                     │
│   - Random citizen (clueless)                    │
│                                                   │
│ 📖 What happens? (2-4 sentences)                 │
│ [_________________________________]               │
│ Example: "The robber grabs the money and runs.   │
│ The cop chases him. They crash into the citizen. │
│ The robber trips and drops the money."           │
│                                                   │
│ 🎭 What's the mood? (pick one or write)          │
│ [ ] Action   [ ] Comedy   [ ] Drama              │
│ [ ] Mystery  [ ] Adventure  [ ] Other: ____      │
│                                                   │
└──────────────────────────────────────────────────┘
```

This is structured. We know exactly what goes where. No more free-form guessing.

### Stage 4: Shot List Generation (replaces "screenplay")

Claude Sonnet generates a **shot list**, not a screenplay. Think storyboard, not dialogue:

```json
{
  "title": "The Heist",
  "tagline": "He thought he had it all figured out.",  // narrator line 1
  "genre": "action",
  "total_duration_seconds": 60,
  "narrator_lines": [
    {"time": "0:05", "line": "In a city where fortune favors the bold..."},
    {"time": "0:12", "line": "One man had a plan."},
    {"time": "0:20", "line": "But plans..."},
    {"time": "0:25", "line": "...never survive contact."},
    {"time": "0:35", "line": "Now the chase is on."},
    {"time": "0:50", "line": "And there's nowhere to hide."},
    {"time": "0:55", "line": "THE HEIST. A film by Cary."}
  ],
  "shots": [
    {
      "shot_number": 1,
      "duration_seconds": 5,
      "type": "establishing",
      "description": "Wide shot of the full scene from above",
      "reference_photo": "frame_00.jpg",
      "camera": "static or very slow push-in",
      "motion": "none — just atmosphere",
      "sfx": "wind, distant city ambience",
      "music_beat": "quiet tension"
    },
    {
      "shot_number": 2,
      "duration_seconds": 4,
      "type": "character_intro",
      "description": "Close-up of the bank robber minifig",
      "reference_photo": "frame_02.jpg",
      "camera": "static close-up",
      "motion": "robber's head tilts slightly",
      "sfx": "footstep",
      "music_beat": "bass note"
    },
    {
      "shot_number": 3,
      "duration_seconds": 3,
      "type": "action",
      "description": "The bank vehicle at an angle",
      "reference_photo": "frame_03.jpg",
      "camera": "low angle",
      "motion": "NONE — static hero shot",
      "sfx": "engine rumble",
      "music_beat": "building"
    }
  ]
}
```

**Key rules for the shot list:**
- 6-10 shots, each 3-6 seconds
- Each shot is **one idea, one beat**
- Motion is constrained: "head tilts", "slight arm movement", "NONE"
- No impossible physics, no flying, no transforming
- Every shot references a specific photo

### Stage 5: Approval (unchanged)
Kid reviews the shot list + narrator lines. Approves or requests changes.

### Stage 6: Production

#### 6a. Video Generation (TIGHT Kie.ai prompts)

The current prompt is too loose. The new prompt is ruthlessly constrained:

**Template:**
```
Stop-motion animation of a physical Lego scene. The scene is EXACTLY the reference photo.
DO NOT change the layout, DO NOT add or remove pieces, DO NOT invent new elements.

Visible in this shot: {exact description of what's in the photo, listing every piece}

Motion allowed:
- {specific single motion, e.g. "the minifig in red shirt tilts his head to the left"}
- Nothing else moves.

Camera: {specific, e.g. "static — no camera movement"} OR {"slow dolly-in over 5 seconds"}

Duration: {3-5 seconds}
Style: Stop-motion Lego, shallow depth of field, warm cinematic lighting.

FORBIDDEN:
- Flying, floating, or defying physics
- Minifigs walking or running (they slide stiffly in stop-motion, not walk)
- Buildings morphing or changing shape
- Vehicles disappearing or reappearing
- New characters or objects appearing
- Cuts within the clip (it's one continuous shot)
- Extreme close-ups that don't match the reference
- Camera flying through walls
- Impossible perspectives
```

Plus:
- **`FIRST_AND_LAST_FRAMES_2_VIDEO`** mode (already set) — anchors start AND end to the reference
- **Seed 81422** (already set) — deterministic
- **Shorter duration 3-5s** instead of 8s — less time to drift
- **Single reference photo per shot** (not all photos) — match shot to photo

#### 6b. Narrator Voiceover (crisp, dramatic)

Replace character dialogue entirely. Just one narrator voice throughout.

- **Voice:** ElevenLabs deep storyteller voice — George (already have) or Brian (deep resonant) — specifically chosen to sound like a movie trailer
- **Settings:** Stability 0.65, Similarity 0.9, Style 0.8, Speaker boost ON — this gives the dramatic cinematic quality
- **Processing:** Post-generation we add:
  - Subtle reverb (`aecho=0.8:0.5:50:0.3`)
  - Bass boost (`equalizer=f=100:t=q:w=1:g=3`)
  - Compression (`acompressor=threshold=-16dB:ratio=3:attack=5:release=50`)
  - Master normalize to -14 LUFS

#### 6c. Music (bundled trailer tracks)

Ship the backend with a small library of royalty-free trailer music tracks:
- `trailer_tension_build.mp3` — slow build
- `trailer_action_drive.mp3` — driving action
- `trailer_mystery.mp3` — suspense
- `trailer_comedy_bounce.mp3` — lighter mood
- `trailer_epic_reveal.mp3` — title card swell

Claude picks a track based on the scene's genre/mood. Mixed under narrator at 25% volume, swelling to 60% during silence beats.

#### 6d. Sound Effects (continue using bundled library)

Keep the current FFmpeg-synthesized SFX library but use them sparingly — one well-placed SFX per shot max, not cluttered.

### Stage 7: Assembly (the edit)

FFmpeg puts it all together with trailer-style cuts:

```python
def assemble_trailer(shots, narrator_audio, music_track, sfx_files, photos):
    # 1. Title card — 3s
    title = make_title_card("LEGO WORLDS presents...", duration=3)

    # 2. Shot clips (6-10 shots, each 3-5s)
    #    Between each shot: 0.2s quick cut (or 0.5s crossfade for slow beats)
    shot_segments = []
    for i, shot in enumerate(shots):
        clip = download_video(shot)
        # Trim to exact duration
        clip = trim_to(clip, shot.duration)
        # Add per-shot SFX if any
        if shot.sfx:
            clip = overlay_sfx(clip, shot.sfx, volume=0.4)
        shot_segments.append(clip)

    # 3. Concat with quick cuts
    action_sequence = concat_with_cuts(shot_segments, cut_type="hard")

    # 4. Overlay music track across entire action sequence
    music = load_music(music_track)
    music = fit_to_duration(music, action_sequence.duration)
    music = duck_under_narration(music, narrator_audio, duck_db=-12)
    music = fade_in_out(music, fade_in=1.0, fade_out=2.0)

    # 5. Overlay narrator voiceover on top of music
    # (narrator timestamps come from shot list)
    narrated = overlay_narrator(action_sequence, narrator_audio, music)

    # 6. End title card — 4s
    end_title = make_title_card(f"{title}\nA FILM BY {director_name}", duration=4)

    # 7. Final concat: title → narrated → end title
    final = concat([title, narrated, end_title])

    # 8. Final pass: EBU R128 loudness normalize for broadcast quality
    final = normalize_loudness(final, target=-16)

    return final
```

---

## Kie.ai Prompt Deep Dive

The biggest quality issue today is weird Kie.ai motion. Here's the fix:

### Current prompt (too loose):
```
The yellow bulldozer sits blocking the delivery area. Wide establishing shot,
slow push-in from overhead. Stop-motion animated Lego scene, cinematic lighting...
```

### New prompt template (Nolan-tight):
```
[SUBJECT]
Stop-motion animation of a real physical Lego scene photographed on a baseplate.
This is a SINGLE SHOT, 5 seconds, with MINIMAL motion.

[EXACT VISUAL MATCH]
The frame shows exactly this (DO NOT deviate): {full visual description
derived from scene bible — every piece, every color, every position}.

[ALLOWED MOTION]
{ONE specific micro-motion:
  - "The minifig in the orange vest tilts his head 15 degrees to the right"
  - "The crowd of 12 minifigs sways gently as a group"
  - "Nothing moves. It's a hero shot. Hold."
}
No other motion is permitted.

[CAMERA]
{ONE specific camera move:
  - "Static camera. No movement."
  - "Slow dolly in from 2m to 1.5m over 5 seconds. Centered on {subject}."
  - "Slow 10-degree pan left. Smooth. No shake."
}

[STYLE]
Stop-motion Lego aesthetic. Real Lego bricks on a real baseplate.
Warm cinematic lighting. Shallow depth of field with focus on {subject}.
Film grain. 24fps. 16:9.

[FORBIDDEN]
- Flying, floating, levitating anything
- Walking or running minifigs (they don't walk in stop-motion)
- Morphing or transforming Lego pieces
- New characters/objects appearing out of nowhere
- Pieces disappearing
- Camera clipping through walls or vehicles
- Extreme zoom that doesn't match the reference
- Impossible perspectives (e.g. top-down when reference is side-on)
- Cuts within the clip
- Animals or characters not in the reference
```

This prompt is ~300 tokens but every token is load-bearing. The explicit FORBIDDEN list is the most important part — naming what NOT to do is how we stop the weirdness.

---

## Implementation Plan

### Phase 1: The Description Form
- Replace freeform backstory with structured form (title, characters, what happens, mood)
- Store as `structured_description` JSON in scenes table
- Update `suggest-backstory` endpoint to return pre-filled form from photos

### Phase 2: Shot List Generator
- New prompt: "You are a trailer editor. Turn this description into 6-10 shots with narrator lines."
- Output: shot list JSON (not screenplay)
- Delete the old screenplay format

### Phase 3: New Kie.ai Prompt Builder
- Per-shot prompt with FORBIDDEN list
- Single motion constraint
- Shot-specific reference photo
- Tighter duration (3-5s)

### Phase 4: Trailer-style Assembly
- Quick cuts between shots (0.2s hard, 0.5s crossfade for held shots)
- Single narrator track (no dialogue per character)
- Trailer music library (5-6 royalty-free tracks bundled)
- Music ducking under narration
- Title card + end card

### Phase 5: Trailer-voice Narrator
- Specific ElevenLabs voice tuned for trailer narration (Brian or George with dramatic settings)
- Post-processing: reverb + bass boost + compression + loudness normalize

### Phase 6: Frontend Rewrite
- ShotListReview page (replaces ScreenplayReview)
- Shot cards with reference photo + single motion description + narrator line
- Green light approves the shot list

---

## What Nolan Gets Right (And How We Mirror It)

| Nolan | Us |
|---|---|
| Practical effects — use real sets | Real Lego scenes — only animate them subtly |
| IMAX — big visual impact | Each shot is a held composition, not motion chaos |
| Hans Zimmer — music as character | Bundled trailer music, chosen per genre |
| Minimal dialogue — show don't tell | NO character dialogue, only narrator |
| Non-linear storytelling | We keep linear but use cuts for rhythm |
| Long takes | 3-5s shots are short but each is complete |
| Sound as storytelling | SFX chosen carefully, one per shot max |
| Title cards with weight | Opening and closing title cards with music swell |

---

## Cost Per Movie (estimated)

| Component | Notes | Cost |
|---|---|---|
| Scene analysis | Claude Vision with frames | $0.03 |
| Shot list | Claude writing shot list (simpler than screenplay) | $0.02 |
| Narrator voiceover | 7-8 lines, short | $0.08 |
| SFX | Bundled | $0 |
| Music | Bundled | $0 |
| Video generation | 6-8 shots @ $0.10 each | $0.60-0.80 |
| Assembly | FFmpeg | $0 |
| **Total** | | **~$0.75-1.00** |

Actually cheaper than the current dialogue-per-character approach.

---

## The Movie We're Trying to Make

Think of the iconic 60-second movie trailer:
- Black screen. A low rumble builds.
- "In a world..."
- Cut to wide establishing shot.
- "One man..."
- Close-up on the hero.
- Music starts building.
- Rapid cuts of action.
- "Will discover..."
- One held shot.
- Music peak.
- Black screen.
- Title + date.
- End.

That's what a Nolan-directed Lego movie trailer looks like. That's what we're building.
