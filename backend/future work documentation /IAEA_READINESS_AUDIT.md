# IAEA Readiness Audit & Remediation Plan

This document audits the current damage-report generation pipeline and defines a concrete plan to reach an auditor-grade standard suitable for the Institute of Automotive Engineer Assessors (IAEA)-level scrutiny.

Key code:
- `backend/main.py` — FastAPI `/generate` endpoint: download → run generator → HTML→PDF → upload → webhook.
- `backend/generate_damage_report_staged.py` — staged AI pipeline (vehicle ID, quick detection, area-specialist detection, enrichment, summary).
- `backend/prompts/` — prompt files used by the phases.

---

## 1) Current Pipeline (High-Level)

- Image ingestion: Supabase public URLs → downloaded to temp dir by `download_images()` in `backend/main.py`.
- Generator script: `backend/generate_damage_report_staged.py` executes multi-phase:
  - Phase -1 Vehicle identification (Vision; small image batches; consensus voting).
  - Phase 0 Quick damaged-area detection (Vision per image; fallback generic detector on all images).
  - Phase 1 Area-specialist detection (Vision; prompt shards A/B; temps [0.1, 0.4, 0.8]; uses `make_crops()` for ROI and wide crops).
  - Phases 2–4: Text-only enrich/plan/summary (Chat completions) with JSON outputs.
  - Deduplication and final JSON.
- PDF: `backend/main.py` converts JSON → HTML → PDF via Playwright.
- Upload & notify: JSON/PDF uploaded to Supabase Storage, then webhook notifies completion.

---

## 2) Issues Identified (Comprehensive)

### A. Image handling & AI payloads
- **Oversized Vision payloads**: `encode_image_b64()` resizes via PIL but base64-encodes the original file bytes (not the resized), inflating requests.
- **Too many images per call**: Generic fallback may send all images at once; Phase 1 also adds full frames in addition to crops.
- **No standardized image selection**: First-N selection can overload tokens and still miss critical evidence; no best-angle heuristics.
- **Missing evidence provenance**: No EXIF capture, timestamps, photographer identity, geotag, chain-of-custody.

### B. Prompting & result structure
- **Prompt drift**: Area mapping uses `detect_*_A/B.txt` while “enterprise” prompt constants exist but are not wired; risk of intent drift.
- **Weak schema enforcement**: Vision outputs rely on trimming code fences and free-form JSON; brittle under load.
- **No controlled vocabulary**: Parts not constrained to a canonical taxonomy (Thatcham/Audatex-like) → duplicates/ambiguity.
- **Severity ambiguity**: Hours-to-severity mapping can drift without authoritative tables.
- **No OEM method references**: Missing repair method sources and rationale links (OEM/Thatcham IDs).
- **No ADAS context**: Missing explicit ADAS/SRS impact flags and calibration requirements.

### C. Concurrency, timeouts, reliability
- **Tight timeouts**: 20–30s per Vision task; frequent timeouts with large payloads.
- **Burst concurrency**: Multiple phases spawn many parallel Vision calls; no global cap → rate limits (429) and cascading failures.
- **No retries/backoff**: Transient failures kill phases; no exponential backoff with jitter.
- **Process hard-exits**: Failure paths can `sys.exit` non-zero → FastAPI error → webhook not fired → stuck "processing".
- **PDF subprocess fragility**: Playwright print may fail without graceful fallback or retry.

### D. Data model, storage, security
- **Public report storage**: JSON/PDF in public bucket risks PII/claim data exposure.
- **Double upload/webhook**: Script may upload/notify in production while FastAPI also uploads/notifies → duplicates/inconsistency.
- **Weak least-privilege**: Service role key used broadly; unclear RLS constraints for private artifacts.

