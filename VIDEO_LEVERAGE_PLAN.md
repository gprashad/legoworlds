# LEGO WORLDS — Video Walkthrough Leverage Plan

> **The insight:** When a kid records a walkthrough video of their Lego build, they're giving us EVERYTHING — the full spatial layout, every angle, every character, what matters to them, and the story in their own words and voice. We're currently throwing away 90% of this richness by extracting a few frames and a text transcript. This plan fixes that.

---

## What We're Losing Today

| What the kid gives us | What we use | What we throw away |
|---|---|---|
| 30-60s of panning video showing the full build | 4-6 static frames | The spatial relationships, transitions between areas, depth |
| Narration with emphasis, excitement, pointing | Flat text transcript | Which characters/areas the kid cares most about |
| The kid's actual voice | Nothing | Could be the behind-the-scenes narration |
| Pointing and pausing on key elements | Nothing | Natural "camera direction" for what to focus on |
| The sequence they show things in | Nothing | Natural story order — they show the setup, then the conflict |

---

## Phase 1: Send Video Directly to Claude Vision

### The Change
Instead of only sending extracted frames to Claude Vision for the scene bible, send the **actual video file**. Claude Vision supports video input — it can watch the walkthrough and understand spatial relationships, character positions, and the full layout far better than static frames.

### How It Works
```
Current:  Extract frames → Send frames to Claude Vision → Scene bible
Upgraded: Send full video to Claude Vision → Much richer scene bible
          Also send frames as supplementary stills for detail
```

### What Claude Vision Gets From Video That Frames Miss
- **Spatial layout** — "the shop is BEHIND the truck, not next to it"
- **Scale relationships** — "the crowd is much larger than it appears in any single frame"
- **Hidden elements** — things only visible from certain angles during the pan
- **The kid's focus** — they linger on what matters, rush past what doesn't
- **Continuity** — understanding that elements in different frames are the same build

### Implementation
```python
async def analyze_scene_with_video(scene_id: str, backstory: str):
    """Send the walkthrough video + frames to Claude Vision."""
    
    # Get the original video as base64
    video_b64 = download_video_as_base64(scene_id)
    
    # Also get frames for supplementary detail
    photos_b64 = download_photos_as_base64(scene_id)
    
    content = []
    
    # Video first — Claude watches the full walkthrough
    if video_b64:
        content.append({
            "type": "video",  # Claude Vision video support
            "source": {"type": "base64", "media_type": "video/mp4", "data": video_b64}
        })
        content.append({
            "type": "text",
            "text": "Above: The builder's walkthrough video of their Lego scene."
        })
    
    # Then frames for detail
    for photo in photos_b64:
        content.append({"type": "image", "source": {...}})
    
    content.append({
        "type": "text",
        "text": f"""
        Backstory: {backstory}
        
        You just watched the builder's walkthrough video of their Lego scene.
        
        Pay close attention to:
        1. The FULL spatial layout — where everything is relative to everything else
        2. What the builder pauses on or returns to — those are the important elements
        3. Every minifig visible from ANY angle during the pan
        4. The sequence they show things — this hints at the story structure
        5. Background elements only visible at certain angles
        
        Create a detailed scene bible...
        """
    })
```

---

## Phase 2: Use the Kid's Voice as Behind-the-Scenes Narration

### The Change
The kid's original voiceover from the walkthrough video becomes the "behind the scenes" narration in the final movie. This is the most authentic, emotional part — it's THEIR voice talking about THEIR creation.

### How It Works
```
Current:  Extract audio → Whisper transcript → text backstory → AI narrator reads backstory
Upgraded: Extract audio → Clean up (noise reduction) → Use as behind-the-scenes voiceover
          Also transcribe for backstory text (for screenplay generation)
```

### Implementation
```python
async def process_video_audio(video_path: str, scene_id: str):
    # Extract clean audio
    audio_path = extract_audio(video_path)
    
    # Noise reduction (FFmpeg highpass + lowpass + volume normalize)
    clean_audio = clean_narration_audio(audio_path)
    
    # Upload as the scene's voiceover (used in behind-the-scenes intro)
    upload_to_storage(f"scenes/{scene_id}/input/voiceover.webm", clean_audio)
    update_scene(scene_id, voiceover_url=public_url)
    
    # Also transcribe for backstory text
    transcript = await whisper_transcribe(audio_path)
    update_scene(scene_id, backstory=transcript)
```

### Audio Cleanup Pipeline (FFmpeg)
```
Raw phone audio → highpass 100Hz (remove rumble) 
                → lowpass 8000Hz (remove hiss)
                → volume normalize to -16 LUFS
                → noise gate (remove silence gaps)
                → output as clean voiceover
```

---

## Phase 3: Smart Frame Extraction Based on Narration

### The Change
Instead of extracting frames at even intervals, extract frames at **moments that match what the kid is talking about**. When they say "see this dragon?", grab the frame where the dragon is in view.

