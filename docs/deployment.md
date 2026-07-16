# Production deployment

## Host preparation

- Linux host with 2 CPU cores, 2 GB RAM, and 1–2 GB swap.
- Current Docker Engine and Docker Compose plugin.
- DNS `A`/`AAAA` record for the application domain.
- Inbound TCP 80/443 and UDP 443; SSH restricted to key authentication.
- PostgreSQL is not published to the host network.

## Configure

```bash
cp .env.example .env
```

Set at minimum:

- `DOMAIN`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_SECURE_SSL_REDIRECT=true`
- PostgreSQL credentials
- Initial administrator credentials

Use a unique password/secret generator. Protect `.env` with owner-only filesystem permissions.

## Deploy

```bash
docker compose -f compose.yml pull
docker compose -f compose.yml up -d --build
docker compose -f compose.yml exec web python manage.py init_admin
docker compose -f compose.yml ps
```

Caddy obtains and renews public TLS certificates automatically when `DOMAIN` resolves to the host and ports 80/443 are reachable.

## Verify

```bash
docker compose -f compose.yml exec web python manage.py check --deploy
curl --fail https://your-domain.example/health/live/
curl --fail https://your-domain.example/health/ready/
```

Also confirm the database port is not publicly reachable and that a backup can be restored into an empty environment.

## Operations

- Schedule `scripts/backup.sh` with the host's cron.
- Monitor `docker compose -f compose.yml ps` and container logs.
- Configure host-level disk-space alerts.
- Keep base images and Python dependencies updated through the documented upgrade process.

