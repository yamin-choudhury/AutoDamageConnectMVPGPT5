# Angle Review and Clarification UI — Functional Requirements

Version: v1.0
Owner: Y. Choudhury
Status: Draft

## 1) Goal
Enable fast, accurate post‑upload angle clarification with a car‑diagram UI. The system auto-classifies angles (heuristic → LLM) and surfaces results for user review. Users correct angles, mark close‑ups, and separate interior images before running the damage report. This reduces cross‑angle mixing and model hallucination.

## 2) Definitions
- Angle: One of the canonical exterior viewpoints used for bucketing images for detection.
- Canonical angles (default): `front`, `front_left`, `front_right`, `side_left`, `side_right`, `back`, `back_left`, `back_right`, plus `unknown`.
- Category: `exterior` | `interior` | `document` (documents optional v1.5).
- Close‑up: An exterior photo focusing on a small region; still belongs to an angle bucket.
- Source: Angle assignment origin: `heuristic` | `llm` | `user`.

## 3) In Scope (v1)
- Auto angle classification via LLM (primary), with caching; optional heuristic assist for edge cases.
- Diagram-based angle review UI with 8 hotspots + unknown.
- Side panel to view/edit thumbnails for a selected angle.
- Marking images as `close-up` and `interior`.
- Persisting corrected metadata in the client state; optional DB persistence.
- Using corrected angles in the `/generate` flow with `ANGLE_BUCKETING` enabled.

## 4) Out of Scope (v1)
- Full drag & drop across hotspots (planned v1.5).
- Interior sub-location ontology (e.g., dashboard, rear seats) — basic tagging only.
- Advanced ML pre‑grouping beyond current heuristic + LLM.

## 5) High-level Flow
1. User uploads images in `ImageUpload.tsx` (existing behavior).
2. Frontend calls `POST /classify-angles` with uploaded URLs.
3. Backend classifies angles with an LLM as the primary classifier; caches by content hash to avoid repeat calls.
4. Frontend renders Angle Review screen:
   - Car diagram with clickable hotspots (one per angle) + unknown.
   - Clicking a hotspot opens a side panel listing thumbnails in that bucket.
   - Users can reassign angle, mark `close-up`, or change `category` to `interior`.
5. On confirm, the corrected metadata is attached to the document payload.
6. `/generate` uses the corrected metadata. Exterior images are filename‑tagged by angle during download, enabling per‑angle detection.

## 6) UX/UI Requirements
- Diagram
  - Top‑down car silhouette centered.
  - 8 hotspots around the silhouette; each displays a count badge.
  - An `unknown` badge in the center or adjacent to the diagram.
  - Hotspot states: default, hover, active, attention (if low-confidence items exist).
- Side Panel (Angle Bucket Panel)
  - Header: Angle label, count, quick actions (filter by source/close‑up/unknown).
  - Body: Virtualized thumbnail list with per-item controls:
    - Badges: `source` (heuristic/LLM/user), `confidence` tier badges (High/Med/Low; numeric in tooltip), `close-up` chip, `interior` chip.
    - Actions: `Move to angle…` (Select), `Toggle close-up`, `Set category: exterior/interior`.
    - Large image preview on click (modal/lightbox) with keyboard nav.
  - Multi-select support + bulk actions (move, toggle close-up, set category).
- Tabs
  - `Exterior` (default): shows diagram/hotspots.
  - `Close-ups`: grid of close-ups grouped by angle; reassign and toggle like above.
  - `Interior`: grid/list; angle controls hidden; category locked to `interior`.
- Accessibility
  - Hotspots are keyboard-focusable buttons with ARIA labels (e.g., "Front right (3 images)").
  - Keyboard: arrow keys move focus; Enter opens panel; number keys (1–8) reassign in panel.
  - Provide a fallback List View (no diagram) for screen readers/low-vision users.
- Responsiveness
  - Mobile: larger tap targets, bottom-sheet panel, stacked layout.
- Empty/Loading/Error States
  - Loading: skeletons on thumbnails.
  - Empty bucket: guidance text and CTA to move images here.
  - Unknown bucket: highlighted with a warning.
