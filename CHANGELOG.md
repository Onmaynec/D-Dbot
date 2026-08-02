# Changelog

## 4.3.0 — Forge & Salvage

### Added

- `/forge` command with an inline crafting and salvage interface;
- three recipes built from items already available in the shop and daily rewards;
- deterministic salvage values based on item rarity;
- atomic crafting transactions that consume ingredients and gold together;
- atomic salvage transactions that remove one item and credit the shared treasury;
- persistent `forge_history` audit table for crafted and salvaged items;
- stale-button protection through stable short item codes;
- automated post-CI publication of a version tag and GitHub Release marked as Latest;
- tests for successful crafting, rollback, stack salvage, and invalid callbacks.

### Recipes

- two healing potions + 15 gold → greater healing potion;
- luck scroll + silver arrows + 20 gold → shield scroll;
- two fate tokens + greater healing potion + 80 gold → phoenix feather.

## 4.2.0 — Daily Rewards

### Added

- `/daily` command with an inline daily reward chest;
- party-wide daily streak stored in SQLite;
- deterministic gold rewards with a preview before claiming;
- bonus inventory item every third consecutive day;
- epic `Жетон судьбы` and extra gold every seventh consecutive day;
- atomic reward transaction that updates the claim, wallet, and inventory together;
- protection against duplicate claims from repeated clicks or multiple party members;
- tests for streak continuation, missed-day reset, milestones, and duplicate claims.

### Rules

- one reward is available per chat per UTC calendar day;
- any party member may open the chest, but the reward goes to the shared treasury;
- missing a day resets the active streak to day one;
- total claim history is preserved even after a streak reset.

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
