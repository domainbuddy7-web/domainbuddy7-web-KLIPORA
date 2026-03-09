# Deep Analysis: AutoShorts/Klipora-Style Faceless Video UI → KLIPORA Implementation

This document maps the **alternative process** (full faceless video generator spec: Landing, Dashboard, Series edit, all settings, unlocked/locked) onto **our current KLIPORA project** and outlines how to implement it.

---

## 1. Spec vs current KLIPORA (gap analysis)

### 1.1 What the spec describes

| Layer | Spec | Our project today |
|-------|------|--------------------|
| **Entry** | Web: Landing → Dashboard → Series edit | Telegram bot + Mission Control API (no web UI) |
| **Unit of work** | **Series** (topic/prompt + one “upcoming” video + settings + past videos) | **Job** (single video: topic, genre, script, status; no “series” grouping) |
| **Script** | “Generate a completely new script” → fill script field; user edits; “Update Video” | WF-GEN (Groq) → script in job; user can’t edit before video runs |
| **Settings** | Rich per-series: Publish (visibility, Comment/Duet/Stitch), Content (length 15/30/60/90s, type), Visual (style, ratio, credits), Caption (style, font, position), Audio (voice, speed, music, volume) | Job + meta: genre, duration, aspect_ratio, vstyle, nstyle; no visibility, no content type, no caption/overlay, no voice speed/music volume |
| **Preview / edit** | Upcoming video card: title, caption, script, preview placeholder; edit then “Update Video” | No web preview; Telegram review message after clips are ready (Approve / Regenerate / Discard) |
| **Publish** | “Publish” or “Download” from web | Approve in Telegram → FFmpeg render → video to Telegram |
| **History** | “Past Videos” per series | No “past videos” list in UI; we have queues and job statuses |
| **Feature gating** | UNLOCKED vs Locked (plans); features.js + isLocked() | No plan/feature flags in app |

### 1.2 Data mapping: Spec “Series” ↔ our “Job” + extensions

**Spec series model (conceptual):**

- id, title, caption, script, thumbnail, createdAt  
- **Publish:** visibility, allowComments, allowDuet, allowStitch  
- **Content:** videoLength (15|30|60|90), contentType (story|facts|hook|custom)  
- **Visual:** aspectRatio (9:16|1:1|4:5), visualStyle, imageCredits, motionCredits  
- **Caption:** captionStyle, captionFont, overlayPosition  
- **Audio:** voice, voiceSpeed, music, musicVolume  

**Our job + meta today:**

- id, topic (≈ title), genre, script, status, created_at, updated_at  
- meta: visual_style (≈ vstyle), narration_style (≈ nstyle), duration, aspect_ratio  
- We already pass: genre, duration, aspect_ratio, vstyle, nstyle, music_url  

**Gaps to add (to support full spec):**

- title (display), caption (TikTok/YouTube text), thumbnail  
- visibility, allowComments, allowDuet, allowStitch  
- videoLength (we have duration; map 15/30/60/90), contentType  
- imageCredits, motionCredits  
- captionStyle, captionFont, overlayPosition  
- voice (we have nstyle), voiceSpeed, music (we have music_url), musicVolume  

So we can implement the spec by **extending the job (and optional “series”) model** and **adding a web app** that reads/writes these fields and triggers the existing pipeline.

---

## 2. Architecture options

### Option A: Web app only (thin UI over existing API)

- Add a **React app** (Landing + Dashboard + Series edit) that talks to **Mission Control API**.
- **No “series” in backend:** “Series” in the UI = one “upcoming” job; “Create new series” = create job + open edit; “Save” = update job in Redis; “Generate script” = `POST /commands/generate-video` (or a dedicated “generate script only” endpoint); “Update Video” = re-submit job to pipeline with current form (script + settings).
- **Pros:** Minimal backend change; reuse existing WF-GEN, WF-VIDEO, WF-ASSEMBLE, Telegram review.  
- **Cons:** No real “series” entity; “Past Videos” would need new API (list jobs by some tag or user).

### Option B: Introduce “series” in backend (recommended)