- Progress & Guardrails
  - Show unresolved unknown count prominently.
  - Block "Generate" until all exterior images have a non-unknown angle. Feature flag `ANGLE_REVIEW_BLOCK_ON_UNKNOWN=1` by default; admins can override if needed.
  - Minimum coverage guidance: surface hints if key angles (front/back/left/right) are missing; do not block.

## 7) Frontend Data Model
Extend image object in client state:
```ts
interface ReviewImage {
  url: string
  id?: string
  angle?:
    | 'front' | 'front_left' | 'front_right'
    | 'side_left' | 'side_right'
    | 'back' | 'back_left' | 'back_right'
    | 'unknown'
  category: 'exterior' | 'interior' | 'document'
  is_closeup?: boolean
  source?: 'heuristic' | 'llm' | 'user'
  confidence?: number // 0..1 if available
}
```

### 8.3 POST /save-angle-metadata
- Purpose: Persist user corrections (autosave debounced) to the DB for session resume and analytics.
- Request
```json
{
  "document_id": "doc_123",
  "images": [
    { "url": "https://.../x.jpg", "angle": "front_left", "category": "exterior", "is_closeup": false, "source": "user" },
    { "url": "https://.../y.jpg", "category": "interior", "source": "user" }
  ]
}
```
- Response
```json
{ "updated": 2, "errors": 0 }
```
- Behavior
  - Upsert by `(document_id, url)` into `images` table.
  - Only whitelisted fields are updated: `angle`, `category`, `is_closeup`, `source`, `confidence` (if provided).
  - Returns counts; partial failures reported per-item if applicable.

## 8) API Contracts
### 8.1 POST /classify-angles
- Request
```json
{
  "images": [
    { "url": "https://.../img1.jpg", "id": "a1" },
    { "url": "https://.../img2.jpg", "id": "a2" }
  ]
}
```
- Response
```json
{
  "results": [
    {
      "url": "https://.../img1.jpg",
      "id": "a1",
      "angle": "front_left",
      "source": "heuristic",
      "confidence": 0.86
    },
    {
      "url": "https://.../img2.jpg",
      "id": "a2",
      "angle": "unknown",
      "source": "llm",
      "confidence": 0.52
    }
  ]
}
```
- Behavior
  - LLM-primary for all images by default.
  - Concurrency-limited; cached by content hash where possible.
  - Optional heuristic assist for tie-breaks/very low-confidence cases.
  - Timeouts and partial failures return best-effort results with per-item errors.

### 8.2 POST /generate (existing)
- Include corrected metadata in `document.images` items:
```json
{
  "document": {
    "id": "doc_123",
    "images": [
      { "url": "https://.../x.jpg", "angle": "front_left", "category": "exterior", "is_closeup": false },
      { "url": "https://.../y.jpg", "category": "interior" }
    ],
    "vehicle": { "make": "Toyota", "model": "Corolla", "year": 2020 }
  }
}
```

## 9) Backend Requirements
- New endpoint `POST /classify-angles` in `backend/main.py`:
  - Downloads images to tmp.
  - Uses functions from `generate_damage_report_staged.py` to classify:
    - LLM as primary: `classify_image_angle_llm()` with retries/timeouts.
    - Optional heuristic assist when configured for edge cases.
  - Returns `angle`, `source` (typically `llm`), optional `confidence`.
  - Applies caching via content hash file DB; enforces concurrency limits.
- Update `download_images()` in `backend/main.py` (used by `/generate`):
  - For `category == 'exterior'` and when `angle` exists, write as `idx_{angle}.jpg`.
  - Interior/document images are saved separately or without angle suffix and excluded from angle-bucket detection.
- No changes required to `generate_damage_report_staged.py` logic:
  - `ANGLE_BUCKETING` already supported.
  - Filenames carrying angle tokens are honored by the heuristic.

## 10) Storage & Database
- Supabase Storage
  - Optional: include angle in storage key at upload time for traceability: `${documentId}/${angle||'unknown'}/${timestamp}_${name}`.
 - Database (v1)
  - Add columns to `images` table: `angle` (text), `category` (text), `is_closeup` (boolean), `source` (text), `confidence` (float).
  - Migration strategy: nullable columns; backfill as data appears.
  - Index: `(document_id, angle)` for review screens.
  - Corrections are autosaved via `POST /save-angle-metadata` (debounced) and also confirmed on finalize.

