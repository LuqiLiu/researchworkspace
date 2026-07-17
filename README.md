# Research Workspace Lite V1

Private, lightweight research workspace for collecting papers, developing ideas,
recording experiments, connecting research evidence, and publishing selected
work. Stages 0–5 are implemented on one small deployment stack.

## Stack

- Django 5.2 LTS and Django Templates
- HTMX loaded as a pinned browser dependency
- PostgreSQL 17
- Gunicorn
- Caddy
- Docker Compose with exactly three long-running services: `web`, `db`, and `caddy`

## Prerequisites

- Docker Engine with Docker Compose v2+
- A copy of `.env.example` named `.env`

Generate strong values for `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`, and `DJANGO_SUPERUSER_PASSWORD` before any non-local deployment. Do not commit `.env`.

## Local start

```bash
cp .env.example .env
docker compose up --build
```

The automatically loaded `compose.override.yml` runs Django's development server with source code mounted into the container. Open `https://localhost`; Caddy uses its local certificate authority for the localhost certificate, so a browser warning may appear until that authority is trusted.

Useful commands:

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py init_admin
docker compose exec web python manage.py seed_demo --password 'local-demo-password'
docker compose exec web python manage.py test
docker compose down
```

The administrator command reads the `DJANGO_SUPERUSER_*` values from `.env`. It is idempotent and can safely be rerun to update the administrator email, password, and active/staff status.

## Production start

1. Point a DNS record at the server.
2. Copy `.env.example` to `.env` and set `DOMAIN`, secure credentials, allowed hosts, and trusted origins.
3. Set `DJANGO_SECURE_SSL_REDIRECT=true`.
4. Start only the production Compose definition:

```bash
docker compose -f compose.yml up -d --build
docker compose -f compose.yml exec web python manage.py init_admin
docker compose -f compose.yml ps
```

The web entrypoint applies migrations and collects static files before starting Gunicorn. Detailed production notes are in [docs/deployment.md](docs/deployment.md).

## Health checks

- `/health/live/` confirms the Django process is responding.
- `/health/ready/` also performs a database query and returns HTTP 503 if PostgreSQL is unavailable.

Docker uses the readiness endpoint for the `web` service health check.

## Stage 1 workspace

- Administrator-created accounts, username/email login, password changes, and basic login throttling
- User profiles
- Seven research-object types with Markdown source storage
- Private-by-default ownership enforced in queryset and download views
- Personal tags, favorites, archive, soft deletion, Markdown export, and permission-aware search
- Private attachments stored outside Caddy's public static routes

## Stage 2 collaboration

- Direct member sharing with `VIEWER`, `COMMENTER`, and `EDITOR` permissions
- Attachment access remains separately opt-in for every direct share
- Lightweight projects with owner-managed `MEMBER` and `EDITOR` roles
- Project content is visible only when the content owner explicitly enables
  project sharing
- Threaded comments for users with comment permission
- Immediate access revocation for direct shares and project membership
- Security audit records for share, revocation, project-member, and comment
  moderation events

Administrators do not automatically gain application-level access to private
research objects. Private content is also intentionally absent from Django
admin.

## Stage 3 research workflow

- DOI, PDF and arXiv paper import with source/confidence provenance
- A safe fallback that still creates a paper when Crossref is unavailable
- PDF metadata and first-two-page text extraction with `pypdf` (no OCR)
- Duplicate suggestions based on DOI, normalized title, and PDF SHA-256
- BibTeX generation and download
- Owner correction of all core bibliographic fields
- Typed links between papers, ideas, experiments, issues, and other objects
- Expanded permission-aware search across metadata, tags, projects, and comments
- Purpose-built templates for paper, idea, experiment, and issue records

## Interface

The server-rendered UI uses a local research-workspace design system: a compact
navigation rail, responsive mobile navigation, document-like content panels,
and semantic object cards. It intentionally avoids a Node.js build pipeline or
a heavyweight component framework so the three-service deployment remains
small and easy to maintain.

## Stage 4 public profiles

- Opt-in academic profiles at `/u/{public-slug}/`
- Separate publication snapshots that never render live private source content
- Owner-only draft editing, preview, publish, update, and withdrawal controls
- Public paper index, selected-work cards, cover images, and basic SEO metadata
- Explicit attachment rights confirmation and copied public attachment files
- Publish-time checks for likely secrets, credentials, and server paths
- Immediate public URL removal when a snapshot or profile is taken offline

Internal pages default to `noindex,nofollow`. `robots.txt` permits `/u/` while
disallowing the rest of the application, and only explicitly published pages
emit `index,follow` metadata.

## Tests and checks

Tests use an isolated SQLite database so framework checks and unit tests do not require a running PostgreSQL container:

```bash
python -m pip install -e ".[dev]"
python manage.py check --settings=config.settings.test
python manage.py test --settings=config.settings.test
```

Validate the production Compose model:

```bash
docker compose --env-file .env -f compose.yml config
```

## V1 portability and safety

- 512 MiB default per-user attachment quota with atomic accounting
- Personal workspace ZIP, paper CSV/BibTeX, and public-profile ZIP exports
- Optimistic edit locking with explicit HTTP 409 conflict handling
- Field-level bibliographic provenance and manual correction
- Pinned Python dependencies, SRI-protected browser dependencies, and CSP
- Immutable release image naming, documented rollback, guarded format-2 restore
- Audited ownership transfer from a disabled account to an active successor

## Backups, restores, and upgrades

- [docs/backup-restore.md](docs/backup-restore.md)
- [docs/upgrade.md](docs/upgrade.md)
- [docs/admin-operations.md](docs/admin-operations.md)
- [docs/recovery-verification.md](docs/recovery-verification.md)
- `scripts/backup.sh`
- `scripts/restore.sh`
- `scripts/deploy.sh`

Backup archives must be stored outside publicly served directories and copied to a separate machine or storage system.

## Stage 5 operations

- Per-service CPU, memory, process, and graceful-shutdown guardrails
- Docker log rotation and Gunicorn worker recycling
- Machine-readable disk-capacity checks
- Atomic, checksummed daily/weekly backups with retention
- Restore with traffic stopped and an isolated recovery-drill workflow
- Deployment, firewall, restart recovery, incident, and administrator guidance

## Repository layout

```text
app/core/                 Stage 0 health checks and admin bootstrap command
config/settings/          Shared, development, production, and test settings
docker/                   Container entrypoint
docs/                     Deployment, backup/restore, and upgrade guidance
scripts/                  Operational shell scripts
static/                   Source static assets
templates/                Django templates
Caddyfile                 HTTPS and reverse proxy configuration
compose.yml               Production service definition
compose.override.yml      Local development overrides
Dockerfile                Django/Gunicorn image
```

## Resource profile

The production topology is intentionally small:

- 2 Gunicorn workers
- PostgreSQL capped at 30 connections with conservative memory settings
- Caddy as the only public-facing service
- No Redis, Celery, MinIO, Elasticsearch, Kubernetes, local model, or Node.js production runtime
