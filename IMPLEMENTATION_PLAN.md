# Stage 0 implementation plan

This repository implements only PRD Stage 0: the deployable project skeleton.

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

## Explicitly deferred

Research objects, profiles, tags, attachments, search, sharing, projects, comments, imports, and public publication snapshots belong to later PRD stages and are intentionally absent.