## 11) Feature Flags & Env
- Feature flag: `ANGLE_REVIEW_ENABLED` (frontend gate to show review step).
 - Feature flag: `ANGLE_REVIEW_BLOCK_ON_UNKNOWN` (default ON) — blocks generate until all exterior images are labeled.
- Env used by generator (already applied smart defaults in backend):
  - `ANGLE_BUCKETING`, `ANGLES`, `MAX_ANGLE_IMAGES`.
  - `COMPREHENSIVE_MODE`, verification thresholds, temps, etc. (kept as in current defaults).
 - Env used by angle classification:
   - `ANGLE_CLASSIFY_MODE=llm_only` (default)
   - `ANGLE_CLASSIFY_CONCURRENCY` (e.g., 6)
   - `ANGLE_CLASSIFY_TIMEOUT_S` (e.g., 15)
   - `ANGLE_CLASSIFY_CACHE=1`
   - Requires `OPENAI_API_KEY` (or the chosen vision model key) in backend env.

## 12) Performance & Reliability
- Virtualized lists for panels with >100 images.
- Image lazy loading with low‑res placeholders.
- Backend concurrency cap for LLM calls; retry/backoff.
- Cache angle classifications by content hash to avoid rework.

## 13) Analytics & Observability
- Metrics
  - Unknowns after heuristic
  - LLM classification share
  - User corrections rate by angle
  - Time to resolve unknowns
  - Proceed-with-unknown confirmation rate
- Logging
  - Classification latencies, error rates
  - Per-bucket counts and corrections

## 14) Security & Privacy
- Only public or signed URLs are used by backend for classification.
- Avoid persisting sensitive EXIF; strip if downloaded to tmp.
- PII-safe logging (truncate URLs).

## 15) QA Plan (Acceptance Criteria)
- Upload 12 mixed images → `/classify-angles` returns results; unknowns routed to panel.
- Reassigning an image updates its angle and source=`user`.
- Marking an image `interior` removes angle controls; excluded from angle buckets.
- Close-up marked image remains in the same angle bucket and is surfaced in Close‑ups tab.
- Proceed blocked when unresolved unknowns exist (configurable) or allowed with explicit confirmation.
- `/generate` writes exterior images as `idx_{angle}.jpg`; interior excluded from detection set.
- Final report runs per‑angle without cross‑angle mixing.
 - PDF includes an "Interior Evidence" section (thumbnails only, no detection).
 - PDF includes per‑angle "Close‑up Evidence" subsections for any close-ups.

## 16) Rollout
- Stage 1: Enable for internal testers; monitor metrics and logs.
- Stage 2: Enable for 50% of users via feature flag.
- Stage 3: Full rollout; keep fallback to legacy list review for one release.

## 17) Open Questions
- Should proceeding with unknowns be blocked by default?
- Do we want DB persistence for angle/category/is_closeup in v1?
- Confidence score exposure: always show, or hide below a threshold?
- Interior sub‑taxonomy needed soon (dashboard/boot/seats)?

## 18) Future Work (v1.5+)
- Drag‑and‑drop between hotspots and from panel to hotspots.
- Interior sub‑locations and guided interior checklist.
- Auto-suggestions: “These 3 look similar to front_left” (visual similarity).
- Bulk rename + keyboard‑only power user flow.

## 19) Decision Log (2025-08-11)
- Block Generate until all exterior images have a non-unknown angle.
- Persist corrections to DB in v1 (columns: angle, category, is_closeup, source, confidence).
- Autosave debounced per change; require explicit Confirm to proceed.
- Show tiered confidence badges (High/Med/Low) with numeric value in tooltip.
- Include a simple Interior Evidence section in the PDF (no detection), thumbnails only.
- Include per-angle Close-up Evidence in the PDF for context.
- Use the 8 exterior angles (+unknown) for v1; defer expansions.
- Minimum coverage policy is soft: show guidance if key angles are missing; do not block.

- Use LLM as the primary angle classifier; heuristic is optional assist only. No user file renaming required; backend writes `idx_{angle}.jpg` automatically.

## 20) Environment & Integration with Existing Infra

Below summarizes the current Supabase/Edge Functions/Backend usage so angle review integrates without surprises.

