# Changelog

## 4.6.0 — Party Support

### Added

- `/support` command for battlefield healing during party combat;
- selection of any wounded or unconscious party member as the healing target;
- support for normal and greater healing potions from the shared inventory;
- revival from zero HP when a potion restores health;
- support actions consume the acting player's turn;
- the final support action of a round triggers the shared enemy phase;
- atomic updates for inventory, party HP, acted-player list, round state, and combat state;
- duplicate-click and missing-item rollback protection;
- `party_support_history` audit table;
- tests for healing, revival, duplicate turns, rollback, and round completion.

### Compatibility

- existing v4.5 party combats automatically support battlefield healing;
- solo inventory healing remains unchanged;
- no new environment variables or database migration commands are required.

## 4.5.0 — Party Combat

### Added

- real multiplayer turns for ordinary combat;
- every living party member acts once per round with their own hero stats;
- enemy phase starts only after all living members have acted;
- enemies select targets from the living party instead of attacking one global hero;
- per-player HP and XP persistence in `party_members`;
- atomic combat-state and party-character updates through `BEGIN IMMEDIATE`;
- duplicate-turn protection for repeated and concurrent button presses;
- party status with acted, waiting, and unconscious markers;
- `party_combat_history` audit table for attacks and spells;
- tests for turn guards, shared enemy phases, Phoenix Feather recovery, persistence, and spell actions.

### Compatibility

- chats without party members keep the existing solo combat rules;
- v4.4 Shield Scroll protects the whole party during an enemy phase;
- v4.4 Phoenix Feather saves the first hero reduced to zero HP;
- existing campaigns, inventories, and active solo combats remain compatible.

## 4.4.0 — Tactical Items

### Added

- `/tactics` command available during an active combat;
- Shield Scroll effect that grants +2 armor class for two enemy phases;
- Phoenix Feather ward that automatically revives the active hero with half maximum HP;
- persistent tactical effects stored inside the existing combat state;
- atomic item activation that consumes inventory and updates combat in one SQLite transaction;
- duplicate-activation protection for repeated or concurrent button presses;
- `combat_item_history` audit table;
- combat status display for active tactical effects;
- tests for persistence, duplicate protection, shield duration, phoenix recovery, and missing items.

### Compatibility

- Shield Scrolls and Phoenix Feathers crafted in v4.3 work immediately;
- existing combats and inventories remain compatible;
- no new environment variables are required.

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
