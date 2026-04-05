# LEGO WORLDS — Project Bible (Pipeline & Backend)

> **Version:** 2.0 | **Author:** Gaurav (CCG Capital / Personal Projects)
> **Status:** Pre-build | **Architecture:** Fully cloud-hosted
> **Dev Machine:** Mac Mini M4 (build only — nothing runs here in production)
> **Build Tool:** Claude Code

---

## 1. Vision

A kid builds a Lego scene, takes a few photos, describes the backstory, and gets back a 60–90 second animated short film where his Lego world comes to life — with voices, sound effects, music, and his actual minifigs as characters.

**The magic:** The kid built the physical scene and wrote the story. The platform is an amplifier, not a replacement. The real Lego photos ground everything — this isn't generic AI Lego content, it's *his* world animated.

---

## 2. User Experience

### The Flow (Kid's POV)

1. Kid finishes building a Lego scene
2. Takes 3–4 photos from different angles
3. Types or voice-records the backstory ("The bulldozer driver is corrupt, he's working with the mayor to tear down the shop. The crowd found out and they're blocking the delivery truck...")
4. Submits via web interface or emails/texts photos to the platform
5. Gets back a screenplay for approval ("green light" moment)
6. Receives a 60–90 second animated short film
7. One-click share to TikTok, YouTube, Instagram

### Example Scene (Reference)

From Jackson's build (see uploaded photo):
- Yellow bulldozer blocking a delivery area
- Red forklift operator trying to unload blue crates from a dark blue delivery truck
- ~12 minifigs gathered as a crowd on the sidewalk near a green/tan shop
- Road baseplates with yellow lane markings, curved road sections
- Train tracks visible in the background
- Additional Lego parts/bags visible (active build session)

Backstory example: "The bulldozer driver is corrupt — he's working with the mayor to tear down the shop. The crowd found out and they're blocking the delivery truck until the mayor shows up. The forklift guy is trying to sneak crates out the back before anyone notices."

---

## 3. Architecture Overview

### Design Principle

**Deterministic media pipeline, not an autonomous agent loop.**

This is a sequential, triggered workflow: photos in → movie out → same steps every time. No recurring loops, no autonomous decision-making. Clean functions that can be called in sequence.

### Cloud-First Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌──────────────────┐
│   Netlify    │     │  Railway/Fly    │     │    Supabase      │
│  (Frontend)  │────▶│  (FastAPI +     │────▶│  (Auth, DB,      │
│  React/Vite  │◀────│   Pipeline)     │◀────│   Storage)       │
└─────────────┘     └────────┬────────┘     └──────────────────┘
                             │
                    ┌────────┴────────┐
                    │  External APIs  │
                    │  Claude, Kling, │
                    │  ElevenLabs     │
                    └─────────────────┘

Dev Machine (Mac Mini M4): Code only. Nothing runs here in production.
```

**Key principle:** The backend is stateless. All state lives in Supabase (database + storage). The backend server pulls files from Supabase Storage, processes them via API calls, and pushes results back to Supabase Storage. If the server restarts, jobs can be resumed from their last saved state.

### Pipeline Stages (v1)

```
[INTAKE] → [SCENE UNDERSTANDING] → [SCREENPLAY] → [GREEN LIGHT] → [PRODUCTION] → [ASSEMBLY] → [DELIVERY]
```

| Stage | Input | Output | AI Model | Storage |
|-------|-------|--------|----------|---------|
| Intake | Photos + text prompt | Validated media in Supabase Storage | None | Supabase Storage: `scenes/{id}/input/` |
| Scene Understanding | Photos + prompt | Scene bible (JSON) | Claude Vision | Supabase DB: `scenes.scene_bible` |
| Screenplay | Scene bible | Structured screenplay (JSON) | Claude | Supabase DB: `scenes.screenplay` |
| Green Light | Kid reviews & approves | Approved status | None | Supabase DB: `scenes.status` |
| Production | Screenplay scenes | Video clips + audio files | Kling + ElevenLabs | Supabase Storage: `scenes/{id}/production/` |
| Assembly | Clips + audio + metadata | Final MP4 video | FFmpeg (on server) | Supabase Storage: `scenes/{id}/output/` |
| Delivery | Final video URL | Playable in browser + shareable | None | Supabase Storage public URL |

---

## 4. Detailed Stage Specifications

### Stage 1: Intake

**Implementation:** Web upload (primary), email intake (secondary), SMS/MMS (future).

All uploaded media goes directly to Supabase Storage. No local filesystem.

```
Input:
  - 3-4 JPEG/PNG photos (phone camera quality)
  - Backstory text (typed or voice-transcribed)
  - Optional: voiceover audio recording (from browser MediaRecorder)

