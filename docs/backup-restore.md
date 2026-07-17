# Backup and restore

Backups include PostgreSQL and the private media volume. Collected static files
are reproducible and are not backed up.

## Create and verify

Run from the repository root:

```bash
./scripts/backup.sh
```

For an alternate environment file or destination:

```bash
COMPOSE_ENV_FILE=.env BACKUP_ROOT=/srv/research-backups ./scripts/backup.sh
```

Each backup contains:

- `database.sql.gz`
- `media.tar.gz`
- `manifest.txt`
- `SHA256SUMS`

The V1 format-2 manifest identifies both the source Compose project and
database, plus the creation time, Compose file and Git revision. Restore
refuses legacy or unidentified manifests; create a fresh V1 backup before a
production upgrade.

The script writes to a partial directory, checks both gzip streams, writes
SHA-256 checksums, and only then publishes the backup directory. It keeps seven
daily and four weekly copies by default. Weekly entries use hard links when the
backup filesystem supports them.

Keep backups outside Caddy paths and Docker volumes, copy them to encrypted
off-host storage, and monitor backup command failures. Use `DAILY_RETENTION` and
`WEEKLY_RETENTION` to change the local retention counts.

## Restore

Restore is intentionally destructive to the selected Compose project. It first
verifies checksums, stops Web traffic, restores the database schema and media,
runs migrations, performs an application check, and records an audit event.

```bash
export COMPOSE_PROJECT_NAME=research_workspace
./scripts/restore.sh ./backups/daily/20260717T120000Z --dry-run research_workspace
./scripts/restore.sh ./backups/daily/20260717T120000Z --yes research_workspace
./scripts/healthcheck.sh
```

Do not run restore against production while users are active. Confirm the
Compose project name, manifest project/database and backup timestamp before
typing `--yes`. The command refuses a missing or mismatched identity. Only the
isolated recovery drill enables the explicit cross-project restore override.

## Isolated recovery drill

The drill restores into a generated Compose project with new database and media
volumes. It never starts Caddy, so it does not bind production ports:

```bash
COMPOSE_ENV_FILE=.env ./scripts/recovery-drill.sh \
  ./backups/daily/20260717T120000Z
```

The script verifies Django, storage, migration rows, and user rows, writes a
small report under `backups/`, and deletes the isolated volumes on completion.
Set `KEEP_RECOVERY_ENV=true` only when an administrator needs to inspect a
failed drill manually.

A backup is not valid until this drill has succeeded. Run it after material
schema/storage changes and at least quarterly.
