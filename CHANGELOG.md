# Changelog

## 4.1.0 — Reliability Update

### Added

- consistent SQLite snapshots through the native SQLite Backup API;
- automatic backup on startup;
- configurable backup directory and retention using `BACKUP_DIR` and `BACKUP_KEEP`;
- `/status` command with application version, SQLite integrity check, and database size;
- GitHub Actions CI for Python 3.11 and 3.12.

### Fixed

- synchronized package and project versions with the actual release;
- added Pillow to `pyproject.toml` runtime dependencies;
- ignored generated database backups in Git.

### Configuration

```env
BACKUP_ON_START=true
BACKUP_DIR=data/backups
BACKUP_KEEP=7
```