Process:
  1. Frontend uploads files to Supabase Storage bucket: scenes/{scene_id}/input/
  2. Creates scene_media records in Supabase DB
  3. Stores backstory text in scenes.backstory column
  4. Validates: minimum 2 photos, backstory 20+ characters

Supabase Storage Structure:
  scenes/
    {scene_id}/
      input/
        photo_1.jpg
        photo_2.jpg
        photo_3.jpg
        photo_4.jpg
        voiceover.webm (optional)
      production/
        video/
          scene_1.mp4
          scene_2.mp4
        audio/
          narrator_intro.mp3
          dialogue_1_1.mp3
      output/
        final.mp4
        thumbnail.jpg
```

### Stage 2: Scene Understanding (Claude Vision)

**Purpose:** Analyze photos and prompt to create a structured "scene bible" — the source of truth for all downstream stages.

```
Input:
  - All photos downloaded from Supabase Storage (as base64)
  - Backstory prompt text from DB

Output: Stored as JSON in scenes.scene_bible column
  {
    "job_id": "uuid",
    "title": "The Corrupt Bulldozer",
    "genre": "drama/action",
    "mood": "tense, conspiratorial",
    "setting": {
      "description": "A city block with a shop, parking area, and road",
      "locations": [
        { "id": "shop", "description": "Green and tan corner shop with windows", "position": "upper right" },
        { "id": "road", "description": "Gray road with yellow lane markings and curved section", "position": "center" },
        { "id": "parking", "description": "Open area in front of shop", "position": "center right" }
      ]
    },
    "cast": [
      {
        "id": "bulldozer_driver",
        "description": "Minifig operating the yellow bulldozer",
        "role": "antagonist",
        "backstory": "Corrupt, working with the mayor",
        "visual_details": "Seated in yellow construction vehicle"
      },
      {
        "id": "forklift_operator",
        "description": "Minifig in the red forklift",
        "role": "supporting",
        "backstory": "Trying to sneak crates out before anyone notices",
        "visual_details": "Orange hair/helmet, operating red forklift"
      },
      {
        "id": "crowd",
        "description": "Group of ~12 minifigs on the sidewalk",
        "role": "protagonists",
        "backstory": "Discovered the corruption, protesting",
        "visual_details": "Mixed clothing colors, gathered in a group"
      }
    ],
    "vehicles": [
      { "id": "bulldozer", "type": "construction", "color": "yellow", "operator": "bulldozer_driver" },
      { "id": "forklift", "type": "warehouse", "color": "red", "operator": "forklift_operator" },
      { "id": "delivery_truck", "type": "cargo", "color": "dark blue", "cargo": "blue crates" }
    ],
    "props": [
      { "id": "crates", "description": "Blue shipping crates", "location": "near delivery truck" }
    ],
    "key_conflicts": [
      "Bulldozer blocking the area vs. crowd protesting",
      "Forklift operator sneaking crates vs. crowd awareness"
    ]
  }
```

**Claude Vision Prompt Strategy:**

```
System: You are a film director's assistant analyzing a physical Lego scene 
to prepare for production. You will receive photos of a Lego build and a 
backstory from the builder. Your job is to create a detailed scene bible 
that maps every visible element to the narrative.

