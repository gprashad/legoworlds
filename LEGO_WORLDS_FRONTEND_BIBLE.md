# LEGO WORLDS — Frontend Bible

> **Version:** 2.0 | **Companion to:** BIBLE.md (Pipeline Bible)
> **Architecture:** Fully cloud-hosted
> **Frontend:** React + TypeScript + Vite → Netlify
> **Backend:** FastAPI (Python) → Railway
> **Auth + DB + Storage:** Supabase

---

## 1. Product Experience

### The Full Loop

1. **Capture** — Kid takes photos/videos of Lego scene on phone or tablet
2. **Send** — Texts or emails them to a dedicated address (auto-ingests) or uploads directly in web app
3. **Organize** — Opens web app, sees a new "Scene" with his media
4. **Narrate** — Records voiceover directly in the browser, adds written backstory
5. **Launch** — Hits "Make My Movie" — pipeline generates a screenplay
6. **Green Light** — Reviews screenplay, edits if he wants, approves it
7. **Watch** — Gets a polished video: real photos slideshow with voiceover intro → fade to AI-animated movie
8. **Share** — One-click upload to TikTok, YouTube, Instagram

### Who Uses This

- **Primary:** Jackson (kid, ~10-12 age range). Must be dead simple, fun, zero friction.
- **Secondary:** Gaurav (parent/admin). Sees all projects, manages settings, monitors API usage.
- **Future:** Other kids/families. But v1 is single-family.

---

## 2. Information Architecture

```
/                           → Landing / redirect to /scenes
/login                      → Google SSO login
/scenes                     → Scene library (all projects)
/scenes/:id                 → Single scene workspace
/scenes/:id/screenplay      → Screenplay review & approval
/scenes/:id/movie           → Final movie player + share
/settings                   → Account, preferences (admin only)
```

### Scene States

```
[DRAFT] → [READY] → [ANALYZING] → [SCREENPLAY_REVIEW] → [APPROVED] → [PRODUCING] → [ASSEMBLING] → [COMPLETE]
                                                                                                        ↓
                                                                                                    [PUBLISHED]
```

| State | What the kid sees |
|-------|------------------|
| DRAFT | Scene folder with uploaded media. Can add more photos, record voiceover, write backstory. "Make My Movie" grayed out until requirements met (2+ photos, backstory). |
| READY | All inputs provided. "Make My Movie" button active and glowing. |
| ANALYZING | Loading animation. "Reading your scene..." with Lego-themed progress indicator. |
| SCREENPLAY_REVIEW | Screenplay as visual storyboard cards. Read through, suggest edits, or hit "Green Light!" |
| APPROVED | "Lights, camera, action!" — production running. Progress bar by scene. |
| PRODUCING | Scene-by-scene progress. "Filming Scene 2 of 4..." with preview thumbnails as clips complete. |
| ASSEMBLING | "Editing your movie..." |
| COMPLETE | Movie player. Watch, rewatch, download. Share buttons visible. |
| PUBLISHED | Shared to at least one platform. Badge on scene card. |

---

## 3. Intake: Getting Media Into the Platform

### Three Intake Channels

#### Channel 1: Direct Upload (Web) — v1 Primary

Standard file upload in the scene workspace. Drag-and-drop or file picker. Photos upload directly to Supabase Storage via the frontend Supabase client (no backend needed for upload).

#### Channel 2: Dedicated Email Address — v1 Secondary

```
scenes@legoworlds.app (or a Gmail address for v1)
```

- Kid emails photos/videos from phone
- Subject line → scene title
- Body text → initial backstory
- Backend polls inbox (Gmail API), extracts attachments
- Uploads to Supabase Storage, creates scene in DB
- Sends confirmation reply with link to web app

#### Channel 3: Dedicated Phone Number (SMS/MMS) — v2

```
Text photos to: (555) 123-LEGO
```

- Twilio webhook receives MMS
- Creates scene or appends to recent draft
- Replies with web app link

**v1 Priority:** Direct upload first, email intake second.

---

## 4. Page-by-Page Design Specs

### 4.1 Login Page (`/login`)

**Minimal. One button.**

