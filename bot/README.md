# ✈️ Delta Air Lines — HelpDesk Discord Bot

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
| Message Relay | Customer and claimed-agent messages are delivered both ways with ✅ confirmation |
| Agent Privacy | Customer DMs identify replies as Delta Air Lines Support and never expose the individual agent's name |
| Ticket Reuse | Repeat creation attempts reconnect the customer to their existing ticket instead of opening a duplicate |
| Staff Commands | `/ticket add-customer`, `/ticket add-support`, `/ticket close`, `/connected`, and `/resolved` are support role-gated |
| Admin Commands | `/ticket admin remove`, `punish`, `unpunish`, and `undo` are admin role-gated |
| Delta Branding | Red (#C8102E), optional server-owned images, and a consistent footer |
| Claim State | Claim ownership is stored with the ticket and survives bot restarts |
| Transcripts | Closed-ticket transcripts are posted to the private transcript channel |
| Server Migration | Cleans the bot's messages from retired server `1436471549703094477`, then leaves it |
| Release Updates | Posts and pins each release once in channel `1543674377953087649`; the current release is `2.0.2` |

Versions use `major.minor.patch`. Breaking or especially large releases increase
the first number, regular feature releases increase the second, and fixes increase
the third.

---

## File Structure

```
bot/
├── main.py          — Entry point; bot class, login, view registration
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
| `/connected` | Notify the user that an agent has connected | Staff only |
| `/resolved` | Mark the ticket as resolved | Staff only |
| `/hr` | Post the available Human Resources positions | Staff only |
| `/leadership` | Post the available Delta Leadership positions | Staff only |

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

The bot publishes commands only to `GUILD_ID`, clears its former global commands, leaves other servers, and accepts DM tickets only from members of the authorized server.

## DM Ticket Flow

1. DL Leadership posts `/panel`, or a member messages the bot directly.
2. A panel selection sends a private confirmation to the member's DMs; direct DM users choose a category there.
3. A staff-only relay channel is created. The member never receives access to it.
4. Each customer DM is copied to that channel and receives a ✅ when delivered.
5. One support agent claims the ticket. Only that agent can reply until they unclaim it.
6. Staff replies are copied to the member's DMs and receive a ✅ when delivered.

---

## Deployment

### Render / Railway

1. Push your repository to GitHub (make sure `.env` is in `.gitignore`).
2. Create a new **Web Service** (Render) or **Service** (Railway).
3. Set the **Start Command** to: `python bot/main.py`
4. Add the `DISCORD_TOKEN` environment variable in the platform dashboard.

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

*Delta Air Lines — Keep Climbing ✈️*
