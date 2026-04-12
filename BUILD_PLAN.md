# LEGO WORLDS — Build Plan

> **Created:** 2026-04-11 | **Status:** In Progress

---

## What's Built

### Infrastructure
- [x] GitHub repo — `gprashad/legoworlds`, auto-deploys to Netlify on push
- [x] Netlify — https://legoworlds.netlify.app, env vars set
- [x] Supabase — project live, migration applied (profiles, scenes, scene_media, jobs + RLS + triggers), `legoworlds` storage bucket created
- [ ] Railway — CLI installed, not yet authenticated/deployed

### Backend (~390 lines)
- [x] FastAPI server with CORS
- [x] JWT auth middleware (verifies Supabase tokens)
- [x] Supabase service-key client
- [x] Pydantic models for all request/response types
- [x] Scene CRUD — GET/POST/PATCH/DELETE `/api/scenes`
- [x] Media registration — POST/DELETE/PATCH reorder `/api/scenes/:id/media`
- [x] Dockerfile (Python 3.11 + FFmpeg)
- [x] Prompt templates for scene analysis + screenplay

### Frontend (~930 lines)
- [x] React/Vite/Tailwind with design system (Lego Red/Yellow dark theme, Fredoka + DM Sans)
- [x] Supabase client + API fetch wrapper with JWT headers
- [x] Google SSO auth hook + ProtectedRoute
- [x] Login page — Google SSO button
- [x] Scene library — responsive grid, status badges, new scene button
- [x] Scene workspace — media upload (drag-drop → Supabase Storage → register), backstory editor (500ms auto-save), movie settings, Make My Movie button with checklist

### Supabase
- [x] Schema: profiles, scenes, scene_media, jobs tables
- [x] RLS policies on all tables + storage
- [x] Auto-create profile trigger on signup
- [x] Auto-update updated_at trigger on scenes
- [x] `legoworlds` storage bucket
- [ ] Google auth provider (in progress)

---

## Build Phases

### Phase 1: Get the Backend Live (Railway Deploy)
- [ ] Authenticate Railway CLI, create project, deploy backend
- [ ] Update `VITE_API_URL` in Netlify env vars to Railway URL
- [ ] End-to-end test: login → create scene → upload photo → save backstory

### Phase 2: Pipeline — Scene Analysis + Screenplay
- [ ] `POST /api/scenes/:id/analyze` endpoint (triggers BackgroundTask)
- [ ] `src/stages/scene_analysis.py` — download photos from Storage → Claude Vision → save scene_bible to DB
- [ ] `src/stages/screenplay.py` — read scene_bible + backstory → Claude → structured screenplay JSON → save to DB
- [ ] `src/pipeline.py` — orchestrator that chains stages, updates scene status + job progress
- [ ] `GET /api/scenes/:id/status` endpoint (poll job progress)
- [ ] `POST /api/scenes/:id/revise` endpoint (re-run screenplay with feedback)
- [ ] `POST /api/scenes/:id/greenlight` endpoint (approve → trigger production)

### Phase 3: Frontend — Screenplay Review + Progress
- [ ] `ScreenplayReview.tsx` page — storyboard cards, narrator cards, dialogue lines, reference photos
- [ ] `FeedbackForm` + `GreenLightButton` components
- [ ] `usePipeline` hook — trigger analyze, poll status, trigger greenlight
- [ ] `ProgressTracker.tsx` — scene-by-scene progress with status icons
- [ ] Wire Make My Movie button → trigger analyze → navigate to screenplay review

### Phase 4: Production Pipeline
- [ ] `src/stages/production.py` — Kling API (image-to-video per scene), upload clips to Storage
- [ ] `src/stages/production.py` — ElevenLabs (voice per character + narrator), upload audio to Storage
- [ ] `src/stages/assembly.py` — FFmpeg: stitch clips + audio + title cards + credits → final.mp4
- [ ] Upload final video to Storage, update `final_video_url` in DB

### Phase 5: Frontend — Movie Player + Delivery
- [ ] `MoviePlayer.tsx` page — video player with Supabase Storage signed URL, download button
- [ ] `BehindTheScenes` component — original photos, link to screenplay
- [ ] `SharePanel` — TikTok/YouTube/Instagram buttons (Ayrshare via backend)
- [ ] `POST /api/scenes/:id/share` endpoint
- [ ] Browser notification on completion

### Phase 6: Polish
- [ ] Voiceover recorder (MediaRecorder API)
- [ ] Scene delete confirmation modal
- [ ] Mobile responsiveness pass
- [ ] Loading/error/empty state polish
- [ ] Email intake (Gmail API polling)
