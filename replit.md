# Delta Air Lines HelpDesk Discord Bot

A professional Delta Air Lines branded Discord support bot built with discord.py 2.x.

## Run & Operate

```bash
cd bot
pip install -r requirements.txt
cp .env.example .env   # then fill in DISCORD_TOKEN
python main.py
```

## Stack

- Python 3.10+, discord.py 2.3.2
- python-dotenv for environment variable loading

## Where Things Live

```
bot/
├── main.py            — Only production implementation and direct entry point
├── config.py          — Version, Discord IDs, colours, and shared settings
├── support_formats.json — Validated `/format` content
├── messages.json      — Validated operational messages
└── delta_bot.py       — Implementation-free compatibility launcher only
```

## Architecture Decisions

- **Persistent views** (`timeout=None` + `add_view` in `setup_hook`) so buttons/dropdowns survive bot restarts.
- **Ticket ownership stored in channel topic** (user ID string) — no database needed.
- **`config.py` as single source of truth** for all IDs; adding a new ticket category only requires a new entry in `TICKET_CONFIG`.
- **Staff-only commands guarded** with `app_commands.check` using `STAFF_ROLE_ID`.
- **Ephemeral staff confirmations** — staff see "Message sent successfully", users see the full branded embed.
- **Single production entry point** — Raven, Replit, and local runs all execute `bot/main.py`; compatibility paths contain no alternate bot implementation.

## User Preferences

- All IDs and branding live in `config.py` for easy updates.
- New ticket categories: add a row to `TICKET_CONFIG` in `config.py` — no other file changes needed.

## Gotchas

- Run `python main.py` from inside the `bot/` directory.
- The bot needs **Server Members Intent** enabled in the Discord Developer Portal.
- Slash commands can take up to 1 hour to propagate globally after first sync. Use guild-scoped sync during development (see comment in `main.py`).
- `DISCORD_TOKEN` must be set in `.env` (copy `.env.example`).
- Raven Host must use `python bot/main.py` as its start command from the repository root.