Analyze the photos carefully:
1. Identify every distinct minifig (describe clothing, hair, accessories)
2. Identify all vehicles and their current positions
3. Map the physical layout (buildings, roads, open areas)
4. Note any props, cargo, signage, or details
5. Cross-reference with the backstory to assign roles and motivations

Output as JSON matching the scene_bible schema.
Be specific about visual details — these will be used as reference for 
video generation prompts.
```

### Stage 3: Screenplay (Claude)

**Purpose:** Transform scene bible + backstory into a structured screenplay with 3-5 scenes.

```
Input:
  - scene_bible JSON from DB
  - Original backstory text from DB

Output: Stored as JSON in scenes.screenplay column
  {
    "title": "The Corrupt Bulldozer",
    "total_scenes": 4,
    "estimated_duration_seconds": 75,
    "scenes": [
      {
        "scene_number": 1,
        "title": "The Blockade",
        "duration_seconds": 20,
        "location": "road",
        "camera": {
          "angle": "wide establishing shot",
          "movement": "slow push-in from overhead",
          "reference_photo": "photo_1.jpg"
        },
        "action": "The yellow bulldozer sits blocking the delivery area. The dark blue truck idles behind it. The crowd begins to gather on the sidewalk.",
        "dialogue": [
          {
            "character": "crowd_leader",
            "line": "They can't do this! The mayor promised that shop would stay!",
            "emotion": "angry"
          },
          {
            "character": "bulldozer_driver",
            "line": "I got my orders. Take it up with city hall.",
            "emotion": "dismissive"
          }
        ],
        "sound_effects": ["engine idling", "crowd murmuring"],
        "music_mood": "tense, building"
      },
      {
        "scene_number": 2,
        "title": "The Sneak",
        "duration_seconds": 15,
        "location": "parking",
        "camera": {
          "angle": "low angle from ground level",
          "movement": "tracking shot following forklift",
          "reference_photo": "photo_3.jpg"
        },
        "action": "While the crowd is focused on the bulldozer, the forklift operator quietly loads crates from the delivery truck, trying to move them before anyone notices.",
        "dialogue": [
          {
            "character": "forklift_operator",
            "line": "Easy... easy... nobody's looking...",
            "emotion": "nervous, whispering"
          }
        ],
        "sound_effects": ["forklift beeping", "crate sliding"],
        "music_mood": "sneaky, comedic"
      }
    ],
    "narrator_intro": "In a city where deals are made behind closed doors, one bulldozer driver is about to learn that you can't bulldoze the truth.",
    "narrator_outro": "And so the people of Block Street saved their shop — proving that sometimes, the biggest builds start with the smallest bricks.",
    "credits": {
      "directed_by": "Jackson",
      "built_by": "Jackson",
      "produced_by": "Lego Worlds AI"
    }
  }
```

**Screenplay Prompt Strategy:**

```
System: You are a children's film screenwriter. You write short, punchy, 
fun screenplays for animated shorts based on Lego scenes built by kids.

Rules:
- 3-5 scenes, total runtime 60-90 seconds
- Dialogue should be fun, age-appropriate, slightly dramatic
- Each scene must reference a specific area of the physical build
- Include camera directions that reference the actual photos
- Add a narrator intro and outro that feel cinematic but playful
- The kid who built this is the director — credit them
- Keep action descriptions vivid but brief
- Include sound effect and music mood notes for production

Output as JSON matching the screenplay schema.
```

**Green Light Step:** After screenplay generation, the frontend displays the screenplay as visual storyboard cards. Kid reviews, optionally requests revisions, then hits "Green Light" to approve. This triggers production.

### Stage 4: Production (Multi-Model)

**Purpose:** Generate video clips and audio for each scene. All intermediate files stored in Supabase Storage.

#### 4a: Video Generation (Kling API)

```
Process:
  1. Download reference photo from Supabase Storage
  2. Construct Kling prompt per scene (action + camera + style directive)
  3. Style: "Stop-motion animated Lego scene, cinematic lighting, 
     shallow depth of field, real Lego pieces, maintain exact appearance 
     from reference photo"
  4. Generate 5-10 second clip per scene
  5. Upload clip to Supabase Storage: scenes/{id}/production/video/scene_{n}.mp4
  6. Update job progress in DB

