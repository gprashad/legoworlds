# LEGO WORLDS — Audio Upgrade Plan

> **Goal:** Make the audio layer feel like a real animated short — fun voices, cinematic music, punchy sound effects, professional mix.

---

## Current State (what's broken)

- **Voices:** Generic ElevenLabs presets (Adam, Arnold, Antoni, Bella) — sound flat, adult, corporate
- **No music:** Zero background music — scenes feel empty and lifeless
- **No SFX:** Screenplay specifies sound effects ("engine idling", "crowd murmuring") but none are generated
- **No mixing:** Dialogue just slapped on top of video at full volume, no ducking or fading
- **No narrator feel:** Narrator voice (Bella) doesn't sound cinematic or playful

---

## Phase A: Voice Upgrade

### A1. Better Voice Selection
- Switch to ElevenLabs voices that sound fun, animated, kid-appropriate
- **Narrator:** Deep, warm, movie-trailer style (think Morgan Freeman lite for kids)
- **Protagonists:** Bright, energetic, heroic
- **Antagonists:** Slightly gruff, comedic villain (not scary)
- **Supporting:** Varied — squeaky sidekick, wise elder, etc.
- Curate a library of 8-10 ElevenLabs voices mapped to character archetypes

### A2. Emotion-Driven Voice Settings
- ElevenLabs supports per-request `stability`, `similarity_boost`, `style`, `use_speaker_boost`
- Map screenplay `emotion` field to voice settings:
  - `angry` → lower stability (0.3), higher style
  - `nervous/whispering` → higher stability (0.8), lower volume
  - `excited` → lower stability (0.4), speaker boost on
  - `dismissive` → high stability (0.7), flat delivery
- This is free — just parameter tuning on existing API

### A3. Voice Speed + Pacing
- Use ElevenLabs `speed` parameter or SSML-like control
- Short punchy lines → slightly faster
- Dramatic reveals → slightly slower
- Narrator → measured, cinematic pace

---

## Phase B: Background Music

### B1. AI-Generated Soundtrack (ElevenLabs or Suno)
- Each screenplay scene has a `music_mood` field (e.g. "tense, building", "sneaky, comedic")
- **Option 1: ElevenLabs Sound Effects API** — can generate short music loops
- **Option 2: Suno API** — generate 10-15 second music clips per mood
- **Option 3: Pre-built library** — curate 10-15 royalty-free loops tagged by mood, store in Supabase Storage `assets/music/`
- Start with Option 3 (fastest, most reliable), upgrade to AI-gen later

### B2. Music Moods Library
```
tense / suspenseful    — low strings, percussion build
sneaky / comedic       — pizzicato, light woodwinds  
heroic / triumphant    — brass fanfare, drums
sad / emotional        — piano, soft strings
action / chase         — fast drums, synth bass
mysterious             — ambient pads, chimes
playful / fun          — ukulele, xylophone, bounce
dramatic               — orchestral swell
```

### B3. Music Mixing Rules
- Background music at 15-20% volume (ducked under dialogue)
- Fade in at scene start (0.5s), fade out at scene end (0.5s)  
- Music volume ducks further during dialogue lines
- Crossfade between scenes if mood changes

---

## Phase C: Sound Effects

### C1. SFX from Screenplay
- Each scene has `sound_effects: ["engine idling", "crowd murmuring"]`
- **Option 1: ElevenLabs Sound Effects API** — generate SFX from text description
- **Option 2: Freesound.org API** — search + download matching SFX (Creative Commons)
- **Option 3: Pre-built SFX library** — curate 30-50 common Lego-world sounds
- Start with ElevenLabs SFX API (most flexible)

### C2. Common Lego World SFX
```
Vehicles:    engine idling, engine revving, truck horn, forklift beep, helicopter
People:      crowd murmuring, crowd cheering, footsteps, gasp, laughter  
Action:      crash, explosion, door slam, glass breaking, siren
Environment: wind, rain, city ambience, construction noise, traffic
Comedy:      boing, slide whistle, record scratch, cartoon pop, rim shot
Lego:        brick clicking (signature sound), building montage clicks
```

### C3. SFX Placement
- Layer SFX at timestamps matching the scene action
- SFX at 40-60% volume (noticeable but not overwhelming)
- Some SFX loop for duration (ambience), some are one-shot (crash)

---

## Phase D: Assembly Audio Mix

### D1. Professional Audio Layering (FFmpeg)
```
Layer 0: Scene video (original audio muted or at 5%)
Layer 1: Background music (15-20%, ducked during dialogue)
Layer 2: Sound effects (40-60%)  
Layer 3: Dialogue (100%)
Layer 4: Narrator (100%, with slight reverb for cinematic feel)
```

### D2. Audio Processing
- Normalize all dialogue to consistent volume (-16 LUFS)
- Add slight reverb to narrator (FFmpeg `aecho` filter)
- Compress dynamic range on dialogue (FFmpeg `acompressor`)
- Master limiter on final mix to prevent clipping

### D3. Transitions
- Crossfade audio between scenes (0.3-0.5s)
- Music swell before narrator intro/outro
- Brief silence (0.2s) before dramatic dialogue reveals

---

## Phase E: Narrator Upgrade

### E1. Cinematic Narrator Style
- Pick an ElevenLabs voice that sounds like a movie trailer narrator
- Add "cinematic" system prompt to screenplay generation:
  - Narrator intro should build tension/excitement
  - Narrator outro should feel like a satisfying conclusion
  - Short, punchy sentences — not walls of text

### E2. Narrator Audio Post-Processing
- Slight bass boost (FFmpeg `equalizer` filter)
- Subtle reverb for "movie theater" feel
- Normalize to -14 LUFS (slightly louder than dialogue)

---

## Build Order (recommended)

1. **A1 + A2** — Better voices + emotion settings (biggest impact, easiest change)
2. **B1 + B3** — Pre-built music library + mixing rules (fills the silence)
3. **D1** — Proper audio layering in FFmpeg (makes everything gel)
4. **C1** — SFX generation via ElevenLabs API
5. **E1 + E2** — Narrator polish
6. **B1 upgrade** — AI-generated music per scene (Suno)

---

## API Costs (estimated per movie)

| Component | API | Cost |
|-----------|-----|------|
| Dialogue (8-12 lines) | ElevenLabs TTS | ~$0.10-0.20 |
| Narrator (intro + outro) | ElevenLabs TTS | ~$0.05 |
| SFX (6-10 effects) | ElevenLabs SFX | ~$0.10 |
| Music (3-5 loops) | Pre-built library | $0 |
| Music (AI-gen, future) | Suno API | ~$0.20 |
| **Total** | | **~$0.25-0.55** |
