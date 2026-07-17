# Production deployment

## Host preparation

Use a Linux host with 2 CPU cores, 2 GB RAM, and 1–2 GB swap. Install a current
Docker Engine and Docker Compose plugin. Point the application domain at the
host before starting Caddy.

Only these public ports are required:

- TCP 22 for key-only SSH, restricted to trusted source addresses where possible
- TCP 80 and 443 for Caddy
- UDP 443 for HTTP/3

PostgreSQL and Gunicorn are connected only to the private Compose network and
must not be published to the host.

Example Ubuntu firewall configuration (review against the host's access path
before enabling it):

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from YOUR_ADMIN_IP to any port 22 proto tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 443/udp
sudo ufw enable
sudo ufw status verbose
```

## Configure

```bash
cp .env.example .env
chmod 600 .env
```

Set a real domain, unique Django and PostgreSQL secrets, trusted origins, and
initial administrator credentials. Set `DJANGO_SECURE_SSL_REDIRECT=true`.
Set `WEB_IMAGE` to a unique release/commit tag (or a registry digest); never use
`latest`. Keep the previous value for rollback.
Increase HSTS gradually after HTTPS is confirmed; enable subdomains or preload
only when every relevant hostname is permanently HTTPS-only.

The default resource guardrails reserve no memory but cap the stack at roughly
1.4 GB: 768 MB for Django, 512 MB for PostgreSQL, and 128 MB for Caddy. CPU caps
sum to two cores. Change them only after observing the host.

## Deploy

Create a verified backup before every upgrade, then run:

```bash
./scripts/deploy.sh
docker compose -f compose.yml exec web python manage.py init_admin
./scripts/healthcheck.sh
```

Caddy obtains and renews the TLS certificate when DNS and ports are correct.

## Verify

```bash
docker compose -f compose.yml exec web python manage.py check --deploy
docker compose -f compose.yml exec web python manage.py check_storage --json
curl --fail https://your-domain.example/health/live/
curl --fail https://your-domain.example/health/ready/
docker compose -f compose.yml ps
docker stats --no-stream
```

Also confirm from another machine that port 5432 is unreachable.

## Service recovery

All three services use `restart: unless-stopped`. Enable Docker at boot and
test a restart during a maintenance window:

```bash
sudo systemctl enable docker
docker compose -f compose.yml restart
./scripts/healthcheck.sh
```

This verifies container recovery; a host reboot test should also be completed
before relying on the server for production work.

## Logging and capacity

Container logs use Docker's `json-file` driver with three 10 MB files per
container by default. Inspect recent errors with:

```bash
docker compose -f compose.yml logs --since 1h web db caddy
```

Schedule `check_storage` and alert on a non-zero exit. The default critical
threshold is 1024 MB free. Docker volumes, backups, and system logs all consume
the same host filesystem unless deliberately placed elsewhere.