Parameters:
  - Mode: image-to-video (using reference photo)
  - Duration: 5-10 seconds per scene
  - Character consistency: Kling Elements if available
```

#### 4b: Voice Generation (ElevenLabs API)

```
Process:
  1. Assign distinct ElevenLabs voice per character role
  2. Generate audio for each dialogue line + narrator intro/outro
  3. Upload to Supabase Storage: scenes/{id}/production/audio/

Parameters:
  - Model: eleven_multilingual_v2
  - Stability: 0.5
  - Style: matched to emotion field from screenplay
```

#### 4c: Sound Effects & Music

```
v1: Bundle small SFX/music library with backend deployment
    or store in Supabase Storage bucket: assets/sfx/, assets/music/
    Map screenplay sound_effects and music_mood to library files

Future: AI music generation (Suno, Udio), ElevenLabs SFX API
```

### Stage 5: Assembly (FFmpeg on Cloud Server)

**Purpose:** Stitch everything into a polished final video. FFmpeg runs on the Railway/Fly server.

```
Process:
  1. Download all production assets from Supabase Storage to /tmp/legoworlds/{job_id}/

  2. Create "Behind the Scenes" intro segment:
     - Ken Burns pan/zoom slideshow of real Lego photos (3-5 sec per photo)
     - Layer kid's voiceover audio (if recorded) or AI narrator reading backstory
     - Subtle background music
     - Duration: 15-20 seconds
  
  3. Create transition: photos dissolve into animated movie

  4. Title cards: "LEGO WORLDS presents..." → "A film by Jackson" → Movie title

  5. For each scene:
     - Base: video clip
     - Layer 1: background music (low volume)
     - Layer 2: sound effects
     - Layer 3: dialogue lines
     - Crossfade transitions (0.5s)
  
  6. Narrator outro + credits sequence

  7. Encode: MP4 (H.264 + AAC), 1080p, 24fps, stereo

  8. Upload final.mp4 + thumbnail.jpg to Supabase Storage: scenes/{id}/output/
  9. Update scenes.final_video_url in DB
  10. Clean up /tmp directory
```

### Stage 6: Delivery

```
  1. Final video URL = Supabase Storage signed/public URL
  2. Frontend displays video in browser player
  3. Download button → direct download link
  4. Share flow → Ayrshare API for TikTok/YouTube/Instagram
  5. Scene status → COMPLETE
  6. Browser notification if kid navigated away
```

---

## 5. Tech Stack

### Dependencies

```
Core:
  anthropic          — Claude API (vision + text)
  elevenlabs         — Voice generation
  httpx              — Async HTTP for Kling API
  ffmpeg-python      — FFmpeg wrapper
  Pillow             — Image processing/validation
  pydantic           — Data models / schema validation
  supabase           — Supabase client (storage + DB + auth)

Server:
  fastapi            — API server
  uvicorn            — ASGI server
  python-multipart   — File upload handling

Infrastructure:
  python-dotenv      — Env vars (dev only)
  logging            — Structured logging
