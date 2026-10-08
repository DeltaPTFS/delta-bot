"""
config.py — Central configuration for the Delta Air Lines HelpDesk Bot.
All IDs, colours, and branding constants live here.
"""

import os

# ── Branding ──────────────────────────────────────────────────────────────────
DELTA_RED       = 0xC8102E
DELTA_BLUE      = 0x003087
FOOTER_TEXT     = "Delta Air Lines • Keep Climbing"
MAILING_ADDRESS = "P.O. Box 20980, Department 980, Atlanta, GA 30320-2980"

DIVIDER_URL = os.getenv("DIVIDER_URL", "")

# ── Guild / Channel IDs ───────────────────────────────────────────────────────
GUILD_ID = 1538738611988467782
TICKET_CATEGORY_ID = 1543674278711529562   # All ticket channels live here
TRANSCRIPT_CHANNEL_ID = 1539005101941850274
UPDATE_CHANNEL_ID = TRANSCRIPT_CHANNEL_ID
LOUNGE_CHANNEL_ID = int(os.getenv("LOUNGE_CHANNEL_ID", "0"))
BOT_VERSION = "2.6.6"

# ── Runtime behavior ─────────────────────────────────────────────────────────
TICKET_CLOSE_DELAY = 5
RATING_TIMEOUT = 15 * 24 * 60 * 60
DISCORD_RECONNECT_DELAY = 15
DM_TICKET_OWNER_MARKER = "Delta DM Ticket Owner:"
DM_TICKET_CATEGORY_MARKER = "Delta Ticket Category:"
DM_TICKET_CLAIM_MARKER = "Delta Ticket Claimed By:"
DM_TICKET_SUPPORT_MARKER = "Delta Ticket Support:"
INVITE_URL = "https://discord.gg/hccQX6nGJw"

# ── Server emoji ─────────────────────────────────────────────────────────────
SUPPORT_EMOJI = "<:Support:1540927430179553321>"
RIGHT_ARROW_EMOJI = "<:RArrow:1540951788889575504>"
BLUE_ARROW_EMOJI = "<:BArrow:1540951845147639809>"
WING_PIN_EMOJI = "<:WingPinLogo:1540927847709802607>"
MESSAGE_EMOJI = "<:Message:1544506028752769134>"
IDENTIFICATION_EMOJI = "<:Identification:1544505969575198821>"
CHECKMARK_EMOJI = "<:CheckMark:1544505870904459264>"

# ── Role IDs ─────────────────────────────────────────────────────────────────
STAFF_ROLE_ID           = 1539005030189891684  # May use staff-only commands
ADMIN_ROLE_ID           = 1539005297417519205  # May use ticket administration commands
# Role granted and removed by /authentication-control. Keeping this configurable
# avoids baking a server role into the bot when authentication roles are replaced.
AUTHENTICATED_ROLE_ID   = int(os.getenv("AUTHENTICATED_ROLE_ID", "0"))
GENERAL_SUPPORT_ROLE_ID = STAFF_ROLE_ID

# ── Ticket-category → channel-prefix / role map ───────────────────────────────
# Add extra rows here as new dropdown options are implemented.
TICKET_CONFIG: dict[str, dict] = {
    "general_inquiries": {
        "label":       "General Inquires",
        "prefix":      "general-support",
        "role_id":     GENERAL_SUPPORT_ROLE_ID,
        "emoji":       "<:Plane:1540926994332651580>",
        "description": "General questions about Delta Air Lines services.",
    },
    "skymiles": {
        "label":       "SkyMiles",
        "prefix":      "skymiles",
        "role_id":     STAFF_ROLE_ID,
        "emoji":       "<:CreditCard:1540927195357253702>",
        "description": "Questions about SkyMiles accounts and benefits.",
    },
    "partnership_requests": {
        "label":       "Partner Request",
        "prefix":      "partnership",
        "role_id":     STAFF_ROLE_ID,
        "emoji":       "<:Partners:1540927071822549114>",
        "description": "Inquiries regarding business partnerships.",
    },
    "careers": {
        "label":       "Careers",
        "prefix":      "careers",
        "role_id":     ADMIN_ROLE_ID,
        "emoji":       "<:Nametag:1541175704622993428>",
        "description": "Questions about careers and applications.",
    },
}

# ── Runtime extension patches ────────────────────────────────────────────────
try:
    # Load the deployment guard before ticket log filters so release updates are
    # never swallowed by ticket-only server log filtering.
    import deployment_update_guard  # noqa: F401
    import runtime_ticket_controls  # noqa: F401
    import presence_status  # noqa: F401
except Exception:
    # The main bot should continue starting even if an optional runtime patch fails.
    pass
