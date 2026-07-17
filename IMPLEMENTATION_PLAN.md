# Delivery plan

Stages 0–5 are complete. The application now provides a private research
workspace, selective collaboration, a paper-centred research workflow, and
opt-in public academic profiles while preserving the same lightweight
deployment architecture.

## Architecture

- One Django monolith using server-rendered templates and HTMX.
- PostgreSQL in development and production Compose environments.
- Gunicorn with two workers for the initial 2-core/2-GB target.
- Caddy for HTTPS, reverse proxying, compression, and static-file delivery.
- Three long-running services only: `web`, `db`, and `caddy`.
- Private media remains outside publicly served static paths.

## Stage 0 delivered

- Split Django settings, root page, liveness/readiness endpoints, and tests.
- Idempotent administrator initialization.
- Three-service Docker Compose stack and Caddy configuration.
- Deployment, backup/restore, and upgrade documentation.

## Stage 1 delivered

- Administrator-managed accounts, username/email login, password changes, and
  database-backed login throttling.
- User profiles and seven private research-object types.
- Markdown rendering and sanitization, personal tags, favorites, archive,
  soft deletion, autosave, and export.
- Permission-aware search and protected attachment upload/download.

## Stage 2 delivered

- Direct sharing with viewer, commenter, and editor permission levels.
- Lightweight projects with member/editor roles and explicit object sharing.
- Independent attachment permissions and threaded comments.
- Centralized permission checks and immediate access revocation.
- Security audit records and a permission-matrix test suite.

## Stage 3 delivered

- DOI/PDF paper import, Crossref enrichment, local fallbacks, and BibTeX.
- Metadata and limited PDF text extraction without OCR.
- DOI, title, and file-hash duplicate suggestions.
- Typed, permission-filtered relations between research objects.
- Search indexing for structured metadata and expanded live search coverage.
- Purpose-built forms for papers, ideas, experiments, and issues.
- A responsive, research-focused visual system built with local templates and
  CSS, without adding a Node.js production runtime.

## Stage 4 delivered

- Extended academic profiles with avatar, affiliation, position, research
  interests, scholarly links, and an explicit public enable switch.
- Independent publication snapshots with owner-only edit and preview flows.
- Publish, update, and withdrawal controls with audit records.
- Public profile, publication index, and individual note URLs under `/u/`.
- Metadata whitelisting that excludes comments, shares, private tags, private
  BibTeX notes, and unsafe external links.
- Explicit attachment rights confirmation and storage-level copies for public
  downloads; private attachment paths are never exposed.
- Publish-time checks for common secret, credential, and server-path patterns.
- Basic canonical, Open Graph, robots, and search-indexing controls.

## Stage 5 delivered

- CPU, memory, PID, graceful-shutdown, and log-rotation guardrails for all three
  long-running services.
- Gunicorn request recycling and a machine-readable media-volume capacity check.
- Atomic backups with gzip/SHA-256 verification and daily/weekly retention.
- Restore with Web/Caddy stopped, post-restore migration/check, and audit events.
- A disposable Compose recovery drill that uses isolated database/media volumes.
- Expanded deployment, firewall, restart, backup, incident, and administrator
  documentation.

## Next candidate scope

- Operate the V1 with real users and collect maintenance feedback.
- Add capabilities only when observed use demonstrates a concrete need.
