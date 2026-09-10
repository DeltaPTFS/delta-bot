"""
config.py — Central configuration for the Delta Air Lines HelpDesk Bot.
All IDs, colours, and branding constants live here.
"""

# ── Branding ──────────────────────────────────────────────────────────────────
DELTA_RED       = 0xC8102E
FOOTER_TEXT     = "Delta Air Lines • Keep Climbing"
MAILING_ADDRESS = "P.O. Box 20980, Department 980, Atlanta, GA 30320-2980"

BANNER_URL = (
    "https://cdn.discordapp.com/attachments/1525901449769254922"
    "/1525992386948239582/delta_banner.jpg"
)
DIVIDER_URL = (
    "https://cdn.discordapp.com/attachments/1525901449769254922"
    "/1525992387254685869/skinny_delta_banner.jpg"
)

# ── Guild / Channel IDs ───────────────────────────────────────────────────────
TICKET_CATEGORY_ID = 1524489811627475075   # All ticket channels live here

# ── Role IDs ─────────────────────────────────────────────────────────────────
STAFF_ROLE_ID           = 1436474227971592325  # May use staff-only commands
GENERAL_SUPPORT_ROLE_ID = 1436480867240251493  # Pinged / given access on General Inquiries tickets

# ── Ticket-category → channel-prefix / role map ───────────────────────────────
# Add extra rows here as new dropdown options are implemented.
TICKET_CONFIG: dict[str, dict] = {
    "general_inquiries": {
        "label":       "General Inquiries",
        "prefix":      "general-support",
        "role_id":     GENERAL_SUPPORT_ROLE_ID,
        "emoji":       "📋",
        "description": "General questions about Delta Air Lines services.",
    },
    "lead_support": {
        "label":       "Lead Support",
        "prefix":      "lead-support",
        "role_id":     STAFF_ROLE_ID,
        "emoji":       "🏅",
        "description": "Escalated issues requiring a lead team member.",
    },
    "partnership_requests": {
        "label":       "Partnership Requests",
        "prefix":      "partnership",
        "role_id":     STAFF_ROLE_ID,
        "emoji":       "🤝",
        "description": "Inquiries regarding business partnerships.",
    },
    "class_purchases": {
        "label":       "Class Purchases",
        "prefix":      "class-purchase",
        "role_id":     STAFF_ROLE_ID,
        "emoji":       "💺",
        "description": "Purchase or upgrade a cabin class.",
    },
    "application_status": {
        "label":       "Application Status",
        "prefix":      "application",
        "role_id":     STAFF_ROLE_ID,
        "emoji":       "📄",
        "description": "Check the status of a submitted application.",
    },
    "jobs_roles": {
        "label":       "Jobs & Roles",
        "prefix":      "jobs",
        "role_id":     STAFF_ROLE_ID,
        "emoji":       "💼",
        "description": "Inquiries about open positions and roles.",
    },
    "bug_reports": {
        "label":       "Bug Reports",
        "prefix":      "bug-report",
        "role_id":     STAFF_ROLE_ID,
        "emoji":       "🐛",
        "description": "Report a bug or technical issue.",
    },
}
