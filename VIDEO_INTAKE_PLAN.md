# LEGO WORLDS — Video Intake Plan

> **Feature:** Kid records a video of their Lego scene, narrating the backstory as they pan around. The platform extracts frames as reference photos, transcribes the voiceover as the backstory, and uses both to drive the pipeline.
>
> **Why this matters:** This is the most natural way a kid interacts — they pick up a phone, hit record, talk about what they built while showing it off. No typing, no separate photo uploads. One video = everything we need.

---

## User Experience

### The Flow

1. Kid builds a Lego scene
2. Opens phone camera (or the web app) and records a 15-60 second video
3. While recording, pans around the scene and narrates: *"So this is my city. The bulldozer guy is corrupt, he's trying to tear down the shop. See all these people? They found out and they're blocking the truck..."*
4. Sends the video via:
   - **Web app** — upload in the workspace (drag-drop or file picker)
   - **Text/MMS** — text the video to the Lego Worlds number
   - **Email** — email the video to scenes.legoworlds@gmail.com
5. Platform automatically:
   - Extracts key frames from the video as reference photos
   - Transcribes the voiceover as the backstory
   - Uses both to create the scene bible + screenplay
6. Kid opens the web app and sees their scene ready — photos extracted, backstory transcribed, ready to review or hit "Make My Movie"

### What the Kid Sees

- Upload a video → "Processing your video..." (10-15 seconds)
- Scene workspace shows:
  - Extracted frames as the photo grid (auto-populated)
  - Transcribed narration as the backstory (auto-populated, editable)
  - The original video in the media section (playable)
  - "Make My Movie" button ready if 2+ frames + backstory length met

---

## Technical Architecture

### Step 1: Video Upload

The video arrives via one of three channels:

```
Web Upload:  frontend → POST /api/scenes/:id/media/upload → Supabase Storage
SMS/MMS:     Twilio webhook → download from Twilio → Supabase Storage
Email:       Gmail IMAP → extract attachment → Supabase Storage
```

All three already handle video files (we added video support to intake). The video lands at:
```
scenes/{scene_id}/input/video_original.mp4
```

### Step 2: Frame Extraction (FFmpeg)

Extract key frames from the video to use as reference photos for the pipeline.

```python
async def extract_key_frames(video_path: str, output_dir: str, max_frames: int = 6) -> list[str]:
    """Extract evenly-spaced key frames from video.
    
    Strategy:
    - Get video duration
    - Extract frames at evenly-spaced intervals (skip first/last 10%)
    - Also extract frames at scene-change points (ffmpeg scene detection)
    - Deduplicate similar frames (perceptual hash)
    - Return 4-6 best frames as JPEGs
    """
    
    # Get duration
    duration = get_video_duration(video_path)
    
    # Extract at intervals (skip first/last 10% — usually shaky start/end)
    start = duration * 0.1
    end = duration * 0.9
    interval = (end - start) / (max_frames + 1)
    
    frames = []
    for i in range(max_frames):
        timestamp = start + interval * (i + 1)
        output = f"{output_dir}/frame_{i:02d}.jpg"
        ffmpeg -ss {timestamp} -i {video} -vframes 1 -q:v 2 {output}
        frames.append(output)
    
    return frames
```

**Why FFmpeg:** Already in the Docker image. Fast, reliable, no extra dependencies.

**Frame selection heuristics:**
- Skip first/last 10% of video (usually shaky start/stop)
- Extract more frames from the middle where the kid is showing the best angles
- Use FFmpeg's scene detection (`-vf "select=gt(scene,0.3)"`) to find natural cut points
- If video is a slow pan, space frames evenly for different angles
- Target 4-6 frames — enough for good reference without redundancy

### Step 3: Audio Transcription

Extract audio from the video and transcribe the kid's narration.

**Option A: OpenAI Whisper API** (recommended)
```python
async def transcribe_video_audio(video_path: str) -> str:
    """Extract audio from video and transcribe with Whisper."""
    
    # Extract audio track
    audio_path = video_path.replace('.mp4', '.wav')
    ffmpeg -i {video} -vn -acodec pcm_s16le -ar 16000 -ac 1 {audio}
    
    # Send to Whisper API
    response = openai.audio.transcriptions.create(
        model="whisper-1",
        file=open(audio_path, "rb"),
        language="en",
        prompt="A kid describing their Lego scene and backstory."
    )
    
    return response.text
```

**Option B: ElevenLabs Speech-to-Text** (if available on plan)

**Option C: Google Cloud Speech-to-Text** (free tier: 60 min/month)

**Recommendation:** OpenAI Whisper — best accuracy for kids' speech, handles background noise, $0.006/min (~$0.01 per video).