```

### External Services

| Service | Purpose | Hosting |
|---------|---------|---------|
| Supabase | Auth (Google SSO), PostgreSQL DB, File Storage | Supabase Cloud (free tier) |
| Netlify | Frontend hosting | Netlify (free tier) |
| Railway or Fly.io | Backend API + pipeline | Railway (~$5/mo hobby) |
| Anthropic Claude API | Vision + screenplay | API |
| Kling AI API | Video generation | API (existing BennyBot account) |
| ElevenLabs API | Voice acting + narration | API (existing BennyBot account) |
| Ayrshare | Social posting | API (existing BennyBot account) |

### Development Environment

```
Machine: Mac Mini M4 (bennybotai@192.168.234.147)
Purpose: Development ONLY — SSH in, run Claude Code, write/test code
Deploy: Git push → auto-deploy (Netlify for frontend, Railway for backend)
```

---

## 6. Project Structure (Monorepo)

```
~/legoworlds/
├── README.md
├── BIBLE.md                    ← This file
├── FRONTEND_BIBLE.md           ← Frontend design & architecture
├── .gitignore
│
├── backend/
│   ├── Dockerfile              ← For Railway/Fly (includes FFmpeg)
│   ├── requirements.txt
│   ├── .env                    ← Local dev only
│   ├── .env.example
│   │
│   ├── src/
│   │   ├── __init__.py
│   │   ├── config.py           ← Settings, Supabase client init
│   │   ├── models.py           ← Pydantic models
│   │   ├── pipeline.py         ← Main orchestrator
│   │   ├── supabase_client.py  ← Storage + DB helpers
│   │   │
│   │   ├── stages/
│   │   │   ├── __init__.py
│   │   │   ├── intake.py
│   │   │   ├── scene_analysis.py
│   │   │   ├── screenplay.py
│   │   │   ├── production.py
│   │   │   ├── assembly.py
│   │   │   └── delivery.py
│   │   │
│   │   ├── prompts/
│   │   │   ├── scene_analysis.txt
│   │   │   └── screenplay.txt
│   │   │
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   ├── ffmpeg.py
│   │   │   ├── audio.py
│   │   │   ├── image.py
│   │   │   └── storage.py      ← Supabase upload/download helpers
│   │   │
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── server.py
│   │       ├── auth.py         ← Supabase JWT verification
│   │       ├── routes_scenes.py
│   │       ├── routes_media.py
│   │       ├── routes_pipeline.py
│   │       ├── routes_share.py
│   │       └── routes_intake.py
│   │
│   ├── assets/
│   │   ├── sfx/
│   │   └── music/
│   │
│   └── tests/
│
├── frontend/                   ← See FRONTEND_BIBLE.md
│   ├── package.json
│   ├── vite.config.ts
│   ├── netlify.toml
│   └── src/
│
└── docs/
    ├── deployment.md
    └── api.md
```

---

## 7. Data Models (Pydantic)

```python
from pydantic import BaseModel
from typing import Optional
from enum import Enum

class Genre(str, Enum):
    ACTION = "action"
    COMEDY = "comedy"
    DRAMA = "drama"
    ADVENTURE = "adventure"
    MYSTERY = "mystery"
    SCIFI = "sci-fi"

class CastMember(BaseModel):
    id: str
    description: str
    role: str
    backstory: str
    visual_details: str

class Vehicle(BaseModel):
    id: str
    type: str
    color: str
    operator: Optional[str] = None
    cargo: Optional[str] = None

class Location(BaseModel):
    id: str
    description: str
    position: str

class Prop(BaseModel):
    id: str
    description: str
    location: str

class SceneBible(BaseModel):
    job_id: str
    title: str
    genre: str
    mood: str
    setting: dict
    cast: list[CastMember]
    vehicles: list[Vehicle]
    props: list[Prop]
    key_conflicts: list[str]

class DialogueLine(BaseModel):
    character: str
    line: str
    emotion: str

class CameraDirection(BaseModel):
    angle: str
    movement: str
    reference_photo: str

class Scene(BaseModel):
    scene_number: int
    title: str
    duration_seconds: int
    location: str
    camera: CameraDirection
    action: str
    dialogue: list[DialogueLine]
    sound_effects: list[str]
    music_mood: str

class Credits(BaseModel):
    directed_by: str
    built_by: str
    produced_by: str = "Lego Worlds AI"

