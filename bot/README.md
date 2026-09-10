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
| Close Ticket | Button *and* `/close` slash command; DMs the user on close |
| Message Relay | Per-ticket locking suppresses concurrent duplicate events; customer messages and Delta-blue human replies are recorded once |
| Agent Privacy | Customer DMs identify replies as Delta Air Lines Support; only the private ticket record identifies the agent |
| Ticket Reuse | Repeat creation attempts reconnect the customer to their existing ticket instead of opening a duplicate |
| Staff Commands | `/reply`, `/format`, `/ticket add-customer`, `/ticket add-support`, and `/ticket close` are support role-gated |
| Admin Commands | `/ticket admin remove`, `punish`, `unpunish`, and `undo` are admin role-gated |
| Delta Branding | Red (#C8102E), optional server-owned images, and a consistent footer |
| Claim State | Support can claim and unclaim repeatedly; claim ownership survives bot restarts |
| Transcripts | Closed-ticket transcripts are posted to the private transcript channel |
| Server Safety | Commands and tickets are locked to server `1538738611988467782`, but the bot never removes itself from a server |
| Release Updates | Posts and pins each release once in channel `1543674377953087649`; the current release is `2.1.7` |

Versions use `major.minor.patch`. Breaking or especially large releases increase
the first number, regular feature releases increase the second, and fixes increase
the third.

---

## File Structure

```
bot/
├── main.py          — Entry point; bot class, login, view registration
├── support_formats.json — Web-editable canned `/format` messages
├── config.py        — All IDs, colours, branding constants
├── embeds.py        — Factory functions for every embed
├── views.py         — UI components (Select dropdown, Close button, Panel view)
├── tickets.py       — Ticket close orchestration helper
├── commands.py      — All slash commands + error handler
├── utils.py         — Shared helpers (permission checks, channel creation)
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
| `/close` | Close the current ticket | Support/admin role or ticket creator |
| `/reply` | Send an anonymous branded reply to the claimed ticket customer | Claiming support/admin member |
| `/format` | Choose one of the prewritten customer notices | Staff only |
| `/ticket` | Add people, close tickets, and use role-appropriate administration tools | Staff/admin, depending on subcommand |

---

## Configuration

The active single-file bot keeps its IDs and constants in **`main.py`**:

| Constant | Default Value | Purpose |
|---|---|---|
| `GUILD_ID` | `1538738611988467782` | The only authorized Discord server |
| `TICKET_CATEGORY_ID` | `1543674278711529562` | Category for private ticket relay channels |
| `STAFF_ROLE_ID` | `1539005030189891684` | Support/admin role for commands, access, and ticket pings |
| `TRANSCRIPT_CHANNEL_ID` | `1543674377953087649` | Channel that receives closed-ticket transcripts |
| `DELTA_RED` | `0xC8102E` | Embed accent colour |

To add a new ticket category, add an entry to the `TICKET_CONFIG` dictionary in `main.py`. The rest of the bot picks it up automatically.

The bot publishes commands only to `GUILD_ID`, clears its former global commands,
and accepts DM tickets only from members of the authorized server. Other guilds
remain inert; the bot never automatically leaves a server.

## DM Ticket Flow

1. DL Leadership posts `/panel`, or a member messages the bot directly.
2. A panel selection immediately opens the ticket and connects the member in DMs; direct DM users choose one category.
3. A staff-only relay channel is created. The member never receives access to it.
4. Each customer DM is copied to that channel and receives a branded delivery confirmation.
5. One support agent claims the ticket. Only that agent can reply until they unclaim it.
6. The claimed agent uses `/reply message:`; ordinary ticket-channel chat remains internal.

---

## Deployment

### Render / Railway

1. Push your repository to GitHub (make sure `.env` is in `.gitignore`).
2. Create a new **Web Service** (Render) or **Service** (Railway).
3. Set the **Start Command** to: `python bot/main.py`
4. Add the `DISCORD_TOKEN` environment variable in the platform dashboard.

#### Render recovery checklist

Use these exact service settings:

```text
Build Command: pip install -r requirements.txt
Start Command: python bot/main.py
Environment: DISCORD_TOKEN=<the current bot token>
```

After merging an update, choose **Manual Deploy → Clear build cache & deploy**.
In the deploy logs, verify both of these lines appear:

```text
Starting Delta Air Lines HelpDesk 2.1.7 (source <merged commit>).
Synced 8 application command(s) to guild 1538738611988467782.
Delta Air Lines HelpDesk 2.1.7 is online (source <merged commit>).
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

`bot/main.py` is the only production implementation. The obsolete
`bot/delta_bot.py` copy was removed so the Render start command cannot silently
launch stale behavior again.

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
