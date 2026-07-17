# Recovery verification record

## 2026-07-17 isolated recovery drill

- Result: passed
- Source backup: `20260717T024056Z`
- Backup format: PostgreSQL plain SQL gzip + media tar gzip
- Integrity checks: all SHA-256 and gzip checks passed before restore
- Isolation: generated Compose project with separate PostgreSQL, static, and
  media volumes; Caddy was not started
- Restored migration rows: 30
- Restored user rows: 2
- Django system check: passed
- Media storage check: passed; restored media size 6,594 bytes
- Cleanup: no drill containers or volumes remained after completion

The production-shaped three-service stack was then restarted. PostgreSQL and
Django returned healthy, Caddy returned to service, and the HTTPS home page
returned HTTP 200. Observed idle memory after restart was approximately 18 MB
for PostgreSQL, 102 MB for Django/Gunicorn, and 12 MB for Caddy.

Configured limits were verified from Docker:

| Service | Memory | CPU | PID limit | Log rotation | Restart policy |
| --- | ---: | ---: | ---: | --- | --- |
| db | 512 MB | 0.65 | 120 | 3 × 10 MB | unless-stopped |
| web | 768 MB | 1.00 | 160 | 3 × 10 MB | unless-stopped |
| caddy | 128 MB | 0.35 | 80 | 3 × 10 MB | unless-stopped |

This development-host exercise verifies container restart recovery. A real
production host reboot remains a mandatory deployment checklist item because
rebooting the user's Windows development machine was intentionally out of
scope.