### E. Report content vs IAEA expectations
- **Missing assessor-critical sections**:
  - Vehicle identity depth: VIN/VRM decode, trim, engine, paint code.
  - Incident details: date, location, description; pre-accident condition; mileage.
  - Roadworthiness/safety statement; structural vs cosmetic classification.
  - ADAS/SRS impact: airbags, pretensioners, radars, cameras; calibration ops.
  - Method references: OEM/Thatcham citations, torque specs, corrosion protection, NVH pads, seam sealer.
  - Deterministic labor times (authoritative source); parts pricing source and date.
  - Paint operations: panel grade, blend allowances, materials.
  - Cost summary: labor, parts, paint/materials, sublet, ADAS, alignment, sundries, storage, VAT.
  - Salvage/write-off analysis: market value, salvage value, thresholds (Cat N/S rationale).
  - Annotated photo board with figure numbers/captions.
  - Assessor credentials, digital signature, disclaimers, revision history.

### F. Workflow & governance
- **No structured review/sign-off**: No RBAC workflow for second-check and approval; no lock on finalized reports.
- **No versioning/audit trail**: Prompts, model versions, code SHA, and intermediate artifacts not recorded per job.
- **Async orchestration gaps**: HTTP lifecycle coupled; no durable queue/worker with retries/status.
- **No SLA/progress visibility**: Users see a generic "processing" without phase progress.

### G. Observability, QA, testing
- **Limited telemetry**: No correlation IDs across FastAPI, generator, OpenAI calls, storage, webhook.
- **PII in logs risk**: Prompts/outputs may contain PII; no redaction policy.
- **No golden datasets**: Absent fixed datasets with expected JSON for regression.
- **No schema tests**: JSON schema not enforced and validated per phase.
- **Flaky ensembles**: Temperature ensembles reduce reproducibility without seeds and sampling control.

### H. Frontend/PDF presentation
- **Basic PDF**: Lacks professional layout (cover, ToC, headers/footers, figure references, page numbers).
- **Image selection**: Historically included all images; should include curated damage-relevant set + photo board.
- **Branding & readability**: Limited assessor-grade structure and consistent styles.

---

## 3) Quick Wins (High Impact / Low Risk)

- **Fix base64 resize bug**: Encode the resized image bytes (or switch to image URLs) in Vision calls.
- **Limit images per call**: Cap at 3–4 best images per Vision request; sample smartly per phase.
- **Retries + backoff**: Add 3 retries with exponential backoff/jitter for 429/5xx and JSON-parse failures.
- **Global concurrency cap**: Enforce a single semaphore across all OpenAI calls (e.g., 3–4 concurrent max).
- **Never exit non-zero**: On failures, emit minimal valid JSON and continue; always update status/notify.
- **Private reports bucket**: Move JSON/PDF to private storage with signed URL access; enforce RLS.
- **Strict JSON schemas**: Define pydantic models and validate inputs/outputs for each phase.
- **Upgrade PDF template**: Add cover, headers/footers, page numbers, structured sections, curated photo board.

---

## 4) Detailed Remediation Plan (Phased)

### Phase 0 — Stabilization & Safety (1–3 days)
- [ ] Fix `encode_image_b64()` to encode resized image bytes or switch Vision to use `image_url` (preferred).
- [ ] Introduce global OpenAI concurrency limiter (semaphore) across phases.
- [ ] Implement retries with exponential backoff for Vision/Text calls.
- [ ] Increase timeouts: Vision 45–60s; stagger per phase.
- [ ] Cap images per Vision call and implement a best-angle sampler.
- [ ] Ensure generator never `sys.exit` on phase failures; always return a valid JSON and set status.
- [ ] Unify upload/notify path to avoid double-notify (generator vs FastAPI). Choose one system of record.
- [ ] Move report storage to private bucket; add signed URL generation; confirm RLS policies.

### Phase 1 — Schema & Prompt Hardening (2–4 days)
- [ ] Define canonical JSON schemas (pydantic + jsonschema) for each stage and final report.
- [ ] Enforce schema via OpenAI function-calling/tool-call or strict prompt wrappers.
- [ ] Replace multi-temp ensembles with 1–2 robust prompts + validator passes.
- [ ] Align `area_prompt_map` with intended “enterprise” prompts; remove unused prompt constants.
- [ ] Controlled vocabulary: introduce a canonical parts taxonomy and synonym map; normalize outputs.
- [ ] Add ADAS/SRS extraction fields; calibration requirements section.