```
┌─────────────────────────────────────┐
│                                     │
│          🧱 LEGO WORLDS            │
│     Where your builds come alive    │
│                                     │
│     ┌─────────────────────────┐     │
│     │  Continue with Google   │     │
│     └─────────────────────────┘     │
│                                     │
└─────────────────────────────────────┘
```

- Google SSO via Supabase Auth
- Whitelist of allowed Google accounts (family only for v1)
- After login, redirect to `/scenes`
- Background: subtle Lego brick animation
- Logo: blocky, playful typography

### 4.2 Scene Library (`/scenes`)

**The kid's studio — all scenes/projects in one place.**

```
┌──────────────────────────────────────────────────────┐
│  🧱 LEGO WORLDS                    Jackson ▾   ⚙️   │
├──────────────────────────────────────────────────────┤
│                                                      │
│  My Scenes                          [+ New Scene]    │
│                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ 📸       │  │ 🎬       │  │ 📸       │           │
│  │ cover    │  │ cover    │  │ cover    │           │
│  │ photo    │  │ photo    │  │ photo    │           │
│  │──────────│  │──────────│  │──────────│           │
│  │The Corrupt│  │Space     │  │Bank Heist│           │
│  │Bulldozer │  │Station   │  │          │           │
│  │🟡 Draft  │  │🟢 Complete│  │🔵 Review │           │
│  │ 4 photos │  │ 1:12 movie│  │ 3 photos │           │
│  └──────────┘  └──────────┘  └──────────┘           │
│                                                      │
└──────────────────────────────────────────────────────┘
```

- Responsive grid (3 col desktop, 2 tablet, 1 mobile)
- Each card: cover photo, title, status badge, media count, date
- Complete scenes show play button overlay
- "+" button creates blank scene → navigate to workspace
- Sorted by last modified
- Status badges color-coded (Draft=yellow, Review=blue, Producing=orange pulse, Complete=green, Published=green+icon)

### 4.3 Scene Workspace (`/scenes/:id`)

**Main working area. Kid spends most time here.**

