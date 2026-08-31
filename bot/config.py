"""
config.py — Central configuration for the Delta Air Lines HelpDesk Bot.
All IDs, colours, and branding constants live here.
"""

import os

# ── Branding ──────────────────────────────────────────────────────────────────
DELTA_RED       = 0xC8102E
FOOTER_TEXT     = "Delta Air Lines • Keep Climbing"
MAILING_ADDRESS = "P.O. Box 20980, Department 980, Atlanta, GA 30320-2980"

BANNER_URL = os.getenv("BANNER_URL", "")
DIVIDER_URL = os.getenv("DIVIDER_URL", "")

# ── Guild / Channel IDs ───────────────────────────────────────────────────────
GUILD_ID = 1538738611988467782
TICKET_CATEGORY_ID = 1543674278711529562   # All ticket channels live here

# ── Role IDs ─────────────────────────────────────────────────────────────────
STAFF_ROLE_ID           = 1539005030189891684  # May use staff-only commands
ADMIN_ROLE_ID           = 1539005297417519205  # May use ticket administration commands
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
        "role_id":     STAFF_ROLE_ID,
        "emoji":       "<:Nametag:1541175704622993428>",
        "description": "Questions about careers and applications.",
    },
}