- **Series** = persistent entity (Redis or DB): id, title, caption, script, thumbnail, createdAt, **all spec settings** (publish, content, visual, caption, audio), and optional list of job_ids (past videos).
- **Upcoming video** = “next” job for that series (created when user clicks “Generate script” or “Update Video”); job gets series_id + copy of series settings.
- **Backend:**  
  - `GET/POST /series` (list, create)  
  - `GET/PUT/DELETE /series/:id` (get, update, delete)  
  - `POST /series/:id/generate-script` (create/update job, trigger WF-GEN with series settings)  
  - `POST /series/:id/update-video` (push current script + settings to job, optionally re-trigger pipeline)  
  - `GET /series/:id/jobs` or `GET /series/:id/past-videos` (for Past Videos section)  
- **Frontend:** Same as spec: Dashboard = list series; Series edit = one series + upcoming video card + sidebar settings + Past Videos.
- **Pros:** Clean match to spec; “Past Videos” and multiple series make sense; one source of truth per series.  
- **Cons:** More backend work (series storage, endpoints).

### Option C: Copy reference app then wire API

- Copy the **full reference app** (Landing, Dashboard, Series edit, features.js, all controls) into the repo (e.g. `frontend/` or `klipora-web/`).
- Replace mock data with **API calls** to Mission Control + new series endpoints (Option B).
- Implement **features.js** and use it to show/hide or disable controls (unlocked vs locked).

---

## 3. Recommended implementation plan (Option B + C)

### Phase 1: Backend – Series and extended job

1. **Series storage**  
   - Redis: e.g. `series:{id}` = JSON (all spec fields).  
   - Optional: `series:ids` = set or list of series ids for “list all”.

2. **Extend job (meta) for full spec**  
   - Add to job (or meta): title, caption, visibility, allowComments, allowDuet, allowStitch, videoLength, contentType, imageCredits, motionCredits, captionStyle, captionFont, overlayPosition, voice, voiceSpeed, musicVolume (we have music_url already).  
   - WF-GEN / WF-VIDEO / WF-ASSEMBLE already use genre, duration, aspect_ratio, vstyle, nstyle; extend payload where needed (e.g. voice speed, music volume for render).

3. **New API (Mission Control or separate service)**  
   - `GET /series` – list series (from Redis).  
   - `POST /series` – create series (default settings).  
   - `GET /series/:id` – get series + optional “upcoming” job.  
   - `PUT /series/:id` – update series (title, caption, script, all settings).  
   - `DELETE /series/:id` – delete series.  
   - `POST /series/:id/generate-script` – create/update job from series, trigger WF-GEN with series topic + settings; return job_id.  
   - `POST /series/:id/update-video` – update job script/settings from series form; optionally re-push to script_queue if you want to re-run pipeline.  
   - `GET /series/:id/jobs` – list past jobs (for Past Videos).  
   - Optional: `GET /jobs/:id` for “upcoming” job status (script_ready, video_in_progress, etc.).

4. **Telegram + web**  
   - Keep Telegram flow as is (Generate Video → review → Approve).  
   - Web “Generate script” / “Update Video” use the new endpoints and same pipeline (script_queue → WF-VIDEO → … → Telegram review).

### Phase 2: Frontend – React app (spec-aligned)

1. **Stack**  
   - React 18, React Router 6, Vite (as in spec).  
   - Theme: dark (e.g. purple/gray), accent, DM Sans or similar.

2. **Routes**  
   - `/` – Landing (hero, how it works, pricing, FAQ).  
   - `/dashboard` – Series & Videos (list series cards or empty state).  
   - `/dashboard/series/new` – New series (empty form).  
   - `/dashboard/series/:id` – Series edit (upcoming video card + sidebar settings + Past Videos).

3. **Feature flags**  
   - Copy `features.js`: `UNLOCKED`, `FEATURES`, `isLocked(featureKey)`.  
   - Use for unlocked vs locked (e.g. video length, download, past videos).  
   - Can later drive from API (e.g. plan from auth).

4. **Screens (match spec)**  
   - **Landing:** Hero “Faceless Videos on Auto-Pilot”, CTA to dashboard, How it works (3 steps), Pricing (unlocked: one card; locked: 3 plans), FAQ, footer.  
   - **Dashboard:** “Series & Videos”, “Create new series”, series cards (thumb, title, Created date), empty state.  
   - **Series edit:**  
     - Toolbar: BACK, Delete, Download Video (when unlocked).  
     - Main: Upcoming video card (preview placeholder 9:16, title, caption, script, “Generate a completely new script”, “Update Video”).  
     - Sidebar: Publish Settings, Content Settings, Visual Styles, Caption & Overlays, Audio Settings, “Save Changes”.  
     - Below: Past Videos (when unlocked).