```
┌──────────────────────────────────────────────────────────────┐
│  ← My Scenes    The Corrupt Bulldozer              ⚙️  🗑️   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─── MEDIA ──────────────────────────────────────────────┐  │
│  │  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────────┐              │  │
│  │  │ 📸 │ │ 📸 │ │ 📸 │ │ 📸 │ │+ Add   │              │  │
│  │  └────┘ └────┘ └────┘ └────┘ └────────┘              │  │
│  │                                                        │  │
│  │  ┌──────────────────────────────────┐                  │  │
│  │  │ 🎤 Record Voiceover             │  ⏱️ 0:45        │  │
│  │  │ ▶️ ████████████░░░░░░░░          │  [Re-record]    │  │
│  │  └──────────────────────────────────┘                  │  │
│  │                                                        │  │
│  │  📧 Email photos to: scenes+abc123@legoworlds.app     │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─── BACKSTORY ──────────────────────────────────────────┐  │
│  │  Tell the story of your scene...                       │  │
│  │                                                        │  │
│  │  The bulldozer driver is corrupt — he's working with   │  │
│  │  the mayor to tear down the shop...                    │  │
│  │                                                        │  │
│  │  💡 Tip: Describe who the characters are, what's       │  │
│  │  happening, and what's about to happen next!           │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─── MOVIE SETTINGS ────────────────────────────────────┐  │
│  │  Director credit: [Jackson          ]                  │  │
│  │  Movie style:     [🎬 Cinematic  ▾]                   │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │            🎬  MAKE MY MOVIE                           │  │
│  │               ✅ 4 photos  ✅ backstory                │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

**Media Section:**
- Thumbnail grid, click for lightbox
- Drag to reorder (first photo = cover)
- "+" card: file picker + drag-and-drop zone
- Uploads go directly to Supabase Storage via frontend client
- Video thumbnails show duration + play icon
- Delete (x) on hover
- **Voiceover recorder:** MediaRecorder API, big red record button, waveform, playback, re-record. Audio uploads to Supabase Storage.

**Backstory Section:**
- Plain text area, auto-save (debounced 500ms to Supabase DB)
- Character/word count indicator
- Dismissable tip card

**Movie Settings:**
- Director credit name (pre-filled, editable per scene)
- Style selector (v1: just "Cinematic")

**Make My Movie Button:**
- Large, prominent
- Disabled until: 2+ photos AND backstory 20+ chars
- Checklist shows what's ready / missing
- Click → confirmation modal → POST to backend → navigate to screenplay review

### 4.4 Screenplay Review (`/scenes/:id/screenplay`)

```
┌──────────────────────────────────────────────────────────────┐
│  ← The Corrupt Bulldozer              SCREENPLAY REVIEW     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  🎬 Your screenplay is ready! Review and green light it.    │
│                                                              │
│  ┌─── NARRATOR INTRO ────────────────────────────────────┐  │
│  │  🎙️ "In a city where deals are made behind closed     │  │
│  │  doors, one bulldozer driver is about to learn..."     │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─── SCENE 1: "The Blockade" ── 20 sec ─────────────────┐  │
│  │  ┌─────────┐  📷 Wide shot, slow push-in               │  │
│  │  │reference│  The yellow bulldozer sits blocking...     │  │
│  │  │ photo   │                                           │  │
│  │  └─────────┘  💬 Crowd Leader: "They can't do this!"   │  │
│  │               💬 Bulldozer Driver: "I got my orders."   │  │
│  │               🔊 engine idling  🎵 tense               │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  [... more scene cards ...]                                  │
│                                                              │
│  ┌─── FEEDBACK ──────────────────────────────────────────┐  │
│  │  Want changes? [                                     ] │  │
│  │                                    [Revise Script]     │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │          🟢  GREEN LIGHT — START PRODUCTION!           │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  Estimated production time: ~12 minutes                      │
└──────────────────────────────────────────────────────────────┘
```

- Storyboard cards per scene: reference photo, camera direction, action, dialogue, SFX, music
- Narrator intro/outro as quote blocks
- Reference photos loaded from Supabase Storage (signed URLs)
- Feedback textarea → "Revise Script" re-runs screenplay stage with feedback
- "Green Light" → POST to backend → transition to progress view
- Estimated time shown

### 4.5 Production Progress

```
┌──────────────────────────────────────────────────────────────┐
│  🎬 Filming Scene 2 of 4...                                 │
│  ████████████████░░░░░░░░░░░░  58%                           │
│                                                              │
│  ✅ Scene 1: "The Blockade"         — done                   │
│  🔄 Scene 2: "The Sneak"           — generating video        │
│  ⏳ Scene 3: "The Discovery"        — waiting                │
│  ⏳ Scene 4: "The Showdown"         — waiting                │
│  ⏳ Voice acting                     — waiting                │
│  ⏳ Final assembly                   — waiting                │
│                                                              │
│  ⏱️ ~8 minutes remaining                                     │
│  💡 Go build something new while you wait!                   │
└──────────────────────────────────────────────────────────────┘
```

- Poll GET /api/scenes/:id/status every 5 seconds (v1) or Supabase Realtime (v2)
- Scene-by-scene status icons
- Browser notification on completion (Notification API)
- Auto-navigate to movie player on completion

### 4.6 Movie Player & Share (`/scenes/:id/movie`)

```
┌──────────────────────────────────────────────────────────────┐
│  ← The Corrupt Bulldozer                    PREMIERE 🎬     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │              🎬 VIDEO PLAYER                           │  │
│  │              (Supabase Storage signed URL)             │  │
│  │  ──────────────●──────────────── 0:00 / 1:24           │  │
│  │  🔊 ████░░  |  ⬜ Fullscreen  |  ⬇️ Download          │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─── SHARE ─────────────────────────────────────────────┐  │
│  │  🎉 Your movie is ready! Share it with the world.     │  │
│  │                                                        │  │
│  │  [TikTok] [YouTube] [Instagram] [Copy Link]            │  │
│  │                                                        │  │
│  │  Caption: [Auto-generated, editable                  ] │  │
│  │  Hashtags: #LegoWorlds #LegoAnimation #BrickFilm       │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─── BEHIND THE SCENES ─────────────────────────────────┐  │
│  │  ┌────┐ ┌────┐ ┌────┐ ┌────┐  The original build      │  │
│  │  │ 📸 │ │ 📸 │ │ 📸 │ │ 📸 │  📜 View Screenplay     │  │
│  │  └────┘ └────┘ └────┘ └────┘                          │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  [🔄 Re-make with different style]  [🎬 Make a sequel]      │
└──────────────────────────────────────────────────────────────┘
```

**The Final Video Structure:**

```
Timeline:
0:00 - 0:05   Title card: "LEGO WORLDS presents..."
0:05 - 0:08   Title card: "A film by Jackson"
0:08 - 0:12   Title card: Movie title
0:12 - 0:30   BEHIND THE SCENES — real photo slideshow + kid's voiceover
0:30 - 0:33   Transition: photos dissolve into animated movie
0:33 - 1:20   THE MOVIE — AI-animated scenes with narration, dialogue, SFX, music
1:20 - 1:27   Credits: "Directed by Jackson" / "Built by Jackson" / "Produced by Lego Worlds"
```

**Share Features:**
- Download as MP4 (direct from Supabase Storage)
- TikTok/Instagram: auto-format to 9:16 vertical
- YouTube: 16:9 with title, description, tags
- Copy Link: shareable Supabase Storage public URL
- Auto-generated caption (AI-written, editable)
- Pre-populated hashtags
- Social upload via Ayrshare API (POST to backend → Ayrshare)

---

## 5. The Voiceover — "Behind the Scenes" Intro

**Recording in Browser:**
```
- MediaRecorder API (audio/webm or audio/wav)
- Big red pulsing record button + live waveform
- Prompt: "Talk about what you built and what's happening in your scene"
- Max duration: 60 seconds
- Playback review before saving
- Uploads to Supabase Storage: scenes/{id}/input/voiceover.webm
```

**If No Voiceover:** AI narrator reads backstory summary over photos instead.

---

## 6. Tech Stack

### Frontend

```
Framework:       React 18+ with TypeScript
Build:           Vite
Styling:         Tailwind CSS
Routing:         React Router v6
State:           Zustand
Auth:            Supabase Auth (Google SSO)
File Upload:     Supabase Storage JS client (direct upload from browser)
Audio Recording: MediaRecorder API (native browser)
Video Player:    Native <video> or react-player
Real-time:       Polling (v1) → Supabase Realtime (v2)
Notifications:   Browser Notification API
Hosting:         Netlify (auto-deploy from GitHub)
```

### Database (Supabase)

```sql
-- Profiles (extends Supabase Auth users)
create table profiles (
  id uuid references auth.users primary key,
  display_name text not null,
  role text default 'creator',  -- 'creator' or 'admin'
  phone_number text,
  created_at timestamptz default now()
);

