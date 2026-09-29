# Delta Air Lines — HelpDesk Discord Bot

A professional, branded Discord support bot for Delta Air Lines.  
Built with **discord.py 2.x**, featuring a fully interactive Assistance Panel, private ticket channels, and Delta Air Lines branding throughout.

---

## Features

| Feature | Details |
|---|---|
| Assistance Panel | Support or admins can post the plain-text contact panel or upload custom top and bottom banner images with `/panel`; confirmation continues in DMs |
| Private Tickets | Members stay in DMs while staff work from a hidden relay channel |
| Duplicate Guard | Prevents users from opening multiple simultaneous tickets |
| Close Ticket | Persistent button plus `/ticket control` and `/ticket admin`; DMs the user on close |
| Message Relay | Per-ticket locking suppresses concurrent duplicate events; customer messages and Delta-blue human replies are recorded once |
| Agent Privacy | Customer DMs receive plain reply text; only the private ticket retains the attributed reply embed |
| Ticket Reuse | Repeat creation attempts reconnect the customer to their existing ticket instead of opening a duplicate |
| Staff Commands | `/reply`, `/format`, and claimant-only `/ticket control` are support role-gated |
| Admin Commands | `/ticket admin` consolidates assignment, removal, punishment, close, and undo actions |
| Delta Branding | Red (#C8102E), optional server-owned images, and a consistent footer |
| Claim State | Support can claim and unclaim repeatedly; claim ownership survives bot restarts |
| Transcripts | Closed-ticket transcripts are posted to the private transcript channel |
| Server Logs | Member joins/leaves, message edits/deletions, and moderation changes are sent to the configured logs channel |
| Weekly Audit Digest | Every Sunday at 12:00 a.m. Eastern, posts the complete weekly event totals and recovers a missed report after a restart |
| Lounge AutoMod | Messages matching configurable curse/offensive terms are removed from `#lounge`, with actions recorded in server logs |
| Commands-only Channel | Ordinary member messages are automatically removed from `#bot-commands` |
| Authentication | Admins grant, remove, or check the configured authentication role through one `/authentication-control` command |
| Economy | Persistent Delta Credits with balance, daily, work, pay, and leaderboard commands |
| Server Safety | Commands and tickets are locked to server `1538738611988467782`, but the bot never removes itself from a server |
| Release Updates | Posts and pins the newest release in server logs channel `1539005101941850274`, then removes every older or duplicate update |

Versions use `major.minor.patch`. Breaking or especially large releases increase
the first number, regular feature releases increase the second, and fixes increase
the third.

---

## File Structure

```
bot/
├── main.py          — The only production implementation and entry point
├── config.py        — Single source for version, IDs, roles, and shared settings
├── support_formats.json — Web-editable canned `/format` messages
├── messages.json      — Syntax-safe operational ticket messages
├── delta_bot.py       — Tiny compatibility launcher; contains no bot implementation
├── requirements.txt — Python dependencies
├── .env.example     — Template for required environment variables
└── README.md        — This file
```

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-org/delta-helpdesk-bot.git
cd delta-helpdesk-bot/bot
```

### 2. Create a virtual environment & install dependencies

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env and set DISCORD_TOKEN=your_bot_token_here
```

### 4. Run the bot

```bash
python main.py
```

---

## Discord Developer Portal Setup

1. Go to [discord.com/developers/applications](https://discord.com/developers/applications) and create a new application.
2. Under **Bot**, create a bot user and copy the token into `.env`.
3. Enable **SERVER MEMBERS INTENT** and **MESSAGE CONTENT INTENT** under the *Privileged Gateway Intents* section.
4. Under **OAuth2 → URL Generator**, select:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `View Channels`, `Send Messages`, `Manage Channels`, `Read Message History`, `Embed Links`, `Attach Files`, `Mention Everyone`
5. Use the generated URL to invite the bot to your server.

---

## Slash Commands

| Command | Description | Who Can Use |
|---|---|---|
| `/panel` | Post the private-ticket Assistance Panel in the current channel | DL Leadership only |
| `/reply` | Send plain reply text to the customer and retain the attributed embed in the ticket | Claimant or support member added to that ticket |
| `/format` | Choose one of the prewritten customer notices | Staff only |
| `/ticket control` | Add/remove customers or support and close the current ticket | Staff member who claimed that ticket |
| `/ticket admin` | Run consolidated assignment, removal, punishment, close, or undo actions | Admin only |
| `/version` | Show version, commit, uptime, and Discord latency | Staff only |
| `/authentication-control command: member:` | Authenticate, remove authentication, or check a member | Admin only |
| `/economy balance [member]` | View a Delta Credits balance | Everyone |
| `/economy daily` | Claim a reward every 24 hours | Everyone |
| `/economy work` | Earn credits once per hour | Everyone |
| `/economy pay member: amount:` | Transfer credits safely | Everyone |
| `/economy leaderboard` | Show the ten highest balances | Everyone |

---

## Configuration

All shared production settings live in **`config.py`**. `main.py` imports them;
do not copy version or Discord IDs back into the entry point.

| Constant | Default Value | Purpose |
|---|---|---|
| `GUILD_ID` | `1538738611988467782` | The only authorized Discord server |
| `TICKET_CATEGORY_ID` | `1543674278711529562` | Category for private ticket relay channels |
| `STAFF_ROLE_ID` | `1539005030189891684` | Support/admin role for commands, access, and ticket pings |
| `TRANSCRIPT_CHANNEL_ID` | `1539005101941850274` | Server logs channel that receives closed-ticket transcripts and release notices |
| `LOUNGE_CHANNEL_ID` | `0` | Optional explicit lounge channel ID; `0` finds a text channel named `lounge` |
| `BOT_COMMANDS_CHANNEL_ID` | `0` | Optional commands channel ID; `0` finds a text channel named `bot-commands` |
| `AUTHENTICATED_ROLE_ID` | `0` | Role managed by `/authentication-control` |
| `ECONOMY_DB_PATH` | `bot/economy.db` | Persistent SQLite economy database path |
| `AUDIT_DB_PATH` | `bot/audit.db` | Persistent counters and weekly-report checkpoint |
| `DELTA_RED` | `0xC8102E` | Embed accent colour |

To add a new ticket category, add an entry to `TICKET_CONFIG` in `config.py`.
The production implementation in `main.py` consumes it automatically.

The bot publishes commands only to `GUILD_ID`, clears its former global commands,
and accepts DM tickets only from members of the authorized server. Other guilds
remain inert; the bot never automatically leaves a server.

Lounge AutoMod terms are maintained in `automod_terms.json`. Matching is
case-insensitive and recognizes common number/symbol substitutions. If the server
has more than one channel named `lounge`, set `LOUNGE_CHANNEL_ID` in Raven to the
correct channel ID. The bot requires **Manage Messages** in that channel and
**Send Messages** plus **Embed Links** in the configured logs channel.
The bot also requires **Manage Messages** in `#bot-commands`. Set
`AUTHENTICATED_ROLE_ID` to the role that administrators should manage; the bot's
highest role must be above it in the server role list.

Operational logs use branded Delta embeds for joins, leaves, edits, deletions,
member updates, bans, and AutoMod actions. At Sunday 12:00 a.m. in the
`America/New_York` timezone, the bot posts a weekly digest to
`TRANSCRIPT_CHANNEL_ID`. Daylight-saving changes are handled automatically. Keep
`AUDIT_DB_PATH` on persistent storage so a restart can recover a report that was
temporarily missed.

## DM Ticket Flow

1. DL Leadership posts `/panel`, or a member messages the bot directly.
2. A panel selection immediately opens the ticket and connects the member in DMs; direct DM users choose one category.
3. A staff-only relay channel is created. The member never receives access to it.
4. Each customer DM is copied to that channel and receives a branded delivery confirmation.
5. One support agent claims the ticket. Only that agent can reply until they unclaim it.
6. The claimed agent uses `/reply message:`; ordinary ticket-channel chat remains internal.

---

## Deployment

### Raven Host

Raven must launch the repository-root entry point directly. Configure:

```text
Build Command: python -m pip install -r requirements.txt
Start Command: python bot/main.py
Environment: DISCORD_TOKEN=<the current bot token>
```

No wrapper module is involved: `bot/main.py` ends with `main()` and is the only
production implementation. Persistent ticket buttons and the public Assistance
dropdown are registered during `setup_hook` before commands are synchronized.

At startup, the Raven console reports the version, detected Git branch and commit,
and hosting environment. It then validates the guild, ticket category, logs
channel, staff role, and admin role. Any incorrect configured ID produces a clear
warning without hiding the remaining checks. Assistance dropdown exceptions are
logged with a full traceback, so an “application didn't respond” incident can be
diagnosed in the Raven console.

The release announcement is automatically maintained as a single message. When
`BOT_VERSION` changes, the bot posts and pins the new update before deleting the
previous announcement. Reconnects do not repost the same update, and any older or
duplicate update messages found in the pinned messages or recent log history are
removed.

After deployment, run `/version` as staff to verify the commit, uptime, and Discord
latency. Raven only needs the current `DISCORD_TOKEN`; no entry-point change is
required.

### Render / Railway (alternative hosts)

1. Push your repository to GitHub (make sure `.env` is in `.gitignore`).
2. Create a new **Web Service** (Render) or **Service** (Railway).
3. Set the **Start Command** to: `python bot/main.py`
4. Add the `DISCORD_TOKEN` environment variable in the platform dashboard.

#### Deployment recovery checklist

Use these exact service settings:

```text
Build Command: pip install -r requirements.txt
Start Command: python bot/main.py
Environment: DISCORD_TOKEN=<the current bot token>
```

After merging an update, choose **Manual Deploy → Clear build cache & deploy**.
In the deploy logs, verify both of these lines appear:

```text
Starting Delta Air Lines HelpDesk <version> | branch=<branch> | commit=<commit> | host=<host>.
Synced 8 application command(s) to guild 1538738611988467782.
Delta Air Lines HelpDesk <version> is online | branch=<branch> | commit=<commit> | host=<host>.
```

If the source hash is not the commit you merged, Render is deploying the wrong
branch or an older revision. Set the service branch to `main` before redeploying.
Run `/version` as a support member to verify the release and source from Discord.
You can also open the service's public Render URL; the status page displays the
same version and source revision without requiring Discord access.
If the bot logs in but does not receive DMs or member information, enable
**Server Members Intent** and **Message Content Intent** in Discord Developer
Portal → Applications → the bot → Bot → Privileged Gateway Intents.

The former `PyNaCl is not installed` message only meant Discord voice support
was unavailable; it did not stop ticket commands. PyNaCl is now installed anyway
so that warning no longer distracts from actionable deployment errors. Keep only
one service running with the production `DISCORD_TOKEN`, since two deployments
using the same bot account can process the same customer event independently.

`bot/main.py` is the only production implementation. The historical Python module
paths remain as tiny, implementation-free compatibility shims so modify/delete
conflicts can be handled in GitHub's web editor. Repository validation rejects any
attempt to put a second bot implementation back into those shims or redirect
`main.py` away from `main()`.

If the bot was removed from the authorized server, reinvite the application from
Discord Developer Portal → OAuth2 → URL Generator with the `bot` and
`applications.commands` scopes. After it rejoins, redeploy once so guild commands
sync immediately. The bot deliberately never calls Discord's `guild.leave()` API;
its single-server restriction is enforced by command checks and guild-only sync.

### Replit

The repository-level `.replit`, `requirements.txt`, and `runtime.txt` files are
already configured to install the bot dependencies and start `bot/main.py`.
Add `DISCORD_TOKEN` as a Replit Secret, then redeploy. Do not replace the
deployment command with the TypeScript workspace's build command.

### VPS (systemd)

```ini
# /etc/systemd/system/delta-bot.service
[Unit]
Description=Delta Air Lines HelpDesk Bot
After=network.target

[Service]
WorkingDirectory=/opt/delta-helpdesk-bot/bot
ExecStart=/opt/delta-helpdesk-bot/bot/venv/bin/python main.py
EnvironmentFile=/opt/delta-helpdesk-bot/bot/.env
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now delta-bot
```

---

## Branding Assets

Old-server Discord attachments are not built into the bot. Upload replacement
assets to the authorized server and set `BANNER_URL` and `DIVIDER_URL` to their
new Discord CDN URLs. Both variables are optional.

---

*Delta Air Lines — Keep Climbing*
