# ✈️ Delta Air Lines — HelpDesk Discord Bot

A professional, branded Discord support bot for Delta Air Lines.  
Built with **discord.py 2.x**, featuring a fully interactive Assistance Panel, private ticket channels, and Delta Air Lines branding throughout.

---

## Features

| Feature | Details |
|---|---|
| Assistance Panel | Sent privately after a member DMs the bot and confirms they want a ticket |
| Private Tickets | Members stay in DMs while staff work from a hidden relay channel |
| Duplicate Guard | Prevents users from opening multiple simultaneous tickets |
| Close Ticket | Button *and* `/close` slash command; DMs the user on close |
| Message Relay | Customer and claimed-agent messages are delivered both ways with ✅ confirmation |
| Deployment Notes | Posts plain-language added, changed, and removed notes from `deployment_notes.json` |
| Staff Commands | `/connected`, `/resolved`, `/hr`, and `/leadership` — staff role-gated |
| Delta Branding | Red (#C8102E), banner/divider images, consistent footer on every embed |
| Claim State | Claim ownership is stored with the ticket and survives bot restarts |

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
| `/close` | Close the current ticket | Staff or Manage Channels |
| `/connected` | Notify the user that an agent has connected | Staff only |
| `/resolved` | Mark the ticket as resolved | Staff only |
| `/hr` | Post the available Human Resources positions | Staff only |
| `/leadership` | Post the available Delta Leadership positions | Staff only |
| `/bot-updates post` | Post an update and notify the Bot Updates role | Staff only |

---

## Configuration

The active single-file bot keeps its IDs and constants in **`main.py`**:

| Constant | Default Value | Purpose |
|---|---|---|
| `TICKET_CATEGORY_ID` | `1524489811627475075` | Discord category for all ticket channels |
| `STAFF_ROLE_ID` | `1436474227971592325` | Role that can run staff-only commands |
| `GENERAL_SUPPORT_ROLE_ID` | `1436480867240251493` | Role pinged on General Inquiries tickets |
| `UPDATES_CHANNEL_ID` | `1532958715592966338` | Channel that receives the latest deployment update |
| `DELTA_RED` | `0xC8102E` | Embed accent colour |

To add a new ticket category, add an entry to the `TICKET_CONFIG` dictionary in `main.py`. The rest of the bot picks it up automatically.

## DM Ticket Flow

1. A member sends the bot a direct message and chooses **Yes, make a ticket**.
2. The bot sends the Assistance Panel in DMs and the member chooses a category.
3. A staff-only relay channel is created. The member never receives access to it.
4. Each customer DM is copied to that channel and receives a ✅ when delivered.
5. One support agent claims the ticket. Only that agent can reply until they unclaim it.
6. Staff replies are copied to the member's DMs and receive a ✅ when delivered.

Before deploying, update **`deployment_notes.json`** with short, plain-language
items under `added`, `changed`, and `removed`. The bot posts those notes once
when the new process connects; it does not post generic online or command-sync
status messages to the updates channel.

Before deploying, update **`deployment_notes.json`** with short, plain-language
items under `added`, `changed`, and `removed`. The bot posts those notes once
when the new process connects; it does not post generic online or command-sync
status messages to the updates channel.

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

| Asset | URL |
|---|---|
| Full Delta banner | `https://cdn.discordapp.com/attachments/1525901449769254922/1525992386948239582/delta_banner.jpg` |
| Skinny divider | `https://cdn.discordapp.com/attachments/1525901449769254922/1525992387254685869/skinny_delta_banner.jpg` |

Both URLs are defined in `config.py` (`BANNER_URL`, `DIVIDER_URL`).

---

*Delta Air Lines — Keep Climbing ✈️*
