# SIH26143 Maritime Oil-Spill Attribution — Project Implementation Guide

> This document is the practical build guide for the project described in [ai-ml-maritime-oil-spill-architecture.md](./ai-ml-maritime-oil-spill-architecture.md). It turns that architecture into an ordered implementation plan, with boundaries, contracts, local development steps, completion criteria, and operational guidance.

## 1. Project goal

Build an investigator-facing application that takes a Sentinel-1 SAR observation of a suspected oil slick and produces a traceable, evidence-based list of possible source vessels. The system must preserve the uncertainty in each step and present candidate vessels as investigative leads, never as proof of responsibility.

The complete workflow is:

1. An analyst creates a case and supplies a SAR image reference and acquisition metadata.
2. The backend starts a durable pipeline run.
3. Slick detection produces a georeferenced polygon and quality metadata.
4. Drift hindcasting estimates possible source regions and a spill-time window.
5. AIS correlation ranks vessels using spatial, temporal, anomaly, and reporting-gap evidence.
6. The analyst reviews the map, candidate table, evidence, source quality, and run audit trail.

The first runnable milestone should use a deterministic fixture mode. Real data processing is added stage by stage after the whole workflow can run end to end.

## 2. Scope and non-goals

### In scope

- A web interface for case creation, pipeline monitoring, maps, candidate review, and analyst notes.
- A Python FastAPI application for analyst-facing REST APIs, authentication integration, case/run lifecycle, persistence, and orchestration.
- Three independently deployable FastAPI AI services: slick detection, drift hindcast, and AIS correlation.
- PostgreSQL for searchable case, run, evidence, and audit metadata.
- S3-compatible object storage for large source and result files.
- A job queue and worker for long-running or retryable work.
- Fixture data and a reproducible demo that runs without external data credentials.
- Version and provenance capture for inputs, models, software, and configuration.

### Out of scope for the initial release

- Automated legal conclusions, enforcement actions, or automatic accusations.
- Guaranteed identification of the responsible vessel.
- Production access to restricted satellite, environmental, or AIS data without provider credentials and usage rights.
- Claims of scientific accuracy until evaluated against labeled, representative cases.
- A training platform for building and labeling large segmentation datasets.

### Requirements from the SIH problem statement

The official challenge extends beyond identifying the slick's origin. The implementation should also:

- Accept SAR imagery and support EO imagery through a sensor-aware ingestion contract. Deliver SAR first; add EO preprocessing as a separately validated path because optical and SAR data need different preprocessing.
- Characterize slick geometry and estimate slick age when the available observations support it. Treat age as an estimate, include its method and confidence, and return `unavailable` when a single observation cannot support a defensible estimate.
- Backtrack the slick to estimate its origin and spill-time window, and forecast its likely forward movement from the observation time.
- Reconstruct vessel traffic around the estimated origin and time window, filter unrelated traffic, and rank candidates using proximity, trajectory consistency, timing, and behavioral anomalies.
- Support real AIS inputs when licensed and available, while providing synthetic AIS fixtures for a reproducible demonstration.

