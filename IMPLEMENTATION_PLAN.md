# Delivery plan

Stage 0 is complete. Stage 1 now provides the private workspace MVP while
preserving the same lightweight deployment architecture.

## Architecture

- One Django monolith using server-rendered templates and a pinned HTMX browser script.
- PostgreSQL as the application database in development and production Compose environments.
- Gunicorn with two workers for the initial 2-core/2-GB target.
- Caddy for HTTPS, reverse proxying, compression, and static-file delivery.
- Three long-running Compose services only: `web`, `db`, and `caddy`.
- Local Docker volumes for PostgreSQL data, collected static assets, and future private media.

## Delivery sequence

1. Create the Django project, split settings, root page, health endpoints, and tests.
2. Add the idempotent administrator initialization command.
3. Add the three-service Docker Compose stack and Caddy configuration.
4. Add environment examples, backup/restore scripts, and deployment/upgrade documentation.
5. Run Django tests, system checks, Compose validation, image build/startup checks when Docker is available, and review the Stage 0 boundary.

## Stage 1 delivered

- Administrator-managed accounts, username/email login, password changes, and
  database-backed login throttling.
- User profiles.
- Seven private research-object types with Markdown rendering and sanitization.
- Personal tags, favorites, archive, soft deletion, autosave, and Markdown export.
- Permission-aware search and protected attachment upload/download.
- Backend ownership filtering for list, detail, edit, export, autosave, search,
  and attachment access.

## Explicitly deferred

Sharing, projects, comments, paper metadata import, object relations, and public
publication snapshots belong to later PRD stages and remain intentionally absent.
