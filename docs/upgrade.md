# Upgrade and migration procedure

1. Read release notes and review pending dependency changes.
2. Create and verify a fresh backup.
3. Build and test the new image in a non-production environment.
   Set `WEB_IMAGE` to an immutable release tag such as
   `research-workspace-web:1.0.0-<commit>` or to an image digest. Never deploy
   `latest`. Record the currently running image as `PREVIOUS_WEB_IMAGE` before
   continuing.
   PostgreSQL, Caddy and the Dockerfile base are digest-pinned in the repository;
   update those digests deliberately and re-run the complete recovery drill.
4. Inspect migrations:

   ```bash
   docker compose -f compose.yml run --rm web python manage.py showmigrations
   docker compose -f compose.yml run --rm web python manage.py migrate --plan
   ```

5. Deploy:

   ```bash
   ./scripts/deploy.sh
   ```

6. Verify the liveness/readiness endpoints and administrator access.
7. Keep the previous image tag and backup available for rollback.

## Application rollback

If the new schema remains compatible, set `WEB_IMAGE` back to the recorded
`PREVIOUS_WEB_IMAGE` value and run:

```bash
docker compose -f compose.yml pull web
docker compose -f compose.yml up -d --no-build web caddy
./scripts/healthcheck.sh
```

If a migration is not backward compatible, stop Web/Caddy and use the verified
pre-upgrade backup with the guarded restore procedure. Do not run an older
application against a newer incompatible schema.

All future model changes must include committed Django migrations. Migration commands must be safe to rerun.