-- Scenes
create table scenes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references profiles(id) not null,
  title text not null default 'Untitled Scene',
  backstory text,
  status text not null default 'draft',
  director_name text default 'Jackson',
  movie_style text default 'cinematic',
  music_mood text default 'auto',
  scene_bible jsonb,
  screenplay jsonb,
  screenplay_feedback text,
  screenplay_version int default 0,
  voiceover_url text,
  final_video_url text,
  final_video_duration_seconds int,
  published_platforms jsonb default '[]',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Scene media (photos, videos)
create table scene_media (
  id uuid primary key default gen_random_uuid(),
  scene_id uuid references scenes(id) on delete cascade not null,
  file_url text not null,
  file_type text not null,  -- 'photo' or 'video'
  file_name text,
  file_size_bytes int,
  sort_order int default 0,
  source text default 'upload',  -- 'upload', 'email', 'sms'
  created_at timestamptz default now()
);

-- Jobs (pipeline tracking)
create table jobs (
  id uuid primary key default gen_random_uuid(),
  scene_id uuid references scenes(id) not null,
  status text not null default 'pending',
  current_stage text,
  progress_pct int default 0,
  stages_completed jsonb default '[]',
  error text,
  started_at timestamptz,
  completed_at timestamptz,
  created_at timestamptz default now()
);

