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

### Phase 1: Get the Backend Live (Railway Deploy) ✅
- [x] Authenticate Railway CLI, create project, deploy backend
- [x] Update `VITE_API_URL` in Netlify env vars to Railway URL
- [x] End-to-end test: create scene → upload photo → save backstory
- [x] Backend: https://legoworlds-api-production.up.railway.app

### Phase 2: Pipeline — Scene Analysis + Screenplay ✅
- [x] `POST /api/scenes/:id/analyze` endpoint (triggers BackgroundTask)
- [x] `src/stages/scene_analysis.py` — download photos from Storage → Claude Vision → save scene_bible to DB
- [x] `src/stages/screenplay.py` — read scene_bible + backstory → Claude → structured screenplay JSON → save to DB
- [x] `src/pipeline.py` — orchestrator that chains stages, updates scene status + job progress
- [x] `GET /api/scenes/:id/status` endpoint (poll job progress)
- [x] `POST /api/scenes/:id/revise` endpoint (re-run screenplay with feedback)
- [x] `POST /api/scenes/:id/greenlight` endpoint (approve → trigger production)

### Phase 3: Frontend — Screenplay Review + Progress ✅
- [x] `ScreenplayReview.tsx` page — storyboard cards, narrator cards, dialogue lines, reference photos
- [x] `FeedbackForm` + `GreenLightButton` components
- [x] `usePipeline` hook — trigger analyze, poll status, trigger greenlight
- [x] `ProgressTracker.tsx` — scene-by-scene progress with status icons
- [x] Wire Make My Movie button → trigger analyze → navigate to screenplay review

### Phase 4: Production Pipeline ✅
- [x] `src/stages/production.py` — Kie.ai VEO3 (image-to-video per scene), upload clips to Storage
- [x] `src/stages/production.py` — ElevenLabs (voice per character + narrator), upload audio to Storage
- [x] `src/stages/assembly.py` — FFmpeg: title cards + photo slideshow + scene videos + dialogue + credits → final.mp4
- [x] Upload final video to Storage, update `final_video_url` in DB
- [x] Greenlight triggers production as background task with progress polling

### Phase 5: Frontend — Movie Player + Delivery ✅
- [x] `MoviePlayer.tsx` page — video player with autoplay, download button
- [x] `BehindTheScenes` component — original photos, link to screenplay
- [x] `SharePanel` — copy link, download MP4 (social posting deferred)
- [x] Auto-navigate from screenplay review → movie player on production complete
- [x] SceneCard links complete scenes to movie player, workspace shows "Watch" banner
- [ ] `POST /api/scenes/:id/share` endpoint (social posting via Ayrshare — deferred)
- [ ] Browser notification on completion (deferred)

### Phase 6: Polish ✅
- [x] Voiceover recorder (MediaRecorder API, live waveform, 60s max, upload to Storage)
- [x] Scene delete confirmation modal
- [x] Mobile responsiveness pass (all pages)
- [x] Reusable Modal component
- [ ] Email intake (Gmail API polling — deferred)
- [ ] Browser notification on completion (deferred)
- [ ] Social posting via Ayrshare (deferred)