class Screenplay(BaseModel):
    title: str
    total_scenes: int
    estimated_duration_seconds: int
    scenes: list[Scene]
    narrator_intro: str
    narrator_outro: str
    credits: Credits

class SceneStatus(str, Enum):
    DRAFT = "draft"
    READY = "ready"
    ANALYZING = "analyzing"
    SCREENPLAY_REVIEW = "screenplay_review"
    APPROVED = "approved"
    PRODUCING = "producing"
    ASSEMBLING = "assembling"
    COMPLETE = "complete"
    PUBLISHED = "published"
    FAILED = "failed"

class JobStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    WRITING = "writing"
    AWAITING_APPROVAL = "awaiting_approval"
    PRODUCING = "producing"
    ASSEMBLING = "assembling"
    COMPLETE = "complete"
    FAILED = "failed"
```

---

## 8. Configuration

### Backend Environment Variables

```bash
# Supabase
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
SUPABASE_JWT_SECRET=...

# Claude API
ANTHROPIC_API_KEY=sk-ant-...

# Kling AI
KLING_API_KEY=...
KLING_API_BASE_URL=https://api.klingai.com/v1

# ElevenLabs
ELEVENLABS_API_KEY=...

# Ayrshare
AYRSHARE_API_KEY=...

# Server
PORT=8000
ENVIRONMENT=production
ALLOWED_ORIGINS=https://legoworlds.netlify.app,http://localhost:5173

# Pipeline
MAX_SCENES=5
MIN_SCENES=3
TARGET_DURATION_SECONDS=75
SCENE_CLIP_DURATION_SECONDS=8

# Storage
SUPABASE_STORAGE_BUCKET=legoworlds
TEMP_DIR=/tmp/legoworlds

# Logging
LOG_LEVEL=INFO
```

### Frontend Environment Variables

```bash
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
VITE_API_URL=https://legoworlds-api.up.railway.app
```

---

## 9. Deployment

### Backend — Railway

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
```

- Connect GitHub repo → set root directory to `/backend`
- Set env vars in Railway dashboard
- Auto-deploys on git push

### Frontend — Netlify

- Connect GitHub repo → set root directory to `/frontend`
- Build: `npm run build` → Publish: `dist`
- Set env vars in Netlify dashboard
- Auto-deploys on git push

### Supabase Storage Policies

```sql
-- Users upload to their own scene folders
create policy "Users upload to own scenes" on storage.objects for insert
to authenticated with check (
  bucket_id = 'legoworlds' 
  and (storage.foldername(name))[1] = 'scenes'
  and exists (select 1 from scenes where id::text = (storage.foldername(name))[2] and user_id = auth.uid())
);

-- Users read their own scene files
create policy "Users read own scenes" on storage.objects for select
to authenticated using (
  bucket_id = 'legoworlds'
  and (storage.foldername(name))[1] = 'scenes'
  and exists (select 1 from scenes where id::text = (storage.foldername(name))[2] and user_id = auth.uid())
);
```

---

## 10. Build Phases

### Phase 1: Full Stack MVP (Week 1-2)

**Backend (Days 1-6):**
1. Scaffolding, Dockerfile, FastAPI, Supabase client, auth middleware
2. Scene CRUD + media upload endpoints
3. Scene analysis stage (Claude Vision)
4. Screenplay stage + pipeline orchestrator
5. Production stage (Kling + ElevenLabs)
6. Assembly stage (FFmpeg) + end-to-end test

**Frontend (Days 1-5, parallel):**
1. Vite + React + Tailwind + Supabase Auth (Google SSO)
2. Scene library + workspace pages
3. Media upload + backstory editor + Make My Movie button
4. Screenplay review page + green light flow
5. Progress tracker + movie player

**Success Criteria:** Upload photos → write backstory → make movie → review screenplay → green light → watch video in browser.

### Phase 2: Polish (Week 3)

- Voiceover recording, behind-the-scenes intro
- Email intake, social sharing
- Design polish, animations, mobile