-- RLS
alter table scenes enable row level security;
alter table scene_media enable row level security;
alter table jobs enable row level security;

create policy "Users see own scenes" on scenes
  for all using (auth.uid() = user_id);
create policy "Users see own media" on scene_media
  for all using (scene_id in (select id from scenes where user_id = auth.uid()));
create policy "Users see own jobs" on jobs
  for all using (scene_id in (select id from scenes where user_id = auth.uid()));
```

---

## 7. API Endpoints (FastAPI Backend on Railway)

```
Auth: All endpoints require Supabase JWT in Authorization header.

Scenes:
  GET    /api/scenes                    → list user's scenes
  POST   /api/scenes                    → create new scene
  GET    /api/scenes/:id                → get scene details
  PATCH  /api/scenes/:id                → update (title, backstory, settings)
  DELETE /api/scenes/:id                → delete scene + media

Media:
  POST   /api/scenes/:id/media          → register uploaded media (after frontend uploads to Supabase Storage)
  DELETE /api/scenes/:id/media/:mediaId → remove media
  PATCH  /api/scenes/:id/media/reorder  → update sort order

Voiceover:
  POST   /api/scenes/:id/voiceover      → register voiceover (after frontend uploads to Storage)
  DELETE /api/scenes/:id/voiceover      → remove voiceover

Pipeline:
  POST   /api/scenes/:id/analyze        → trigger analysis → screenplay generation
  POST   /api/scenes/:id/revise         → revise screenplay with feedback
  POST   /api/scenes/:id/greenlight     → approve screenplay, trigger production
  GET    /api/scenes/:id/status         → current pipeline status + progress

Sharing:
  POST   /api/scenes/:id/share          → upload to socials via Ayrshare
  GET    /api/scenes/:id/share-link     → get shareable URL

Intake Webhooks (no JWT, validated by secret):
  POST   /api/intake/email              → Gmail webhook
  POST   /api/intake/sms                → Twilio webhook