### How It Works
```
Current:  Extract frames every N seconds, evenly spaced
Upgraded: 1. Transcribe with timestamps (Whisper verbose mode)
          2. Identify key moments: character introductions, conflict descriptions
          3. Extract frames at those timestamps
          4. Also extract at regular intervals for coverage
```

### Implementation
```python
async def smart_frame_extraction(video_path: str, scene_id: str):
    # Get timestamped transcript
    transcript = await whisper_transcribe_verbose(audio_path)
    # Returns: [{"start": 3.2, "end": 5.1, "text": "this is the king"}, ...]
    
    # Identify key moments using Claude
    key_moments = await identify_key_moments(transcript)
    # Returns: [{"timestamp": 3.5, "description": "introducing the king"},
    #           {"timestamp": 12.0, "description": "showing the dragon"},
    #           {"timestamp": 20.0, "description": "the market area"}]
    
    # Extract frames at key moments
    for moment in key_moments:
        frame = extract_frame_at(video_path, moment["timestamp"])
        # Tag the frame with what it shows
        upload_frame(frame, label=moment["description"])
    
    # Also extract regular interval frames for coverage
    regular_frames = extract_regular_frames(video_path, interval=5)
```

### Whisper Verbose Mode
```python
response = openai.audio.transcriptions.create(
    model="whisper-1",
    file=audio_file,
    response_format="verbose_json",  # Gives timestamps per segment
    timestamp_granularities=["segment"],
)
# Returns segments with start/end timestamps
```

---

## Phase 4: Natural Camera Direction from Video

### The Change
The kid's walkthrough IS a camera direction document. The order they show things, where they linger, the pan direction — all of this should inform how the screenplay structures its camera movements.

### How It Works
```
Current:  Screenplay camera directions are generic ("wide establishing shot")
Upgraded: Camera directions reference the kid's actual walkthrough
          "Start from the angle shown at 0:05 in the walkthrough, then pan 
           left like the builder does at 0:12"
```

### Implementation
Add to the screenplay prompt:
```
The builder recorded a walkthrough video. Here's what they showed:
- 0:00-0:05: Wide shot from above, showing the full layout
- 0:05-0:12: Pans left to show the yellow bulldozer
- 0:12-0:18: Moves down to the crowd on the sidewalk
- 0:18-0:25: Zooms in on the forklift and crates
- 0:25-0:30: Pulls back to show the full scene

Use similar camera movements in the screenplay — these are the angles 
that show the scene best because the builder chose them naturally.
```

---

## Phase 5: Video as Primary Reference for Kie.ai

### The Change
Instead of sending only extracted frames to Kie.ai, also pass context about what the frame shows and what's happening spatially. The visual-first prompt gets enriched with video-derived spatial understanding.

### How It Works
The scene bible now contains richer spatial information from Claude watching the video:
```json
{
  "spatial_layout": {
    "overview": "Rectangular baseplate, buildings on right, road through center, vehicles on left",
    "depth": "Three layers: foreground (road + vehicles), midground (crowd + shop), background (train tracks)",
    "key_angles": [
      {"description": "Overhead shows full layout best", "frame": "frame_00.jpg"},
      {"description": "Low angle from road level shows the blockade drama", "frame": "frame_03.jpg"}
    ]
  }
}
```

This spatial data feeds into the video-first prompts:
```
"Three-layer Lego scene: foreground has yellow bulldozer and dark blue truck 
on gray road. Midground has 12 minifigs on sidewalk near green shop. 
Background shows train tracks. Shot from overhead at 45 degrees."
```

---

## Build Order

1. **Send video to Claude Vision** — biggest impact, straightforward change to scene_analysis.py
2. **Kid's voice as behind-the-scenes** — extract + clean audio, store as voiceover
3. **Smart frame extraction** — Whisper verbose timestamps → extract frames at key narration moments
4. **Camera direction from walkthrough** — analyze pan/movement → inform screenplay camera notes
5. **Enriched spatial data** — video-derived layout info → better Kie.ai prompts

---

## Cost Impact

| Component | Current | Upgraded | Delta |
|---|---|---|---|
| Scene analysis | Claude Vision (frames only) | Claude Vision (video + frames) | +$0.02-0.05 (video tokens) |
| Transcription | Whisper basic | Whisper verbose + moment analysis | +$0.01 |
| Frame extraction | FFmpeg (free) | FFmpeg + Claude moment analysis | +$0.01 |
| Audio cleanup | N/A | FFmpeg (free) | $0 |
| **Total per movie** | | | **+$0.03-0.07** |

---

## The Vision

Kid picks up phone → records 30 seconds panning around their build while narrating → uploads → platform watches the video, hears the story, extracts the best angles, understands the spatial layout, cleans up the narration → screenplay references the actual build from angles the kid showed → video generation starts from the exact reference photo → final movie includes the kid's own voice in the behind-the-scenes intro → kid watches a movie of THEIR scene, narrated by THEIR voice, with characters THEY introduced.

That's the magic. It's their world, amplified.