The problem statement's listed starting points are [MarineCadastre AccessAIS](https://marinecadastre.gov/accessais/) and the [Sentinel-1 SAR oil-spill dataset, Part I](https://zenodo.org/records/8346860), [Part II](https://zenodo.org/records/8253899), and [Part III](https://zenodo.org/records/13761290). Confirm each dataset's license, metadata, and suitability before using it for training or public redistribution. The [SIH26143 statement](https://sih2026-ps-viewer.vercel.app/ps/SIH26143) is the reference for these requirements.

## 3. System components and boundaries

| Component | Owns | Must not own |
| --- | --- | --- |
| Frontend | Case workspace, run status, map layers, candidate selection, evidence presentation, analyst notes | Authorization decisions, scientific calculations, direct calls to AI services |
| FastAPI backend | UI-facing API, identity/authorization integration, case and run state, orchestration, result persistence, audit events | CNN inference, particle simulation, AIS scoring algorithms |
| Slick detection service | SAR validation/preprocessing, segmentation, polygonization, detection artifacts | Drift simulation or vessel ranking |
| Drift hindcast service | Environmental data checks, particle simulation, origin probability and time window | Vessel identity or blame assessment |
| AIS correlation service | AIS normalization/filtering, evidence features, configured score and ranking | Slick segmentation or drift simulation |
| PostgreSQL | Searchable records and lifecycle state | Large raster, NetCDF, or Parquet payloads |
| Object storage | Immutable, versioned source and scientific artifacts | Workflow state transitions |
| Queue and worker | Durable execution, retries, long-running stage work | User-facing API response rendering |

The backend and the three AI services are separate Python applications. Give each a separate container, settings, health endpoint, logs, and deployment configuration. Keep service-to-service APIs private to the application network.

## 4. Suggested repository layout

Use this layout as the implementation target. It can be adjusted to match the existing repository, but keep the ownership boundaries clear.

```text
sih-architecture/
  README.md
  documation.md
  ai-ml-maritime-oil-spill-architecture.md
  docker-compose.yml
  .env.example
  frontend/
    src/
      app/ auth/ api/ cases/ pipeline/ map/ attribution/ components/
    public/
    Dockerfile
  backend/
    app/
      main.py
      api/                 # FastAPI routers and dependencies
      schemas/             # Pydantic request/response models
      application/         # Use cases and orchestration
      domain/              # Case, run, state machine, evidence rules
      infrastructure/      # DB, object storage, queue, identity adapters
      clients/              # Async HTTPX clients for the AI services
      workers/              # Queue consumers and stage execution
      settings.py
    migrations/
    tests/
    pyproject.toml
    Dockerfile
  services/
    slick-detection/
    drift-hindcast/
    ais-correlation/
  data/
    sample/sar/
    sample/environment/
    sample/ais/
    expected/
  infra/
    postgres/
    object-storage/
    monitoring/
  docs/
    api-contracts/
    demo-script.md
```

Each service should have its own `app/`, `tests/`, `pyproject.toml`, and `Dockerfile`. Share only stable contract models or a small internal package; do not share domain implementation in a way that couples deployments.

## 5. Technology and implementation conventions

Select concrete dependency versions during implementation and lock them in each Python project. Avoid floating production dependencies. The architectural choices are:

- Backend and AI APIs: Python, FastAPI, Pydantic, and async HTTPX clients.
- Database: PostgreSQL with SQLAlchemy 2.x or an equivalent async persistence layer; Alembic for schema migrations.
- Queue: a durable broker and worker framework supported by the deployment environment. Keep the queue adapter behind an interface so local and hosted choices can differ.
- Object storage: S3-compatible API, with a local S3-compatible service for development.
- Frontend: TypeScript web application with a query cache, map renderer, and accessible tables and controls.
- Geospatial/scientific services: rasterio/GDAL/shapely for SAR geometry; xarray/netCDF tooling and OpenDrift for hindcast; pandas/geopandas/shapely for AIS analysis; PyTorch for a trained segmentation model.
- Local development and deployment: Docker Compose for a complete local stack; container orchestration can be added for hosted deployment.

Use UTC timestamps everywhere. Validate coordinate reference systems, geographic bounds, timestamp ordering, and units at service boundaries. Represent large file inputs and outputs with artifact references, not embedded JSON arrays or binary payloads.

The public backend API examples use camelCase JSON fields. Python code uses snake_case. Use explicit Pydantic aliases and test serialization so the API does not accidentally change casing. AI-service contracts may use snake_case consistently; do not silently mix conventions within one API.

## 6. Domain model and persistence

Implement the following core records before adding scientific processing:

- **AttributionCase**: id, title, region, owner/organization, lifecycle status, SAR input reference, acquisition timestamp, created/updated timestamps.
- **PipelineRun**: id, case id, status, current stage, correlation id, idempotency key, attempt count, timestamps, failure details, configuration snapshot.
- **Artifact**: id, run id, URI, SHA-256, content type, byte size, creation timestamp, producer and producer version.
- **SlickObservation**: run id, polygon artifact/reference, geometry summary, detection timestamp, sensor type, model/preprocessing version, confidence and quality warnings, and optional age estimate with method and confidence.
- **HindcastResult**: run id, backward origin probability grid and trajectories, forward forecast trajectories/probability grid, estimated spill window, engine/configuration version, forcing-data provenance and coverage warnings.
- **VesselCandidate**: run id, MMSI, vessel name when available, rank, total score, confidence label, source track reference.
- **EvidenceItem**: candidate id, feature type, normalized component value, weight, source record/artifact reference, explanation, quality caveat.
- **AuditEvent**: case/run id, actor or system identity, action, timestamp, correlation id, structured details.
- **AnalystNote**: case/run/candidate reference, author, text, timestamps, and edit history or append-only audit event.

Use migrations to create these tables. Add indexes for case ownership, run status, run-to-case lookup, candidate rank, and audit chronology. Enforce foreign keys and uniqueness for artifact checksums or idempotency keys where appropriate. Store geometry in a geospatial column only if PostGIS is part of the selected database setup; otherwise store a validated GeoJSON reference and summary.

Store large GeoTIFF, NetCDF, AIS Parquet, trajectories, segmentation masks, and exports in object storage. Persist their checksum and metadata in PostgreSQL. Treat artifacts as immutable; a retry that produces a new artifact should create a new version and retain the prior provenance.

### Run states

Use a finite state machine and persist every transition:

`QUEUED → DETECTION_RUNNING → DETECTION_COMPLETED → HINDCAST_RUNNING → HINDCAST_COMPLETED → CORRELATION_RUNNING → COMPLETED`

Any running stage may transition to `FAILED` or `CANCELLED` where applicable. A retry should resume at the failed stage only when its inputs and preceding artifacts still validate. Keep stage-specific status, attempt number, timestamps, and a stable error code. Never mark a run complete when only some stages succeeded.

## 7. API contracts

### Analyst-facing backend API

Prefix routes with `/api/v1`. Protect all case data with backend authorization, even when the frontend hides a route.

| Method | Route | Behavior |
| --- | --- | --- |
| `POST` | `/api/v1/cases` | Validate input references and create a case. |
| `GET` | `/api/v1/cases` | List only cases the user may access; support pagination and filters. |
| `GET` | `/api/v1/cases/{caseId}` | Return case summary and current run state. |
| `GET` | `/api/v1/cases/{caseId}/timeline` | Return stage transitions and audit events. |
| `POST` | `/api/v1/cases/{caseId}/runs` | Create a run, enqueue it, and return `202 Accepted` with a run id. |
| `POST` | `/api/v1/cases/{caseId}/cancel` | Request cancellation of an active run. |
| `GET` | `/api/v1/cases/{caseId}/results` | Return available stage outputs and artifact links. |
| `GET` | `/api/v1/runs/{runId}` | Return status, current stage, progress, and stable error information. |
| `POST` | `/api/v1/cases/{caseId}/notes` | Add a timestamped analyst note and audit event. |

For long-running work, respond immediately with `202 Accepted`; expose progress through polling first. SSE or WebSocket updates are optional and should not be required for the MVP. Use cursor or page-based pagination for case lists and candidate results.

Use a consistent error body such as `{ "code", "message", "retryable", "correlationId", "details" }`. Do not return stack traces, secrets, internal object-store credentials, or raw service error bodies to the browser.

### Backend-to-AI service contracts

All requests include `X-Correlation-Id`, `X-Pipeline-Run-Id`, `X-Idempotency-Key`, and service authentication. Services echo the correlation id. Validate responses before persisting them.

1. **Detection** `POST /detect-slick`: input SAR or EO artifact URI, sensor type, acquisition timestamp, product id, and sensor-specific metadata such as SAR polarization. Output detection id, slick GeoJSON or artifact URI, geometry statistics, confidence, optional age estimate, model/preprocessing versions, and warnings.
2. **Drift** `POST /hindcast`: input slick reference, observation time, allowed spill interval, wind/current artifact references, leeway, and particle configuration. Backtrack from the observation to estimate origin and spill-time window; forecast forward from observation using the same configured environmental forcing. Output origin and forecast artifact references, spill-time window, simulation metadata, forcing-data provenance, and quality warnings.
3. **Correlation** `POST /correlate`: input origin probability-grid reference, spill window, AIS track reference, forward trajectory reference where available, and versioned scoring weights. Output ranked candidates, component scores, evidence references, scoring version, and generated timestamp.

Return `422` for invalid fields, `404` for missing referenced artifacts, `401/403` for service authentication failures, `429` for rate limits, and retryable `5xx` for transient processing errors. Keep error codes stable even if implementation libraries change.

## 8. Build plan

Build the complete vertical slice before investing heavily in model sophistication.

### Milestone 0 — Project foundation

- Create the repository layout and a README linking this guide and the architecture diagram.
- Add formatting, linting, type checking, and per-service dependency locks.
- Add `.env.example` containing placeholders only; never commit real credentials.
- Add Dockerfiles and a compose file for backend, three AI services, frontend, PostgreSQL, object storage, and queue.
- Add health and readiness endpoints to every service.

**Done when:** a fresh checkout can start every container and each health endpoint returns healthy.

### Milestone 1 — Fixture-mode end-to-end workflow

- Implement backend schemas, migrations, case and run endpoints, authorization boundary, state machine, and audit events.
- Implement queue enqueue/consume flow with retry and idempotency behavior.
- Implement each AI API with request/response validation and a deterministic fixture implementation.
- Store fixture outputs in object storage and metadata in PostgreSQL.
- Build a frontend case form, run monitor, map/result placeholders, candidate list, and evidence detail panel.

**Done when:** a user can create a fixture case, see all three stages complete, and inspect deterministic results from a clean local start.

### Milestone 2 — SAR slick detection

- Validate file type, raster dimensions, bands, georeferencing, CRS, acquisition time, and polarization.
- Add a sensor-type field to the input contract. Implement the SAR path first; treat EO imagery with its own atmospheric/cloud masking, band selection, and calibration rather than passing it through SAR preprocessing.
- Implement calibration and record its assumptions and source product metadata.
- Add optional speckle filtering and land masking; make settings versioned and reproducible.
- Load a trained, versioned U-Net model. Do not claim model accuracy without held-out labeled data.
- Convert positive mask components to valid GeoJSON polygons, calculate area/perimeter, and reject empty or invalid geometry.
- Estimate age only when multiple observations or validated contextual inputs support it; report the estimate, uncertainty, method, and inputs. A single image may be insufficient.
- Save the source, processed raster/mask where licensed, result polygon, model version, and quality metadata.

**Done when:** an approved sample image produces a valid, georeferenced polygon and the UI shows it with acquisition metadata.

### Milestone 3 — Drift hindcast

- Load and subset ERA5 wind and HYCOM current forcing for the region/time bounds.
- Validate coverage, timestamps, coordinate conventions, units, missing values, and data versions.
- Seed particles along the observed slick polygon and run backward with configurable time step, leeway, duration, and particle count.
- Run backward particles to build and normalize the origin probability grid and estimate the spill-time interval.
- Run forward particles from the observed slick time to estimate likely future movement; store forecast trajectories and field separately from the source-origin probability.
- Keep backward-origin likelihood and forward-forecast likelihood semantically distinct in the API and map legend.
- Save forcing subsets, simulation settings, trajectories, probability grid, and a reproducibility manifest.
- Render the field with a numeric legend that describes whether values mean normalized probability, density, or relative likelihood.

**Done when:** a fixture or approved sample run produces a probability artifact and time interval that can be reopened from the case page.

### Milestone 4 — AIS correlation

- Normalize real or synthetic AIS inputs, validate MMSI/timestamps/coordinates, handle duplicates, and document interpolation or gap policy.
- Limit tracks by the backward origin region and spill-time window before feature calculation; exclude traffic that cannot plausibly intersect the event window.
- Calculate proximity to high-probability source cells, trajectory consistency, temporal alignment, speed/course anomalies, and reporting gaps.
- Make synthetic AIS fixtures reproduce plausible traffic, unrelated traffic, a candidate near the origin, and missing-reporting scenarios without representing real vessels.
- Define feature normalization and configurable weights; validate that weights are finite, bounded, and normalized according to the selected scoring rule.
- Return per-feature values, weights, underlying source record references, explanations, and score-model version.
- Label outputs as leads and provide “insufficient data” or “no candidates” outcomes.

**Done when:** a known fixture yields ranked vessels whose component scores can be inspected and traced back to inputs.

### Milestone 5 — Analyst-ready workflow

- Synchronize map selection, candidate table selection, and evidence panel by stable candidate id.
- Add filters for time and vessel, independent layer toggles, data timestamp labels, and a probability legend.
- Add loading, partial, empty, failed, retryable, permission-denied, stale-data, and no-candidate states.
- Add analyst notes, timeline/audit display, and artifact download links with short expiry.
- Make keyboard access and non-map textual summaries usable.

**Done when:** an analyst can follow a case from input to evidence review without relying on color alone or losing context on a partial failure.

### Milestone 6 — Hardening and demo packaging

- Add authentication/authorization, secret management, input limits, rate limits, and artifact URI allowlists.
- Add timeout, retry, circuit-breaker, cancellation, dead-letter, and recovery behavior.
- Add structured logs, metrics, traces, correlation propagation, and data-quality warnings.
- Document local startup, fixture walkthrough, environment variables, limitations, and known gaps.
- Record measured stage duration and any measured evaluation results; leave unknown metrics explicitly unreported.

**Done when:** a clean machine can follow the README, run the fixture demonstration with one command, and reproduce the documented outputs.

## 9. Local development runbook

The commands below describe the intended workflow; adjust service names to the final compose file.

1. Install Docker/Compose and the language runtimes used by the frontend and Python services.
2. Copy `.env.example` to a local untracked `.env` and set development-only values. External provider credentials are not needed for fixture mode.
3. Start infrastructure and applications with `docker compose up --build`.
4. Check backend and AI-service `/health/live` and `/health/ready` endpoints.
5. Open the frontend, create a fixture case, start a run, and follow the run timeline.
6. Inspect the slick layer, optional age estimate, backward origin layer, forward forecast, clearly labeled synthetic AIS tracks, candidate evidence, warnings, and audit events.
7. Stop with `docker compose down`. Preserve named volumes when retaining local database/artifact data; remove them only when intentionally resetting the demo.

Provide a fixture seed command or startup seed that is safe to run repeatedly. The demo should avoid downloading multi-gigabyte data or model weights at runtime. If a real model is optional, clearly indicate whether fixture mode or model inference produced the current result.

## 10. Configuration and secrets

Document every setting in `.env.example`, with a description and safe default where possible. At minimum include:

- Backend: environment, API prefix, database URL, queue URL, object-store endpoint/bucket/region, token issuer/audience, allowed origins, artifact URL expiry, and log level.
- Service clients: detection/hindcast/correlation base URLs, connect/read timeouts, retry count, and service credentials.
- Detection: model URI/version, maximum raster size/dimensions, preprocessing settings, and allowed CRS values.
- Hindcast: forcing-data locations/version, maximum duration, particle-count limit, time-step limit, and CPU/memory limits.
- Correlation: AIS source, maximum track size/time span, default scoring weights, scoring version, and candidate limit.
- Frontend: public backend base URL and identity-provider client configuration only. Never expose service credentials or storage secrets.

Validate settings at process startup and fail clearly when required settings are missing. Keep production secrets in a secret manager. Do not log authorization headers, access tokens, signed URLs, or raw data payloads.

## 11. Security, privacy, and responsible attribution

- Enforce case-level authorization on every backend read and write.
- Validate user-supplied artifact references against approved buckets/prefixes; never fetch arbitrary URLs supplied by a caller.
- Use private service networking and authenticated backend-to-service calls.
- Issue short-lived signed URLs only after authorization; avoid placing them in analytics or long-lived logs.
- Set maximum file size, raster dimensions, particle count, simulation duration, and AIS query range.
- Sanitize analyst notes and safely render user-provided text.
- Audit access to sensitive candidate evidence, exports, retries, and cancellations.
- Retain source data and evidence references according to the data license and retention policy.
- Label all scores as heuristic evidence; show missing data, uncertainty, model versions, and timestamps beside results.
- Never describe a high score as confirmation of a spill or legal responsibility.

## 12. Reliability and failure handling

- Use a durable queue for long-running stages and persist state before acknowledging work.
- Make run creation and stage calls idempotent. A duplicate queue delivery must not create duplicate results or advance state twice.
- Retry only transient failures with bounded exponential backoff and jitter. Validation/authentication errors should not be blindly retried.
- Persist the error code, stage, attempt, correlation id, and retryability on failure.
- Preserve completed stage artifacts when a later stage fails and show partial results in the UI.
- Support cancellation as a request; a worker should check cancellation between expensive operations and record the final outcome.
- Move exhausted jobs to a dead-letter path with enough metadata for safe investigation and replay.
- On worker restart, resume from persisted state and verify referenced artifacts before continuing.

## 13. Observability and provenance

Emit structured logs with `case_id`, `run_id`, `correlation_id`, `stage`, `attempt`, outcome, duration, and artifact ids. Do not include raw AIS records or secrets in logs. Propagate the correlation id from browser request through backend, queue, worker, AI services, and audit records.

Track at least:

- API request count, latency, and error rates.
- Queue depth, queue delay, retry count, dead-letter count, and cancellation count.
- Per-stage duration, processing size, model/service version, and failure class.
- Artifact size and object-store read/write failures.
- Environmental coverage and source-data age warnings.
- Fixture-mode completion rate and separately measured scientific evaluation metrics.

For reproducibility, record input checksums, dataset identifiers/timestamps, model and code versions, preprocessing/simulation/scoring configuration, and output checksums in a run manifest.

## 14. Verification plan

Verification is part of the project definition. Keep test data small and deterministic where possible.

- **Unit tests:** state transitions, validators, feature normalization, scoring, URI policies, and error classification.
- **Service contract tests:** valid/invalid Pydantic payloads, headers, response schemas, and stable error codes.
- **Persistence tests:** migrations, foreign keys, idempotency, audit events, and status recovery.
- **Integration tests:** backend-to-service calls, object storage references, queue retries, and partial completion.
- **End-to-end tests:** create case, run fixture pipeline, inspect results, retry a failed stage, cancel a run, and handle no candidates.
- **Frontend accessibility checks:** keyboard navigation, focus handling, contrast, status text, and non-map alternatives.
- **Scientific evaluation:** use labeled or synthetic scenarios; report the dataset and method with metrics. Do not infer production performance from a single demo fixture.

Key acceptance targets:

| Area | Acceptance |
| --- | --- |
| Fixture workflow | Complete from case creation through candidate review on a clean setup. |
| Imagery and geometry | SAR processing works; EO has a sensor-aware path; accepted slick output is valid and has a declared CRS. |
| Characterization | Geometry statistics are returned; age is reported only when validated evidence supports an estimate. |
| Drift | Backward source field and forward forecast are separate, traceable outputs. |
| AIS filtering | Unrelated tracks are filtered; real and synthetic inputs are identified as such. |
| Provenance | Every result links to source artifacts and records code/model/config versions. |
| Explainability | Every candidate score includes component values, weights, and evidence references. |
| Failure states | Invalid input, timeout, retry, partial completion, cancellation, and no-candidate cases are visible and traceable. |
| Security | Unauthorized case access is rejected by the backend; secrets never reach browser payloads/logs. |
| Reproducibility | Same fixture inputs and configuration yield the same manifest and deterministic outputs where supported. |

## 15. Deployment checklist

- Build immutable containers with pinned dependencies and native geospatial library versions.
- Run database migrations as a controlled deployment step.
- Configure separate resource limits: detection may need GPU, hindcast needs memory/CPU, correlation needs data/CPU throughput.
- Keep API and worker scaling independent from AI-service scaling.
- Use readiness probes that verify the service can accept work, not only that its process exists.
- Keep object storage private and enable encryption, lifecycle policy, and backup/retention controls.
- Back up PostgreSQL and test restoration; scientific artifacts should have documented retention and integrity checks.
- Use TLS at public ingress and private networking for internal calls.
- Configure monitoring alerts for queue backlog, repeated stage failures, database availability, and storage errors.
- Deploy a fixture/demo environment separately from any environment with live sensitive data.

## 16. Demo walkthrough

Keep the demonstration under five minutes:

1. Open the case workspace and create a case from the included fixture.
2. Start the run and show the queued/running stage timeline.
3. Open the detected slick polygon and show its sensor, timestamp, area, optional age estimate, and model metadata.
4. Open backward origin and forward forecast layers separately; explain their legends, spill-time interval, and data-quality caveats.
5. Select a ranked candidate and show proximity, trajectory, timing, anomaly, and AIS-gap components with source references.
6. Compare another candidate or show the no-candidate/partial-result behavior.
7. Open the audit timeline and point out the run id, correlation id, source versions, and reproducibility manifest.

Pre-cache fixture artifacts. Make fixture mode visible in the UI so a judge can distinguish demo data from live provider data. Do not switch to screenshots in place of demonstrating the running workflow.

## 17. Definition of complete

The project is ready for a judge-facing demonstration when all of the following are true:

- The frontend creates cases and communicates only with the backend API.
- The FastAPI backend authenticates/authorizes requests, persists cases/runs, and coordinates all three AI services.
- Each service has validation, health checks, stable errors, and fixture behavior.
- Detection returns a valid georeferenced slick result with model metadata.
- Hindcast returns a probability artifact and spill-time window with forcing provenance.
- Correlation returns ranked candidates with complete, traceable evidence components.
- PostgreSQL stores case/run/evidence/audit metadata; object storage holds large scientific files.
- Queue retries, failure states, partial results, and run recovery are represented in the UI and backend.
- Results show source timestamps, quality warnings, model/data/config versions, and correlation ids.
- The map, candidate table, and evidence panel remain synchronized and usable with keyboard navigation.
- A clean checkout can start and complete a deterministic fixture run using documented commands.
- Measured accuracy claims, if any, are tied to named validation data and a repeatable evaluation method.

The next recommended task is Milestone 0 followed immediately by Milestone 1. Keep the fixture workflow working while each scientific service is replaced with a real implementation.