```

**Important:** File uploads (photos, voiceover) go directly from the frontend to Supabase Storage using the Supabase JS client. The backend just registers the metadata in the DB. This avoids routing large files through the backend server.

---

## 8. Frontend Project Structure

```
~/legoworlds/frontend/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── tailwind.config.js
├── netlify.toml                  ← Build config for Netlify
├── .env
├── .env.example
│
├── public/
│   ├── favicon.ico
│   └── logo.svg
│
├── src/
│   ├── main.tsx
│   ├── App.tsx                   ← Router, auth provider
│   │
│   ├── config/
│   │   ├── supabase.ts           ← Supabase client init
│   │   └── api.ts                ← Fetch wrapper with auth headers for backend API
│   │
│   ├── hooks/
│   │   ├── useAuth.ts            ← Google SSO login/logout, session
│   │   ├── useScenes.ts          ← CRUD for scenes
│   │   ├── useMediaUpload.ts     ← Upload to Supabase Storage + register with backend
│   │   ├── useVoiceover.ts       ← MediaRecorder wrapper
│   │   ├── usePipeline.ts        ← Trigger pipeline, poll status
│   │   └── useShare.ts           ← Social sharing
│   │
│   ├── stores/
│   │   └── appStore.ts           ← Zustand (current scene, user, UI state)
│   │
│   ├── pages/
│   │   ├── LoginPage.tsx
│   │   ├── ScenesPage.tsx
│   │   ├── SceneWorkspace.tsx
│   │   ├── ScreenplayReview.tsx
│   │   └── MoviePlayer.tsx
│   │
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Header.tsx
│   │   │   ├── PageContainer.tsx
│   │   │   └── ProtectedRoute.tsx
│   │   │
│   │   ├── scenes/
│   │   │   ├── SceneCard.tsx
│   │   │   ├── StatusBadge.tsx
│   │   │   └── NewSceneButton.tsx
│   │   │
│   │   ├── workspace/
│   │   │   ├── MediaGrid.tsx
│   │   │   ├── MediaUploader.tsx      ← Drag-drop, uploads to Supabase Storage
│   │   │   ├── VoiceoverRecorder.tsx
│   │   │   ├── BackstoryEditor.tsx
│   │   │   ├── MovieSettings.tsx
│   │   │   └── MakeMovieButton.tsx
│   │   │
│   │   ├── screenplay/
│   │   │   ├── StoryboardCard.tsx
│   │   │   ├── NarratorCard.tsx
│   │   │   ├── DialogueLine.tsx
│   │   │   ├── FeedbackForm.tsx
│   │   │   └── GreenLightButton.tsx
│   │   │
│   │   ├── production/
│   │   │   ├── ProgressTracker.tsx
│   │   │   └── ProgressBar.tsx
│   │   │
│   │   ├── movie/
│   │   │   ├── VideoPlayer.tsx
│   │   │   ├── SharePanel.tsx
│   │   │   ├── BehindTheScenes.tsx
│   │   │   └── DownloadButton.tsx
│   │   │
│   │   └── ui/
│   │       ├── Button.tsx
│   │       ├── Modal.tsx
│   │       ├── Lightbox.tsx
│   │       ├── LoadingSpinner.tsx
│   │       └── Waveform.tsx
│   │
│   ├── types/
│   │   ├── scene.ts
│   │   ├── screenplay.ts
│   │   └── api.ts
│   │
│   ├── utils/
│   │   ├── audio.ts
│   │   ├── format.ts
│   │   └── validation.ts
│   │
│   └── styles/
│       └── globals.css
```

---

## 9. Design System

### Visual Identity

**Tone:** Playful but not childish. Bold, colorful, confident — like Lego's own branding. A kid should feel like a real film director, not like they're using a "kids app."

**Color Palette:**
```css
:root {
  /* Primary — Lego Red */
  --color-primary: #E3000B;
  --color-primary-hover: #C8000A;

  /* Accent — Lego Yellow */
  --color-accent: #FFD500;
  --color-accent-hover: #E6C000;

  /* Neutrals — Warm grays (baseplate feel) */
  --color-bg: #1A1A1A;
  --color-surface: #2A2A2A;
  --color-surface-elevated: #3A3A3A;
  --color-text: #F5F5F5;
  --color-text-secondary: #A0A0A0;
  --color-border: #444444;

  /* Status */
  --color-draft: #FFD500;
  --color-review: #4A90D9;
  --color-producing: #FF8C00;
  --color-complete: #4CAF50;
  --color-error: #E3000B;

  /* Green light */
  --color-greenlight: #00C853;
  --color-greenlight-hover: #00A844;
}
```

**Typography:**
```css
/* Display / Headers */
font-family: 'Fredoka', 'Nunito', sans-serif;

/* Body */
font-family: 'DM Sans', 'Outfit', sans-serif;

/* Screenplay text */
font-family: 'JetBrains Mono', 'Fira Code', monospace;
```

**Design Elements:**
- Rounded corners (8-12px) — Lego stud feel
- Dark theme default (cinema / editing suite vibe)
- Subtle shadows, no harsh borders
- Micro-animations on interactions
- Lego stud pattern as subtle background texture (CSS repeating)
- Cards with slight "plastic" feel — subtle gradient + shadow

### Responsive Breakpoints

```
Mobile:   < 640px   — single column, simplified controls
Tablet:   640-1024  — 2-column grid, full workspace
Desktop:  > 1024    — 3-column grid, spacious workspace
```

---

## 10. Data Flow: Upload → Storage → Backend

**Critical architecture decision:** Photos upload directly from the frontend to Supabase Storage. The backend never handles file bytes for uploads.

```
Upload Flow:
  1. Kid drops photos in MediaUploader component
  2. Frontend Supabase client uploads each file to:
     Supabase Storage → legoworlds bucket → scenes/{scene_id}/input/{filename}
  3. On upload success, frontend calls backend:
     POST /api/scenes/:id/media { file_url, file_type, file_name, file_size_bytes }
  4. Backend creates scene_media record in DB