### Phase 3: Scale (Week 4+)

- SMS intake, gallery, sequel support, custom voices

---

## 11. API Integration Code Patterns

### Supabase Storage Helper

```python
from supabase import create_client
import base64

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

async def download_from_storage(path: str) -> bytes:
    return supabase.storage.from_("legoworlds").download(path)

async def upload_to_storage(path: str, data: bytes, content_type: str):
    supabase.storage.from_("legoworlds").upload(path, data, {"content-type": content_type})

async def get_public_url(path: str) -> str:
    return supabase.storage.from_("legoworlds").get_public_url(path)

async def download_photos_as_base64(scene_id: str) -> list[str]:
    files = supabase.storage.from_("legoworlds").list(f"scenes/{scene_id}/input/")
    photos = []
    for f in files:
        if f["name"].endswith((".jpg", ".jpeg", ".png")):
            data = await download_from_storage(f"scenes/{scene_id}/input/{f['name']}")
            photos.append(base64.b64encode(data).decode())
    return photos
```

### Claude Vision Call

```python
import anthropic

client = anthropic.Anthropic()

async def analyze_scene(scene_id: str, backstory: str):
    photos_b64 = await download_photos_as_base64(scene_id)
    content = []
    for photo in photos_b64:
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": photo}})
    content.append({"type": "text", "text": f"Backstory: {backstory}\n\n{SCENE_ANALYSIS_PROMPT}"})
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=SCENE_ANALYSIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}]
    )
    return parse_scene_bible(message.content[0].text)
```

---

## 12. Quality Gates

- [ ] Every visible minifig identified and described
- [ ] 3-5 scenes, 60-90 seconds total (plus behind-the-scenes intro)
- [ ] Dialogue is fun, age-appropriate, slightly dramatic
- [ ] Video clips feel like the actual Lego build animated
- [ ] Behind-the-scenes intro shows real photos with voiceover
- [ ] Smooth transition from real photos to animated movie
- [ ] Credits include the kid's name as director
- [ ] Watchable and fun — would a kid be excited to show friends?

---

## 13. Known Challenges & Mitigations

| Challenge | Mitigation |
|-----------|-----------|
| Kling quality varies | Reference photos + prompt iteration + generate 2 per scene, pick best |
| Character consistency | Kling Elements (same as BennyBot) |
| Pipeline latency (10-20 min) | Green light break point + browser notification on completion |
| FFmpeg on cloud | Docker image with FFmpeg, process in /tmp, clean up |
| Supabase Storage limits | Free tier 1GB, monitor usage |
| Railway timeout on long jobs | FastAPI BackgroundTasks for async processing |
| Cost per movie | ~$2-3 per movie (Claude + Kling + ElevenLabs) + ~$5/mo hosting |

---

## 14. Future Roadmap

- iMessage intake (Mac Mini as relay)
- Multiple output styles (stop-motion, cartoon, realistic)
- Sequel support
- Collaborative multi-kid movies
- AI music generation
- Print storybook (PDF)
- Multi-family SaaS

---

## 15. Claude Code Kickoff Prompt

```
Read BIBLE.md and FRONTEND_BIBLE.md in this directory. These are the complete 
project specs for Lego Worlds — a platform that turns kids' Lego photos into 
animated short films.

Architecture: Fully cloud-hosted.
- Frontend: React/TypeScript/Vite on Netlify
- Backend: FastAPI/Python on Railway (Docker with FFmpeg)
- Database + Auth + Storage: Supabase

Scaffold the monorepo structure from BIBLE.md Section 6:
- /backend with FastAPI, Dockerfile, requirements.txt
- /frontend with React/Vite/Tailwind

Then build Phase 1 from BIBLE.md Section 10.
Reference FRONTEND_BIBLE.md for all frontend decisions.
```

---

*"In a world of plastic bricks and big imaginations, every builder deserves to see their story come to life."*