### Step 4: Auto-Populate Scene

After extraction + transcription:

```python
async def process_video_intake(scene_id: str, video_storage_path: str):
    """Process an uploaded video: extract frames + transcribe → populate scene."""
    
    # 1. Download video to temp
    video_local = download_from_storage(video_storage_path)
    
    # 2. Extract key frames
    frames = await extract_key_frames(video_local, temp_dir)
    
    # 3. Upload frames as scene photos
    for i, frame_path in enumerate(frames):
        upload_to_storage(f"scenes/{scene_id}/input/frame_{i}.jpg", frame_path)
        register_as_scene_media(scene_id, frame_path, file_type="photo", source="video_extract")
    
    # 4. Transcribe narration
    backstory = await transcribe_video_audio(video_local)
    
    # 5. Update scene with transcribed backstory
    update_scene(scene_id, backstory=backstory)
    
    # 6. Store original video reference
    register_as_scene_media(scene_id, video_storage_path, file_type="video", source="upload")
    
    # 7. Scene is now ready — has photos + backstory
    # Frontend shows extracted frames + transcribed text (editable)
```

### Step 5: Pipeline Integration

The existing pipeline doesn't change — it already works with photos + backstory:

```
Video Upload → [NEW: Extract Frames + Transcribe] → Photos + Backstory → [EXISTING: Scene Analysis → Screenplay → Production → Assembly]
```

The scene bible stage (Claude Vision) will analyze the extracted frames just like uploaded photos. The backstory comes from the transcription instead of typing.

---

## Implementation Details

### Video Processing Endpoint

```
POST /api/scenes/:id/process-video
```

Triggered automatically after a video is uploaded (web) or received (SMS/email). Runs as a background task.

### Frontend Changes

1. **MediaUploader** — detect video files, show processing spinner after upload
2. **SceneWorkspace** — show "Processing your video..." state while frames extract
3. **BackstoryEditor** — auto-fill with transcription, show "Transcribed from your video" label
4. **MediaGrid** — show extracted frames with "From video" badge, original video playable

### SMS/Email Video Flow

When a video arrives via SMS or email:
1. Scene is created (existing behavior)
2. Video is uploaded to Storage (existing behavior)
3. **NEW:** `process_video_intake()` runs automatically
4. Scene gets auto-populated with frames + transcription
5. Reply link sent (existing behavior)
6. When kid opens the link, scene is ready with photos + backstory

### Edge Cases

- **No audio in video** — skip transcription, leave backstory empty, kid can type it
- **Very short video (<5s)** — extract 2-3 frames, warn "try recording a longer video"
- **Very long video (>2min)** — only use first 90 seconds, extract more frames
- **Multiple videos** — append frames and transcriptions
- **Video + separate photos** — merge: video frames + uploaded photos both appear in grid
- **Bad audio quality** — Whisper handles noise well, but show transcription as editable so kid can fix

---

## API Costs

| Component | API | Cost per video |
|-----------|-----|---------------|
| Frame extraction | FFmpeg (local) | $0 |
| Transcription (30s video) | OpenAI Whisper | ~$0.003 |
| Transcription (60s video) | OpenAI Whisper | ~$0.006 |
| **Total** | | **< $0.01** |

---

## Build Order

1. **Frame extraction** — FFmpeg key frame extractor with scene detection + dedup
2. **Whisper transcription** — audio extract → Whisper API → backstory text
3. **`process_video_intake()` function** — orchestrates extraction + transcription + scene population
4. **Backend endpoint** — `POST /api/scenes/:id/process-video` (auto-triggered on video upload)
5. **Frontend** — video processing state, auto-filled backstory with "transcribed" label
6. **SMS/Email auto-processing** — trigger `process_video_intake()` when video attachment detected

---

## Example Flow

Kid records 30-second video panning around a castle scene:

*"OK so this is my castle. The king is up on the tower — see him? He's got the gold crown. And down here the knights are guarding the gate. But this dragon — he's hiding behind the mountain, and he's about to attack. The villagers don't know yet, they're just hanging out in the market..."*

**Platform extracts:**
- Frame 1: Wide shot of full castle (5s mark)
- Frame 2: Close-up of king on tower (10s mark) 
- Frame 3: Knights at the gate (15s mark)
- Frame 4: Dragon behind mountain (20s mark)
- Frame 5: Villagers in market area (25s mark)

**Transcription becomes backstory:**
> "This is my castle. The king is up on the tower, he's got the gold crown. Down here the knights are guarding the gate. But this dragon — he's hiding behind the mountain, and he's about to attack. The villagers don't know yet, they're just hanging out in the market."

**Scene is ready:** 5 photos + backstory + original video. Hit "Make My Movie."