Pipeline Flow:
  1. Frontend calls POST /api/scenes/:id/analyze
  2. Backend downloads photos from Supabase Storage (using service key)
  3. Sends to Claude Vision API
  4. Stores scene_bible JSON in scenes table
  5. Generates screenplay, stores in scenes table
  6. Updates scene status to 'screenplay_review'
  7. Frontend polls status, sees screenplay, displays storyboard

Production Flow:
  1. Frontend calls POST /api/scenes/:id/greenlight
  2. Backend runs production in background (FastAPI BackgroundTasks)
  3. For each scene: downloads reference photo → Kling API → uploads clip to Storage
  4. Voice gen: ElevenLabs → uploads audio to Storage
  5. Assembly: downloads all assets to /tmp → FFmpeg → uploads final.mp4 to Storage
  6. Updates final_video_url in DB, status to 'complete'
  7. Frontend polls, sees completion, shows movie player

Video Playback:
  1. Frontend reads final_video_url from scenes table
  2. Gets signed URL from Supabase Storage
  3. Passes to <video> element src
```

---

## 11. Build Phases (Frontend)

### Phase 1: Core Web App (Week 1, parallel with backend)

1. **Day 1:** Vite + React + TS + Tailwind. Supabase project + Auth (Google SSO). Protected routes. Netlify deploy.
2. **Day 2:** Supabase schema (run SQL migration). API client with auth headers. Scene CRUD hooks.
3. **Day 3:** Scene library page (grid, cards, status badges, new scene). Scene workspace layout.
4. **Day 4:** Media uploader (drag-drop → Supabase Storage → register with backend). Thumbnails, reorder, delete. Lightbox.
5. **Day 5:** Backstory editor (auto-save). Movie settings. Make My Movie button with checklist.

### Phase 2: Pipeline Integration (Week 2)

6. **Day 6:** Pipeline trigger. Status polling hook. Progress tracker component.
7. **Day 7:** Screenplay review page (storyboard cards, narrator cards, dialogue). Feedback/revision.
8. **Day 8:** Green light flow. Production progress view (scene-by-scene).
9. **Day 9:** Movie player page. Video from Supabase Storage signed URL. Download button.
10. **Day 10:** End-to-end integration test with real backend.

### Phase 3: Polish & Share (Week 3)

11. **Day 11:** Voiceover recorder (MediaRecorder, waveform, upload to Storage).
12. **Day 12:** Share panel (Ayrshare via backend). Caption editor. Platform buttons.
13. **Day 13:** Email intake system (backend: Gmail API polling).
14. **Day 14:** Design polish. Animations. Loading/error/empty states. Mobile responsiveness.

---

## 12. Deployment

### Netlify Config

```toml
# netlify.toml
[build]
  base = "frontend"
  command = "npm run build"
  publish = "dist"

[build.environment]
  NODE_VERSION = "20"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200
```

### Environment Variables (Netlify Dashboard)

```
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
VITE_API_URL=https://legoworlds-api.up.railway.app
```

---

## 13. Security (v1)

- Google SSO only — no passwords
- Supabase RLS on all tables — users see only their own data
- Allowlist of Google accounts in Supabase Auth settings
- Backend validates Supabase JWT on every request
- File uploads: validate types (images/video only), size limits (50MB/file)
- Frontend uploads directly to Supabase Storage (RLS enforced)
- Backend uses service role key (never exposed to frontend)
- API keys in Railway env vars (never in code)

---

## 14. Claude Code Kickoff Prompt (Frontend)

```
Read BIBLE.md and FRONTEND_BIBLE.md in this directory. 

Scaffold the frontend in ~/legoworlds/frontend/:
- React + TypeScript + Vite
- Tailwind CSS with design system from FRONTEND_BIBLE.md Section 9
- Supabase client setup (Google SSO auth)
- React Router with routes from Section 2
- Zustand store
- netlify.toml for deployment

Build Phase 1 from Section 11:
- Login page (Google SSO)
- Scene library page (grid of cards)
- Scene workspace (media upload to Supabase Storage, backstory editor, Make My Movie button)

Follow component structure from Section 8.
File uploads go directly to Supabase Storage from the frontend.
Backend API calls use the wrapper from src/config/api.ts with Supabase JWT.
```

---

*"Every great movie starts with someone saying: what if?"*
