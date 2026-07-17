# Administrator operations guide

## Privacy boundary

Django administrators manage accounts and system state. They do not gain
application access to private research objects, and private research objects
are not registered in Django admin. Database/server administrators remain
technically capable of accessing stored data; users must be told this clearly.

## Accounts

- Create users in `/admin/auth/user/add/`; self-registration remains disabled.
- Set a temporary password in Django admin and require the user to change it.
- Clear `is_active` to stop login immediately.
- A disabled user's public profile remains online only while its profile has
  `public_enabled` selected. Clear that field to take it offline.
- Do not make routine users staff or superusers.
- Run `python manage.py init_admin` only for the designated system account; the
  command resets that account's password from the supplied environment value.
- `python manage.py seed_demo --password ...` creates an ordinary, private,
  idempotent demo workspace. Use it only for local training, never as a shared
  production credential.

## Daily checks

```bash
./scripts/healthcheck.sh
docker compose -f compose.yml logs --since 24h web db caddy
```

Investigate unhealthy containers, repeated authentication failures, disk
warnings, migration errors, and backup failures. Do not use private content
counts or reading activity as performance metrics.

## Backups

- Run a database/media backup daily.
- Keep at least seven daily and four weekly copies.
- Copy backups to separate encrypted storage.
- Run the isolated recovery drill after schema changes and quarterly.
- Record the drill result and investigate any checksum or restore failure.

Example cron entries:

```cron
17 02 * * * cd /opt/research-workspace && BACKUP_ROOT=/srv/research-backups ./scripts/backup.sh >> /var/log/research-backup.log 2>&1
*/15 * * * * cd /opt/research-workspace && ./scripts/healthcheck.sh >> /var/log/research-health.log 2>&1
```

Configure the host monitoring system to alert on non-zero exits and on low
space in the filesystem holding Docker volumes and backups.

## Update procedure

1. Notify users of the maintenance window.
2. Create and verify a fresh backup.
3. Review migrations with `python manage.py migrate --plan`.
4. Run `scripts/deploy.sh`.
5. Verify health endpoints, login, a private attachment, and a public snapshot.
6. Keep the previous image and backup until the new version has been observed.

## Incident response

- Suspected secret publication: withdraw the snapshot, rotate the secret, then
  review publication audit events.
- Copyright complaint: withdraw the snapshot or public attachment immediately;
  the private source remains private.
- Low disk: stop large uploads, move verified backups off-host, inspect Docker
  usage, and expand storage before deleting recoverable data.
- Database corruption or accidental deletion: stop Web/Caddy and restore only
  from a checksum-verified backup.
- Lost administrator password: run `init_admin` from a trusted server shell with
  a new strong password; never place the password in Git or shell history.