### Phase 2 — Professional PDF & Report Content (3–6 days)
- [ ] Design assessor-grade PDF template: cover page, ToC, headers/footers, page numbers, sections.
- [ ] Add curated photo board with figure numbers and captions referencing `damaged_parts`.
- [ ] Add explicit sections: incident details, roadworthiness, classification (structural/cosmetic).
- [ ] Include method references section (OEM/Thatcham) and rationale for repair vs replace.
- [ ] Add cost summary table (labor, parts, paint/materials, sublet, ADAS, alignment, sundries, storage, VAT).
- [ ] Add assessor credentials, digital signature, disclaimers, revision history.

### Phase 3 — Workflow, Governance, Security (3–6 days)
- [ ] Introduce a job queue/worker (e.g., Celery/RQ) with durable retries and status transitions.
- [ ] Add RBAC review/sign-off flow; lock finalized reports (PDF/A) with timestamp.
- [ ] Record per-job metadata: prompt version, model versions, code git SHA, image hashes, intermediate JSON artifacts.
- [ ] Enforce least-privilege credentials; remove broad service-role usage from runtime paths.
- [ ] Webhook resilience: queue + retries; DB-first state source of truth.

### Phase 4 — Deterministic Costing & Integrations (longer term)
- [ ] Integrate authoritative labor time source (license-dependent) or maintain vetted internal rulesets with references.
- [ ] Parts pricing integration or curated catalog; record source/date and OEM/aftermarket flags.
- [ ] VIN/VRM decoding for exact trim/paint code; enrich report vehicle details.
- [ ] ADAS calibration rules by model; optionally integrate pre/post scan (DTC) if available.
- [ ] Total-loss engine: market value and salvage estimation with transparent logic.

---

## 5) Acceptance Criteria (IAEA-Grade Minimum)

- **Technical robustness**
  - Vision requests use URLs or properly resized base64 images; bounded concurrency; retries in place.
  - All phases produce schema-valid JSON; failures yield minimal valid results without crashing.
  - Private storage with signed URLs; strict RLS; least-privilege keys.
  - Full observability with correlation IDs and structured logs.

- **Report content**
  - Vehicle identity (VIN/VRM decode), incident details, pre-accident condition, mileage.
  - Damage classification (structural/cosmetic), roadworthiness statement.
  - Canonical parts list with controlled vocabulary; operations; labor times with source.
  - Paint operations and materials; ADAS/SRS impacts and calibration ops.
  - Cost summary including VAT and subcategories; rationale for repair vs replace with method references.
  - Annotated photo board; assessor credentials; digital signature; disclaimers; revision history.

- **Workflow & auditability**
  - Job queue with retries; progress and SLA visibility.
  - Reviewer sign-off; immutable finalized report with recorded versions (prompts, models, code SHA).

---

## 6) Observability & QA Plan

- **Tracing**: Correlation ID per job across FastAPI, generator, OpenAI calls, uploads, webhook.
- **Metrics**: Time per phase, token usage, error rates, retries, timeouts, payload sizes.
- **Redaction**: PII-safe logs; redact sensitive fields in prompts/responses.
- **Golden datasets**: Curate scenario-based image sets with expected JSON and PDFs; run in CI.
- **Schema tests**: Unit and integration tests validating each phase against pydantic/jsonschema.
- **Determinism**: Control sampling; allow seeds for reproducible runs.

---

## 7) Decision Log (to maintain)

- [ ] Upload/notify single source of truth: (Decide: generator vs FastAPI path).
- [ ] Vision ingestion method: (Decide: URLs vs resized base64; default to URLs).
- [ ] Prompting approach: (Decide: function-calling vs schema-repair pass).
- [ ] Parts taxonomy: (Decide: specific standard and mapping rules).
- [ ] Labor times source: (Decide: licensed provider vs internal rulesets).

---

## 8) Next Steps (Immediate)

1. Implement Quick Wins in Phase 0 (payload, concurrency, retries, no hard exits, private storage).
2. Draft the canonical JSON schema and controlled vocabulary mapping.
3. Sketch the professional PDF outline and section placeholders.
4. Align prompt inventory and remove unused constants.
5. Plan queue/worker migration and RLS hardening.

---

Maintainer: add dates, owners, and links to issues/PRs as tasks progress.