- __Edge Functions__ (`image-scribe-genesis-flow-main/supabase/functions/`)
  - `generate_report/index.ts`: marks `documents.status='processing'`, reads images from `document_images(image_url)` by `document_id`, then calls backend `REPORT_SERVICE_URL/generate` with payload `document` and `images: [{ url }]`.
  - `report-complete/index.ts`: webhook target for backend; updates `documents` with `status='ready'`, `report_json`, `report_json_url`, `report_pdf_url` when backend finishes and posts.

- __Frontend Supabase client__ (`src/integrations/supabase/client.ts`)
  - Uses Supabase JS v2 with a hardcoded URL and anon key. Components (e.g., `src/components/ImageUpload.tsx`) upload to Storage bucket `images` and insert rows into a table named `images` with `{ document_id, url }`.

- __Backend service__ (`backend/main.py`)
  - Uses Python Supabase client with `SUPABASE_SERVICE_ROLE_KEY`.
  - Uploads artifacts (JSON/PDF) to Storage bucket `reports` (configurable via `REPORT_BUCKET`).
  - For HTML rendering fallback, fetches image URLs from `images` table: `sb.table("images").select("url").eq("document_id", doc_id)`.
  - Calls the `report-complete` edge function after uploads; honors `REPORT_COMPLETE_WEBHOOK_URL` override.

- __Schema & migrations__ (`image-scribe-genesis-flow-main/supabase/migrations/`)
  - Define `documents` and `document_images (document_id, image_url, image_name, ...)`.
  - No migration present here for a table named `images`; yet frontend and backend both reference a table `images`.

__Implication__: There is a table mismatch. Edge function sources `document_images`, while frontend/back‑end read/write `images`. Angle metadata persistence and angle‑aware generation will be unreliable unless we standardize the source of truth for uploaded images and their metadata.

### 20.1 Recommended Alignment (minimal‑change path)

- __Standardize on `images` table__ for angle metadata.
  - Keep frontend inserts as-is (`.from('images').insert({ document_id, url })`).
  - `/save-angle-metadata` continues to upsert `angle`, `category`, `is_closeup`, `source`, `confidence` keyed by `(document_id, url)`.
  - __Update edge function `generate_report`__ to read from `images` instead of `document_images`, e.g.:
    - Select `url, angle, category, is_closeup, source, confidence` and include these fields in the `document.images` payload.
    - __Fallback__: if `images` is empty for a `document_id`, fall back to `document_images(image_url)` to avoid breaking existing data.

- __Migration for `images` table__ (if not already applied):
  - Add columns and unique key:
    - `angle text, category text, is_closeup boolean default false, source text, confidence double precision, updated_at timestamptz default now()`
    - Unique index on `(document_id, url)` for clean upserts
    - Index `(document_id, angle)` filtered to `category='exterior'` for review screens

### 20.2 Alternative Alignment (use `document_images` as canonical)

- Update frontend to insert into `document_images` instead of `images` and rename field to `image_url`.
- Change backend `/save-angle-metadata` and any readers to operate on `document_images` and use `image_url`.
- This is a larger change across codepaths and not recommended given current usage in `backend/main.py` and React components.

### 20.3 Storage & Env consistency

- __Buckets__: `images` for raw uploads (frontend). `reports` for outputs (backend).
- __Edge env__: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `REPORT_SERVICE_URL`.
- __Backend env__: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `REPORT_BUCKET=reports`, optional `REPORT_COMPLETE_WEBHOOK_URL`.

### 20.4 Angle Review flow within this infra

- After upload, frontend calls `POST /classify-angles`, shows AngleBoard, and autosaves to `/save-angle-metadata` (debounced) into `images`.
- The __Generate__ action should trigger the edge `generate_report` function only after user Confirm. With the above alignment, the edge function will pull enriched rows from `images` and backend will perform per‑angle detection based on the provided `angle`/`category`.

### 20.5 Action Items

- __Add/verify DB migration__ for `images` columns/indexes as above.
- __Patch edge function `generate_report`__ to select from `images` first, fallback to `document_images`.
- __Frontend__: gate the review step with `ANGLE_REVIEW_ENABLED`; block with `ANGLE_REVIEW_BLOCK_ON_UNKNOWN` until Confirm.
