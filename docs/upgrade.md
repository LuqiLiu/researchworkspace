# Upgrade and migration procedure

1. Read release notes and review pending dependency changes.
2. Create and verify a fresh backup.
3. Build and test the new image in a non-production environment.
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

All future model changes must include committed Django migrations. Migration commands must be safe to rerun.