5. **Data flow**  
   - On load: `GET /series/:id` (and optional `GET /series/:id/jobs`).  
   - “Generate a completely new script” → `POST /series/:id/generate-script` → show “Script in progress” then poll job or get script when ready; fill script field.  
   - “Update Video” → `PUT /series/:id` (script + settings) + `POST /series/:id/update-video` (push to pipeline if needed).  
   - “Save Changes” → `PUT /series/:id`.  
   - “Download Video” → use job final video URL (from render or Telegram) when available; or `GET /jobs/:id` for asset URL.

### Phase 3: Pipeline wiring

1. **WF-GEN webhook**  
   - Accept extended payload from `POST /series/:id/generate-script`: topic, genre, duration, aspect_ratio, vstyle, nstyle, + title, caption, contentType, etc.  
   - Store in job; use existing Groq script generation.

2. **Job storage**  
   - When creating job from series, set `series_id` on job so “Past Videos” can list by series.  
   - When WF-VIDEO runs, job already has full meta (duration, aspect_ratio, vstyle, nstyle, music_url); add voiceSpeed, musicVolume to render payload if needed.

3. **Render / Telegram**  
   - No change: WF-ASSEMBLE → pending_approve → notify-preview → Telegram Approve → Railway Render.  
   - Optional: “Publish” from web could call same approve endpoint with job_id when video is ready.

---

## 4. Field mapping (spec → our pipeline)

| Spec | Our job / meta / pipeline |
|------|----------------------------|
| title | job.title or topic |
| caption | job.caption (new); could be sent to platform on publish |
| script | job.script (existing) |
| visibility | job.visibility (new); use at publish time |
| allowComments, allowDuet, allowStitch | job meta (new); use at publish time |
| videoLength 15/30/60/90 | job.duration (existing); map 15→15, 30→30, etc. |
| contentType | job.contentType (new); can influence Groq system prompt |
| aspectRatio 9:16 / 1:1 / 4:5 | job.aspect_ratio (existing); map to 9x16, 1x1, 4x5 |
| visualStyle | job.vstyle (existing) |
| imageCredits, motionCredits | job meta (new); optional for WF-VIDEO or render |
| captionStyle, captionFont, overlayPosition | job meta (new); for FFmpeg/render overlay |
| voice | job.nstyle (existing) or new voice id |
| voiceSpeed | job.voiceSpeed (new); pass to TTS or render |
| music | job.music_url (existing) |
| musicVolume | job.musicVolume (new); pass to render |

---

## 5. Effort summary

| Work | Effort | Notes |
|------|--------|------|
| Series model + Redis + API (Phase 1) | Medium | 5–8 endpoints, extend job meta |
| Extend WF-GEN payload (optional extra fields) | Low | Add fields to webhook body and Parse Job Params |
| React app from spec (Phase 2) | Medium–High | Landing, Dashboard, Series edit, all blocks, features.js |
| Wire “Generate script” / “Update Video” to API | Low | Call new endpoints from React |
| Past Videos (list jobs by series) | Low | GET /series/:id/jobs, store series_id on job |
| Feature flags (UNLOCKED / locked) | Low | features.js + conditional UI |
| Download Video | Low | Link to final asset URL when available |

---

## 6. Conclusion and next steps

- **We can implement the spec** by:  
  (1) introducing a **series** entity and **extended job** in the backend,  
  (2) adding a **React web app** that matches the spec (Landing, Dashboard, Series edit, all settings), and  
  (3) wiring “Generate script” and “Update Video” to the **existing pipeline** (WF-GEN → script_queue → WF-VIDEO → … → Telegram review → Approve → Render).

- **Immediate next steps:**  
  1. Decide: Option A (no series) vs Option B (series in backend).  
  2. Add series storage + endpoints (Phase 1).  
  3. Add or copy React app (Phase 2), then connect to API and pipeline (Phase 3).  
  4. Optionally add `features.js` and UNLOCKED/locked behavior from day one so the same codebase can run both modes.

This keeps Telegram as an alternative entry point while adding the full “faceless video on auto-pilot” web experience described in the spec.
