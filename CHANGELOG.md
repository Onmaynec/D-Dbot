# Changelog

## 5.0.0 — Adventure Reforged

### Added

- `/equipment` system with personal weapons, armor, trinkets, shop, ownership, equip and unequip actions;
- twelve equipment items across common, rare, and epic tiers;
- physical damage, spell damage, armor class, and guard bonuses from equipped gear;
- `/actions` tactical combat panel;
- risky power attack with `-2` to hit and `+4` damage;
- defensive stance with temporary armor and incoming-damage reduction;
- persistent `combat_choice_history` audit table;
- `/choice` story encounters with three meaningful options and party-wide ability checks;
- gold, loot, and party-damage consequences for story choices;
- persistent active choices and `story_choice_history`;
- `/casino` with coin flip, dice duel, rune slots, shared treasury, and daily stake limit;
- persistent `casino_history`;
- reorganized reply keyboard and clearer inline navigation;
- progress bars, equipment summaries, clearer character cards, and readable enemy cards;
- lossless PNG scene support from `assets/images_hq`;
- one-time migration that enables document-mode PNG delivery for every chat;
- SHA256 manifest and verification script for all sixteen source PNG files;
- PowerShell installer for PNG files downloaded separately;
- release workflow upload of every HQ PNG as an individual GitHub Release asset;
- integration tests for equipment, combat choices, story consequences, casino transactions, and duplicate-safe rewards.

### Changed

- party physical attacks now include equipped weapon damage;
- party spells now accept a separate equipment damage bonus without changing their hit roll;
- enemy attacks calculate armor from gear and defensive stance;
- document image mode sends the original file and a separate formatted message card;
- long photo-mode messages no longer resend the same image for every text chunk;
- `/start` and `/help` were rewritten as a clear onboarding flow;
- the main menu is grouped by character, story, combat, economy, and world systems.

### Reliability

- equipment purchases and wallet updates use `BEGIN IMMEDIATE`;
- equipment cannot be changed during an active battle;
- casino balance checks, stakes, payouts, and history are committed atomically;
- story choices, rewards, party damage, inventory, and history are committed atomically;
- repeated combat callbacks remain protected by per-round action guards;
- old JPG scenes remain available as an automatic fallback;
- existing v4 databases require no manual migration.

## 4.7.0 — Victory Rewards

- automatic party victory bundles with equal completion XP, gold, and shared loot;
- `/rewards` history and idempotent `battle_reward_history` records.

## 4.6.0 — Party Support

- `/support` battlefield healing, revival from zero HP, and atomic potion consumption.

## 4.5.0 — Party Combat

- real multiplayer rounds, individual heroes, shared enemy phases, and duplicate-turn protection.

## 4.4.0 — Tactical Items

- `/tactics`, Shield Scroll, Phoenix Feather, and persistent combat effects.

## 4.3.0 — Forge & Salvage

- `/forge`, crafting recipes, salvage, and automatic GitHub Release publication.

## 4.2.0 — Daily Rewards

- `/daily`, streaks, milestone items, and atomic shared rewards.

## 4.1.0 — Reliability Update

- SQLite backup API, startup backups, `/status`, and Python 3.11/3.12 CI.
