"""
Delta Air Lines HelpDesk Discord Bot — production entry point.
Runtime behavior lives here; shared settings live in config.py.

Usage:
    python main.py

Requires a .env file with:
    DISCORD_TOKEN=your_bot_token_here
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import threading
import time
import unicodedata
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

from config import (
    ADMIN_ROLE_ID,
    BLUE_ARROW_EMOJI,
    BOT_VERSION,
    CHECKMARK_EMOJI,
    DELTA_BLUE,
    DELTA_RED,
    DISCORD_RECONNECT_DELAY,
    DIVIDER_URL,
    DM_TICKET_CATEGORY_MARKER,
    DM_TICKET_CLAIM_MARKER,
    DM_TICKET_OWNER_MARKER,
    DM_TICKET_SUPPORT_MARKER,
    FOOTER_TEXT,
    GUILD_ID,
    IDENTIFICATION_EMOJI,
    INVITE_URL,
    MAILING_ADDRESS,
    MESSAGE_EMOJI,
    RATING_TIMEOUT,
    RIGHT_ARROW_EMOJI,
    STAFF_ROLE_ID,
    SUPPORT_EMOJI,
    TICKET_CATEGORY_ID,
    TICKET_CLOSE_DELAY,
    TICKET_CONFIG,
    TRANSCRIPT_CHANNEL_ID,
    UPDATE_CHANNEL_ID,
    WING_PIN_EMOJI,
)

# ════════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════════

# Backward-compatible name used by earlier command permission checks.
BOT_COMMAND_ROLE_ID     = STAFF_ROLE_ID
# Updated from the authorized server's custom emoji collection in on_ready.
XMARK_EMOJI                = "❌"

# Serializes history-check-and-send operations within each ticket. Without this,
# two concurrent gateway deliveries can both check history before either copy is
# posted and then create duplicate embeds.
CUSTOMER_RELAY_LOCKS: dict[int, asyncio.Lock] = {}

PANEL_MESSAGE = """## <:DeltaLogo:1540927958116601980> Contact Us | <:SkyTeamLogo:1540927923618316359>
-# <:Blank:1540951736062312529> <:Connection:1540927881683669013>  1021 N Outer Loop Rd, East Point, GA, 30344.

> <:BArrow:1540951845147639809> **Have a question about our airline?** Or interested in **joining our team?** Contact Us and our **Delta Support Team** will offer **24/7 Customer Assistance,** ready to answer and solve **any Inquiry** you may have.

> <:RArrow:1540951788889575504> **Before you begin,** please ensure your **Discord Settings** allow **Direct-Messages** from this **server.**

-# <:WingPinLogo:1540927847709802607> **Keep Climbing, Delta Air Lines.**

<:Support:1540927430179553321> **Select an Assistance Category**"""

SUPPORT_FORMATS_PATH = Path(__file__).with_name("support_formats.json")
with SUPPORT_FORMATS_PATH.open(encoding="utf-8") as format_file:
    # Resolve the standard-library loader at this exact use site. This keeps a
    # web conflict resolution from accidentally dropping a distant import and
    # producing a startup-time ``NameError: json is not defined`` on Render.
    _SUPPORT_FORMAT_DATA: dict[str, dict[str, str]] = __import__("json").load(format_file)

SUPPORT_FORMAT_LABELS: dict[str, str] = {
    key: value["label"] for key, value in _SUPPORT_FORMAT_DATA.items()
}
SUPPORT_FORMATS: dict[str, str] = {
    key: value["message"] for key, value in _SUPPORT_FORMAT_DATA.items()
}
CONNECTED_MESSAGE = SUPPORT_FORMATS["connected"]

MESSAGES_PATH = Path(__file__).with_name("messages.json")
with MESSAGES_PATH.open(encoding="utf-8") as messages_file:
    _MESSAGES: dict[str, str] = __import__("json").load(messages_file)
TICKET_CLAIMED_MESSAGE = _MESSAGES["ticket_claimed"]

AUTOMOD_TERMS_PATH = Path(__file__).with_name("automod_terms.json")
with AUTOMOD_TERMS_PATH.open(encoding="utf-8") as automod_file:
    AUTOMOD_TERMS: tuple[str, ...] = tuple(__import__("json").load(automod_file))

NON_MEMBER_MESSAGE = """# <:DeltaLogo:1540927958116601980> Delta Air Lines | Direct Messages <:SkyTeamLogo:1540927923618316359>

> <:BArrow:1540951845147639809> **Hey there! It looks like you're currently not in the Delta Air Lines server.**

If you'd like to join our community, click the **Join Delta Air Lines** button below to get started!

<:Support:1540927430179553321> **Need Assistance?**
If you'd like to contact our team or create a support ticket, click the **Create Ticket** button below.

<:WingPinLogo:1540927847709802607> **Keep Climbing, Delta Air Lines.**"""

UPDATE_MESSAGE = f"""# <:DeltaLogo:1540927958116601980> Delta Support Bot — Update {BOT_VERSION}

This update improves deployment stability without changing the ticket workflow.

## What's Changed
- `bot/main.py` is now the only production HelpDesk implementation.
- Configuration and the version now have one source of truth.
- Startup logs show the version, Git branch, commit, and detected host.
- Startup validates the configured guild, ticket category, logs channel, and roles.
- `/version` now includes uptime and Discord latency for support staff.
- Assistance dropdown failures now print full exception details to the host console.
- Leadership and HR `/format` options now include their complete application requirements.
- Added support members can use `/reply`, and ticket actions are consolidated under
  `/ticket control` and `/ticket admin`.
- Customer `/reply` deliveries are plain text; the attributed embed remains only in
  the private support ticket.

-# Version format: major.minor.patch."""

# ════════════════════════════════════════════════════════════════════════════════
# EMBEDS
# ════════════════════════════════════════════════════════════════════════════════

def _base_embed(title: str = "", description: str = "") -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=DELTA_RED)
    embed.set_footer(text=FOOTER_TEXT)
    return embed


def _set_brand_image(embed: discord.Embed, url: str) -> None:
    if url:
        embed.set_image(url=url)


def general_inquiries_welcome(member: discord.Member) -> discord.Embed:
    embed = _base_embed(
        title="<:Support:1540927430179553321>  General Inquiries | Support Ticket",
        description=(
            f"Welcome, {member.mention}! Thank you for reaching out to "
            "**Delta Air Lines Support**.\n\n"
            "A member of our General Support team has been notified and will "
            "be with you shortly.\n\n"
            "**Please provide as much detail as possible:**\n"
            "• Describe your question or concern clearly.\n"
            "• Attach any relevant screenshots, videos, or documents.\n"
            "• Include booking references, dates, or flight numbers if applicable.\n\n"
            "The more information you share, the faster our team can assist you."
        ),
    )
    embed.add_field(name="<:Connection:1540927881683669013> Mailing Address", value=MAILING_ADDRESS, inline=False)
    _set_brand_image(embed, DIVIDER_URL)
    return embed


def generic_ticket_welcome(member: discord.Member, label: str, emoji: str) -> discord.Embed:
    embed = _base_embed(
        title=f"{emoji}  {label} | Support Ticket",
        description=(
            f"Welcome, {member.mention}! Thank you for contacting "
            "**Delta Air Lines Support**.\n\n"
            "A member of our team will be with you shortly. "
            "Please describe your request in as much detail as possible "
            "and attach any supporting files.\n\n"
            "*We appreciate your patience and thank you for flying Delta.*"
        ),
    )
    embed.add_field(name="<:Connection:1540927881683669013> Mailing Address", value=MAILING_ADDRESS, inline=False)
    _set_brand_image(embed, DIVIDER_URL)
    return embed


def ticket_closed_dm(ticket_name: str) -> discord.Embed:
    embed = _base_embed(
        title=f"{CHECKMARK_EMOJI}  Ticket Closed",
        description=(
            f"Your support ticket **#{ticket_name}** has been successfully closed.\n\n"
            "Thank you for contacting **Delta Air Lines Support**. "
            "We hope we were able to assist you today. "
            "If you need further assistance, please don't hesitate to open a new ticket.\n\n"
            "*Delta Air Lines — Keep Climbing.*"
        ),
    )
    embed.add_field(name="<:Connection:1540927881683669013> Mailing Address", value=MAILING_ADDRESS, inline=False)
    _set_brand_image(embed, DIVIDER_URL)
    return embed


def ticket_closed_channel() -> discord.Embed:
    embed = _base_embed(
        title=f"{CHECKMARK_EMOJI}  Ticket Closing",
        description=f"This ticket has been marked as **closed** and will be deleted in **{TICKET_CLOSE_DELAY} seconds**.\n\nThank you for contacting Delta Air Lines Support.",
    )
    _set_brand_image(embed, DIVIDER_URL)
    return embed


def already_open_ticket(channel: discord.TextChannel) -> discord.Embed:
    embed = _base_embed(
        title="<:RArrow:1540951788889575504>  Active Ticket Found",
        description=(
            f"You already have an open support ticket: {channel.mention}\n\n"
            "Please continue your conversation there. "
            "If you believe this is an error, contact a staff member."
        ),
    )
    return embed


def error_embed(message: str) -> discord.Embed:
    embed = discord.Embed(title=f"{XMARK_EMOJI}  Error", description=message, color=DELTA_RED)
    embed.set_footer(text=FOOTER_TEXT)
    return embed


def success_embed(message: str) -> discord.Embed:
    embed = discord.Embed(title=f"{CHECKMARK_EMOJI}  Success", description=message, color=DELTA_RED)
    embed.set_footer(text=FOOTER_TEXT)
    return embed


def connected_embed() -> discord.Embed:
    """Customer-facing connection notice used only when a ticket is opened."""
    return _base_embed(description=CONNECTED_MESSAGE)


def support_format_embed(format_key: str) -> discord.Embed:
    """Build one of the customer-safe canned support notices."""
    try:
        message = SUPPORT_FORMATS[format_key]
    except KeyError as exc:
        raise ValueError(f"Unknown support format: {format_key}") from exc
    return _base_embed(description=message)


# ════════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ════════════════════════════════════════════════════════════════════════════════

def is_staff(member: discord.Member) -> bool:
    return any(role.id == BOT_COMMAND_ROLE_ID for role in member.roles)


def is_admin(member: discord.Member) -> bool:
    return any(role.id == ADMIN_ROLE_ID for role in member.roles)


def delta_status_emoji(guild: discord.Guild | None, success: bool) -> str:
    """Resolve the server's Delta check/X emoji, with branded arrow fallbacks."""
    if success:
        return CHECKMARK_EMOJI
    preferred_names = (
        "deltax",
        "deltaxmark",
        "xmark",
        "crossmark",
        "x",
        "deltacross",
        "cross",
    )
    if guild is not None:
        emojis = {emoji.name.casefold(): emoji for emoji in guild.emojis}
        for name in preferred_names:
            if emoji := emojis.get(name):
                return str(emoji)
    return XMARK_EMOJI


def _git_output(*args: str) -> str | None:
    """Read local Git metadata without making startup depend on Git being present."""
    try:
        result = subprocess.run(
            ("git", *args),
            cwd=Path(__file__).resolve().parents[1],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None


def deployed_source() -> str:
    """Return the deployed commit SHA, or the clean fallback ``unknown``."""
    value = next(
        (
            os.getenv(name)
            for name in (
                "RAVEN_GIT_COMMIT",
                "RENDER_GIT_COMMIT",
                "RAILWAY_GIT_COMMIT_SHA",
                "GITHUB_SHA",
                "COMMIT_SHA",
            )
            if os.getenv(name)
        ),
        None,
    )
    return (value or _git_output("rev-parse", "HEAD") or "unknown")[:12]


def deployed_branch() -> str:
    """Return the deployment branch when provided by the host or local Git."""
    value = next(
        (
            os.getenv(name)
            for name in (
                "RAVEN_GIT_BRANCH",
                "RENDER_GIT_BRANCH",
                "RAILWAY_GIT_BRANCH",
                "GITHUB_REF_NAME",
                "BRANCH_NAME",
            )
            if os.getenv(name)
        ),
        None,
    )
    return value or _git_output("branch", "--show-current") or "unknown"


def hosting_environment() -> str:
    """Identify common deployment hosts from their environment variables."""
    if any(name.startswith("RAVEN_") for name in os.environ) or os.getenv("RAVEN_HOST"):
        return "Raven Host"
    if os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID"):
        return "Render"
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_PROJECT_ID"):
        return "Railway"
    if os.getenv("REPL_ID") or os.getenv("REPL_SLUG"):
        return "Replit"
    if os.getenv("GITHUB_ACTIONS"):
        return "GitHub Actions"
    return "unknown"


def format_uptime(seconds: float) -> str:
    """Format a monotonic duration for the staff status command."""
    total = max(0, int(seconds))
    days, remainder = divmod(total, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def get_ticket_owner_id(channel: discord.TextChannel) -> int | None:
    """Return the ticket creator stored in the channel topic."""
    topic = channel.topic or ""
    owner_id = get_topic_value(topic, DM_TICKET_OWNER_MARKER)
    if owner_id is not None and owner_id.isdigit():
        return int(owner_id)

    # Retain compatibility with older ticket topics that only stored the owner ID.
    for part in topic.split():
        if part.isdigit():
            return int(part)
    return None


async def find_existing_ticket(
    guild: discord.Guild,
    user: discord.abc.User,
) -> discord.TextChannel | None:
    category = guild.get_channel(TICKET_CATEGORY_ID)
    if category is None or not isinstance(category, discord.CategoryChannel):
        return None
    for channel in category.channels:
        if isinstance(channel, discord.TextChannel):
            topic = channel.topic or ""
            if get_topic_value(topic, DM_TICKET_OWNER_MARKER) == str(user.id):
                return channel
    return None


def get_topic_value(topic: str, marker: str) -> str | None:
    """Return the value stored after a ticket topic marker."""
    for line in topic.splitlines():
        if line.startswith(marker):
            return line.removeprefix(marker).strip() or None
    return None


def set_topic_value(topic: str, marker: str, value: str | None) -> str:
    """Set or remove a ticket topic marker without disturbing other markers."""
    lines = [line for line in topic.splitlines() if not line.startswith(marker)]
    if value is not None:
        lines.append(f"{marker} {value}")
    return "\n".join(lines)


def get_ticket_support_ids(topic: str) -> set[int]:
    """Return support members explicitly added to a ticket topic."""
    value = get_topic_value(topic, DM_TICKET_SUPPORT_MARKER)
    if value is None:
        return set()
    return {int(item) for item in value.split(",") if item.strip().isdigit()}


def set_ticket_support_ids(topic: str, member_ids: set[int]) -> str:
    """Persist explicitly added support members in a restart-safe topic marker."""
    value = ",".join(str(member_id) for member_id in sorted(member_ids)) or None
    return set_topic_value(topic, DM_TICKET_SUPPORT_MARKER, value)


def is_ticket_channel(channel: discord.TextChannel) -> bool:
    """Return whether a channel is a live ticket created in the ticket category."""
    return (
        channel.category_id == TICKET_CATEGORY_ID
        and (
            get_topic_value(channel.topic or "", DM_TICKET_OWNER_MARKER) is not None
            or get_topic_value(channel.topic or "", DM_TICKET_CATEGORY_MARKER) is not None
        )
    )


def toggle_ticket_claim(topic: str, member_id: int) -> tuple[str, bool]:
    """Return the next claim topic and whether this action is an unclaim.

    The topic is the only source of truth, so this remains restart-safe and can
    be applied repeatedly without relying on a particular button/view instance.
    """
    claimed_id = get_topic_value(topic, DM_TICKET_CLAIM_MARKER)
    if claimed_id is not None and claimed_id != str(member_id):
        raise ValueError("This ticket has already been claimed by another support agent.")
    unclaiming = claimed_id == str(member_id)
    next_claim = None if unclaiming else str(member_id)
    return set_topic_value(topic, DM_TICKET_CLAIM_MARKER, next_claim), unclaiming


async def create_dm_ticket_channel(
    guild: discord.Guild,
    user: discord.abc.User,
    category_key: str,
    prefix: str,
) -> discord.TextChannel:
    """Create a staff-only relay channel for a ticket opened in the bot's DMs."""
    category = guild.get_channel(TICKET_CATEGORY_ID)
    if not isinstance(category, discord.CategoryChannel):
        raise ValueError(f"Ticket category {TICKET_CATEGORY_ID} not found.")

    safe_name = "".join(c if c.isalnum() or c == "-" else "-" for c in user.name.lower())
    channel_name = f"{prefix}-{safe_name}"[:100]

    overwrites: dict[discord.abc.Snowflake, discord.PermissionOverwrite] = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            read_message_history=True,
        ),
    }
    # Leadership always gets full admin on every ticket
    staff_role = guild.get_role(STAFF_ROLE_ID)
    if staff_role is not None:
        overwrites[staff_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            manage_permissions=True,
            manage_messages=True,
        )
    admin_role = guild.get_role(ADMIN_ROLE_ID)
    if admin_role is not None:
        overwrites[admin_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
            manage_channels=True,
            manage_permissions=True,
            manage_messages=True,
        )
    channel = await guild.create_text_channel(
        name=channel_name,
        category=category,  # type: ignore[arg-type]
        overwrites=overwrites,
        topic=(
            f"{DM_TICKET_OWNER_MARKER} {user.id}\n"
            f"{DM_TICKET_CATEGORY_MARKER} {category_key}"
        ),
        reason=f"DM HelpDesk ticket opened by {user} ({user.id})",
    )
    return channel


def can_close_ticket(member: discord.Member, channel: discord.TextChannel) -> bool:
    return is_staff(member) or is_admin(member) or get_ticket_owner_id(channel) == member.id


async def notify_ticket_owner(
    client: discord.Client,
    owner_id: str | None,
    title: str,
    message: str,
) -> None:
    """Send a ticket status update to the customer without breaking staff actions."""
    if owner_id is None or not owner_id.isdigit():
        return
    try:
        user = client.get_user(int(owner_id)) or await client.fetch_user(int(owner_id))
        await user.send(embed=_base_embed(title=title, description=message))
    except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
        log.warning("Could not notify DM ticket owner %s: %s", owner_id, exc)


async def send_embed_to_ticket_owner(
    client: discord.Client,
    channel: discord.TextChannel,
    embed: discord.Embed,
) -> bool:
    """Deliver a ticket command's full embed to the customer in DMs."""
    owner_id = get_topic_value(channel.topic or "", DM_TICKET_OWNER_MARKER)
    if owner_id is None or not owner_id.isdigit():
        return False
    try:
        user = client.get_user(int(owner_id)) or await client.fetch_user(int(owner_id))
        await user.send(embed=embed)
        return True
    except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
        log.warning("Could not deliver ticket command to owner %s: %s", owner_id, exc)
        return False


def relay_description(message: discord.Message) -> str:
    """Build safe relay text containing message content and attachment links."""
    parts = [message.content] if message.content else []
    parts.extend(f"<:Connection:1540927881683669013> [{attachment.filename}]({attachment.url})" for attachment in message.attachments)
    description = "\n".join(parts) or "*(No text content)*"
    return description if len(description) <= 4000 else f"{description[:3997]}..."


async def relay_customer_message(message: discord.Message, channel: discord.TextChannel) -> bool:
    """Relay a customer DM once, even if Discord dispatches it repeatedly."""
    embed = customer_response_embed(
        content=relay_description(message),
        customer_id=message.author.id,
        timestamp=message.created_at,
        author=message.author,
    )
    lock = CUSTOMER_RELAY_LOCKS.setdefault(channel.id, asyncio.Lock())
    async with lock:
        bot_member = channel.guild.me
        async for previous in channel.history(limit=20):
            if bot_member is None or previous.author.id != bot_member.id or not previous.embeds:
                continue
            prior = previous.embeds[0]
            if prior.description == embed.description and prior.timestamp == embed.timestamp:
                return False
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    # A reaction is only an acknowledgement. If Discord rate-limits or rejects
    # it, the already-delivered support message must not be treated as failed and
    # retried (which previously contributed to duplicate-looking behavior).
    try:
        await message.add_reaction(CHECKMARK_EMOJI)
    except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
        log.warning("Relayed DM %s but could not add CheckMark reaction: %s", message.id, exc)
    return True

def conversation_embed(
    content: str,
    customer_id: int | str,
    heading: str,
    timestamp: datetime | None = None,
    author: discord.abc.User | None = None,
    color: int = DELTA_RED,
) -> discord.Embed:
    """Build a ticket conversation embed with an explicit, non-replaced heading."""
    safe_content = content if len(content) <= 3500 else f"{content[:3497]}..."
    embed = discord.Embed(
        description=(
            f"{MESSAGE_EMOJI} **{heading}**\n\n"
            f"{safe_content}\n\n"
            f"{IDENTIFICATION_EMOJI} **Customer ID**\n"
            f"{customer_id}"
        ),
        color=color,
    )
    embed.set_footer(text=FOOTER_TEXT)
    if author is not None:
        embed.set_author(name=str(author), icon_url=author.display_avatar.url)
    embed.timestamp = timestamp
    return embed

def customer_response_embed(
    content: str,
    customer_id: int | str,
    timestamp: datetime | None = None,
    author: discord.abc.User | None = None,
) -> discord.Embed:
    """Build the customer-to-support ticket record."""
    return conversation_embed(
        content, customer_id, "Customer Response", timestamp, author
    )


def attributed_staff_reply_embed(
    content: str,
    customer_id: int | str,
    author: discord.Member,
    timestamp: datetime | None = None,
) -> discord.Embed:
    """Build the private ticket record identifying the responding agent."""
    return conversation_embed(
        content,
        customer_id,
        author.display_name,
        timestamp,
        author,
        DELTA_BLUE,
    )


async def deliver_support_reply(
    client: discord.Client,
    owner_id: str,
    content: str,
) -> bool:
    """Deliver plain text to the customer while embeds remain staff-only."""
    try:
        user = client.get_user(int(owner_id)) or await client.fetch_user(int(owner_id))
        await user.send(content, allowed_mentions=discord.AllowedMentions.none())
        return True
    except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
        log.warning("Could not relay support message to %s: %s", owner_id, exc)
        return False


async def open_dm_ticket(
    bot: "DeltaBot",
    user: discord.abc.User,
    category_key: str,
) -> tuple[discord.TextChannel, bool]:
    """Create and introduce a staff relay channel for a confirmed DM ticket."""
    category = bot.get_channel(TICKET_CATEGORY_ID)
    if not isinstance(category, discord.CategoryChannel):
        raise ValueError("The configured ticket category could not be found.")
    guild = category.guild
    existing = await find_existing_ticket(guild, user)
    if existing is not None:
        return existing, False

    cfg = TICKET_CONFIG[category_key]
    channel = await create_dm_ticket_channel(
        guild=guild,
        user=user,
        category_key=category_key,
        prefix=cfg["prefix"],
    )
    mention_ids = [STAFF_ROLE_ID]
    mentions = [
        role.mention
        for role_id in dict.fromkeys(mention_ids)
        if (role := guild.get_role(role_id)) is not None
    ]
    await channel.send(" ".join(mentions))
    embed = _base_embed(
        title=f"{cfg['emoji']}  {cfg['label']} | Private DM Support",
        description=(
            f"A new private support request has been received from **{user}**.\n\n"
            "The customer will remain in the bot's direct messages. Messages they send "
            "will appear here automatically, and replies from the assigned agent will "
            "be delivered back to their DMs."
        ),
    )
    embed.add_field(name="Customer", value=f"{user} (`{user.id}`)", inline=True)
    embed.add_field(name="Department", value=cfg["label"], inline=True)
    embed.add_field(
        name="Support Instructions",
        value=(
            "1. Select **Claim Ticket** before replying.\n"
            "2. Send replies normally in this channel.\n"
            f"3. A {CHECKMARK_EMOJI} confirms delivery to the customer."
        ),
        inline=False,
    )
    _set_brand_image(embed, DIVIDER_URL)
    await channel.send(embed=embed, view=TicketActionView())
    return channel, True


# ════════════════════════════════════════════════════════════════════════════════
# TRANSCRIPT + FINALIZE HELPERS
# ════════════════════════════════════════════════════════════════════════════════

async def generate_transcript(channel: discord.TextChannel) -> str:
    """Fetch all messages and return them as a formatted string."""
    lines: list[str] = [
        f"═══════════════════════════════════════════════════════",
        f"  DELTA AIR LINES — TICKET TRANSCRIPT",
        f"  Channel : #{channel.name}",
        f"  ID      : {channel.id}",
        f"═══════════════════════════════════════════════════════\n",
    ]
    messages = [msg async for msg in channel.history(limit=None, oldest_first=True)]
    for msg in messages:
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        content = msg.content or ""
        if msg.embeds:
            for emb in msg.embeds:
                title = emb.title or ""
                desc  = emb.description or ""
                content += f"\n[EMBED] {title}\n{desc}"
        if msg.attachments:
            for att in msg.attachments:
                content += f"\n[ATTACHMENT] {att.url}"
        lines.append(f"[{ts}] {msg.author} ({msg.author.id}): {content}")
    return "\n".join(lines)


async def _archive_ticket(
    channel: discord.TextChannel,
    closer: discord.Member,
    reason: str,
    rating: int | None,
) -> discord.Message | None:
    """Generate and log the ticket transcript before deletion."""
    guild = channel.guild

    # Find ticket owner from topic
    owner_id = get_ticket_owner_id(channel)
    owner = guild.get_member(owner_id) if owner_id is not None else None

    # Generate transcript text
    transcript_text = await generate_transcript(channel)
    rating_line = f"{rating} / 5 {WING_PIN_EMOJI}" if rating is not None else "No rating given"
    transcript_text += (
        f"\n\n═══════════════════════════════════════════════════════"
        f"\n  CLOSE REASON : {reason}"
        f"\n  RATING       : {rating_line}"
        f"\n  CLOSED BY    : {closer} ({closer.id})"
        f"\n═══════════════════════════════════════════════════════"
    )

    # Send to transcript log channel
    log_channel = guild.get_channel(TRANSCRIPT_CHANNEL_ID)
    if isinstance(log_channel, discord.TextChannel):
        stars = WING_PIN_EMOJI * rating if rating else "—"
        log_embed = _base_embed(
            title="<:Support:1540927430179553321>  Ticket Transcript",
            description=(
                f"**Channel:** #{channel.name}\n"
                f"**Opened by:** {owner.mention if owner else 'Unknown'}\n"
                f"**Closed by:** {closer.mention}\n"
                f"**Reason:** {reason}\n"
                f"**Rating:** {stars} ({rating_line})"
            ),
        )
        _set_brand_image(log_embed, DIVIDER_URL)
        file = discord.File(
            fp=__import__("io").BytesIO(transcript_text.encode()),
            filename=f"transcript-{channel.name}.txt",
        )
        return await log_channel.send(embed=log_embed, file=file)
    return None

async def _finalize_ticket(
    channel: discord.TextChannel,
    closer: discord.Member,
    reason: str,
    rating: int | None,
    close_deadline: float | None = None,
) -> discord.Message | None:
    """Archive a ticket when possible, but always attempt to delete it."""
    archive_message: discord.Message | None = None
    try:
        archive_message = await _archive_ticket(channel, closer, reason, rating)
    except (discord.Forbidden, discord.HTTPException) as exc:
        # A transcript/DM failure must not leave a channel stuck open.
        log.warning("Could not fully archive ticket %s: %s", channel.id, exc)
    finally:
        if close_deadline is not None:
            await asyncio.sleep(max(0, close_deadline - time.monotonic()))
        try:
            await channel.delete(reason=f"Ticket closed by {closer}: {reason}")
        except discord.NotFound:
            pass
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.error("Could not delete closed ticket %s: %s", channel.id, exc)
    return archive_message


# ════════════════════════════════════════════════════════════════════════════════
# MODALS
# ════════════════════════════════════════════════════════════════════════════════

class CloseReasonModal(discord.ui.Modal, title="Close Ticket — Delta Air Lines"):
    reason = discord.ui.TextInput(
        label="Reason for closing",
        placeholder="e.g. Issue resolved, No response from user...",
        style=discord.TextStyle.paragraph,
        max_length=500,
        required=True,
    )

    def __init__(self, channel: discord.TextChannel, closer: discord.Member) -> None:
        super().__init__()
        self._channel = channel
        self._closer  = closer

    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Acknowledge the modal immediately
        await interaction.response.defer(ephemeral=True)

        # Find the ticket owner from the channel topic
        owner_id = get_ticket_owner_id(self._channel)
        owner = self._channel.guild.get_member(owner_id) if owner_id is not None else None

        close_deadline = time.monotonic() + TICKET_CLOSE_DELAY
        view = RatingView(
            owner_id=owner.id if owner is not None else None,
        )

        # Send rating prompt to the owner's DMs
        dm_sent = False
        if owner is not None:
            rating_embed = _base_embed(
                title=f"{WING_PIN_EMOJI}  Rate Your Support Experience",
                description=(
                    f"Your support ticket **#{self._channel.name}** has been closed.\n\n"
                    f"**Reason:** {self.reason.value}\n\n"
                    "Please select a rating below. The buttons remain available for "
                    "**15 days**. If you need more help, you can open a new ticket.\n\n"
                    "*Thank you for contacting Delta Air Lines Support.*"
                ),
            )
            _set_brand_image(rating_embed, DIVIDER_URL)
            try:
                view.message = await owner.send(embed=rating_embed, view=view)
                dm_sent = True
            except discord.Forbidden:
                pass

        # Always show the same countdown in the ticket, even when the owner
        # cannot receive the optional rating request.
        await self._channel.send(embed=ticket_closed_channel())

        if dm_sent:
            await interaction.followup.send(
                embed=success_embed(f"A rating request was sent by DM. The ticket will close in {TICKET_CLOSE_DELAY} seconds."),
                ephemeral=True,
            )
        else:
            # DMs disabled — finalize immediately without rating
            await interaction.followup.send(
                embed=success_embed("Closing in progress — please wait."),
                ephemeral=True,
            )
        # Closing the channel and expiring the DM rating are independent: the
        # channel still closes after five seconds, while the one DM remains.
        await asyncio.sleep(max(0, close_deadline - time.monotonic()))
        view.archive_message = await _finalize_ticket(
            self._channel,
            self._closer,
            self.reason.value,
            rating=view.rating,
        )


# ════════════════════════════════════════════════════════════════════════════════
# RATING VIEW
# ════════════════════════════════════════════════════════════════════════════════

class RatingView(discord.ui.View):
    """Star rating buttons kept in the ticket owner's single closure DM."""

    STARS = [
        ("1", 1, discord.ButtonStyle.secondary),
        ("2", 2, discord.ButtonStyle.secondary),
        ("3", 3, discord.ButtonStyle.secondary),
        ("4", 4, discord.ButtonStyle.success),
        ("5", 5, discord.ButtonStyle.success),
    ]

    def __init__(self, owner_id: int | None) -> None:
        super().__init__(timeout=RATING_TIMEOUT)
        self._owner_id = owner_id
        self._rated = False
        self.rating: int | None = None
        self.message: discord.Message | None = None
        self.archive_message: discord.Message | None = None

        for label, value, style in self.STARS:
            button: discord.ui.Button = discord.ui.Button(
                label=label,
                emoji=WING_PIN_EMOJI,
                style=style,
                custom_id=f"delta:rating:{value}",
            )
            button.callback = self._make_callback(value)
            self.add_item(button)

    def _make_callback(self, stars: int):
        async def callback(interaction: discord.Interaction) -> None:
            if self._rated:
                await interaction.response.send_message(
                    embed=error_embed("This ticket has already been rated."),
                    ephemeral=True,
                )
                return

            if self._owner_id is None or interaction.user.id != self._owner_id:
                await interaction.response.send_message(
                    embed=error_embed("Only the ticket owner can submit a rating."),
                    ephemeral=True,
                )
                return

            self._rated = True
            self.rating = stars
            self.stop()
            confirm = _base_embed(
                title=f"{CHECKMARK_EMOJI}  Rating Submitted",
                description=(
                    f"Thank you! You rated your support experience **{stars} / 5 {WING_PIN_EMOJI}**.\n\n"
                    "*Delta Air Lines — Keep Climbing.*"
                ),
            )
            _set_brand_image(confirm, DIVIDER_URL)
            # Edit the existing closure embed instead of sending a second DM.
            await interaction.response.edit_message(embed=confirm, view=None)
            await self._update_archived_rating(stars)

        return callback

    async def _update_archived_rating(self, stars: int) -> None:
        """Keep the staff transcript rating in sync with a later DM rating."""
        # A member can click while the five-second close/archive task is still
        # running. Briefly wait for its message reference so that timing never
        # leaves the staff copy showing "No rating given".
        for _ in range(TICKET_CLOSE_DELAY * 2 + 2):
            if self.archive_message is not None:
                break
            await asyncio.sleep(0.5)
        if self.archive_message is None or not self.archive_message.embeds:
            return

        embed = self.archive_message.embeds[0]
        description = embed.description or ""
        lines = description.splitlines()
        rating_line = f"**Rating:** {WING_PIN_EMOJI * stars} ({stars} / 5 {WING_PIN_EMOJI})"
        for index, line in enumerate(lines):
            if line.startswith("**Rating:**"):
                lines[index] = rating_line
                break
        else:
            lines.append(rating_line)
        embed.description = "\n".join(lines)
        try:
            await self.archive_message.edit(embed=embed)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
            log.warning("Could not update archived ticket rating: %s", exc)

    async def on_timeout(self) -> None:
        """Disable the buttons after 15 days without sending another DM."""
        for item in self.children:
            item.disabled = True
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass


# ════════════════════════════════════════════════════════════════════════════════
# VIEWS (UI COMPONENTS)
# ════════════════════════════════════════════════════════════════════════════════

class TicketActionView(discord.ui.View):
    """Persistent view with Claim/Unclaim and Close buttons attached to every ticket."""

    _claim_locks: dict[int, asyncio.Lock] = {}

    def __init__(self, claimed: bool = False) -> None:
        super().__init__(timeout=None)
        if claimed:
            self.claim_ticket.label = "Unclaim Ticket"
            self.claim_ticket.style = discord.ButtonStyle.secondary

    # ── Claim / Unclaim ────────────────────────────────────────────────────────────
    @discord.ui.button(
        label="Claim Ticket",
        emoji=SUPPORT_EMOJI,
        style=discord.ButtonStyle.primary,
        custom_id="delta:claim_ticket",
    )
    async def claim_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        member = interaction.user
        channel = interaction.channel
        if not isinstance(member, discord.Member) or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("This button can only be used by support staff in a ticket channel."),
                ephemeral=True,
            )
            return

        if not is_staff(member):
            await interaction.response.send_message(
                embed=error_embed("Only support team members can claim tickets."),
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Serialise claim changes per channel so two agents cannot claim the same
        # ticket at the same time. Fetch the channel before every change instead
        # of trusting Discord's local topic cache; a stale cached claim marker was
        # what prevented agents from reclaiming a ticket immediately after an
        # unclaim.
        lock = self._claim_locks.setdefault(channel.id, asyncio.Lock())
        async with lock:
            try:
                fresh_channel = await channel.guild.fetch_channel(channel.id)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
                await interaction.followup.send(
                    embed=error_embed(f"I could not refresh this ticket: {exc}"),
                    ephemeral=True,
                )
                return
            if not isinstance(fresh_channel, discord.TextChannel):
                await interaction.followup.send(
                    embed=error_embed("This is no longer a valid ticket channel."),
                    ephemeral=True,
                )
                return

            topic = fresh_channel.topic or ""
            owner_id = get_topic_value(topic, DM_TICKET_OWNER_MARKER)
            try:
                new_topic, unclaiming = toggle_ticket_claim(topic, member.id)
            except ValueError as exc:
                await interaction.followup.send(
                    embed=error_embed(str(exc)),
                    ephemeral=True,
                )
                return
            fresh_channel = await fresh_channel.edit(
                topic=new_topic,
                reason=f"Ticket {'unclaimed' if unclaiming else 'claimed'} by {member}",
            )

        if unclaiming:
            await interaction.followup.send(
                embed=success_embed("You have unclaimed this ticket."), ephemeral=True
            )
            status_embed = _base_embed(
                title=f"{CHECKMARK_EMOJI}  Ticket Unclaimed",
                description=f"This ticket has been unclaimed by {member.mention}.",
            )
            owner_title = f"{CHECKMARK_EMOJI}  Support Agent Disconnected"
            owner_message = (
                "The support agent handling your ticket has unclaimed it. "
                "Another agent can now assist you."
            )
        else:
            await interaction.followup.send(
                embed=success_embed("You have claimed this ticket."), ephemeral=True
            )
            status_embed = _base_embed(
                title="<:Support:1540927430179553321>  Ticket Claimed",
                description=(
                    f"This ticket has been claimed by {member.mention}.\n\n"
                    "They will be assisting the customer through the DM relay."
                ),
            )
            if owner_id is not None and owner_id.isdigit():
                try:
                    owner = interaction.client.get_user(int(owner_id)) or await interaction.client.fetch_user(int(owner_id))
                    await owner.send(embed=_base_embed(description=TICKET_CLAIMED_MESSAGE))
                except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
                    log.warning("Could not send claimed notice to ticket owner %s: %s", owner_id, exc)

        _set_brand_image(status_embed, DIVIDER_URL)
        await fresh_channel.send(embed=status_embed)
        if interaction.message is not None:
            await interaction.message.edit(view=TicketActionView(claimed=not unclaiming))
        if unclaiming:
            await notify_ticket_owner(interaction.client, owner_id, owner_title, owner_message)

    # ── Close ──────────────────────────────────────────────────────────────────────
    @discord.ui.button(
        label="Close Ticket",
        emoji=RIGHT_ARROW_EMOJI,
        style=discord.ButtonStyle.danger,
        custom_id="delta:close_ticket",
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        channel = interaction.channel
        member  = interaction.user

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("This button can only be used inside a ticket channel."),
                ephemeral=True,
            )
            return

        if not isinstance(member, discord.Member):
            await interaction.response.send_message(
                embed=error_embed("Unable to verify your permissions."),
                ephemeral=True,
            )
            return

        if not can_close_ticket(member, channel):
            await interaction.response.send_message(
                embed=error_embed("You do not have permission to close this ticket."),
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(CloseReasonModal(channel, member))


# Keep old name as alias so existing persistent views still resolve
CloseTicketButton = TicketActionView


class AssistanceSelect(discord.ui.Select):
    def __init__(self, bot: "DeltaBot", user_id: int) -> None:
        self.bot = bot
        self.user_id = user_id
        options = [
            discord.SelectOption(
                label=cfg["label"],
                value=key,
                emoji=cfg["emoji"],
                description=cfg["description"],
            )
            for key, cfg in TICKET_CONFIG.items()
        ]
        super().__init__(
            placeholder="Select an Assistance Category",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="delta:assistance_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            await self._handle_selection(interaction)
        except Exception:
            log.exception(
                "DM assistance dropdown failed for user %s (interaction %s).",
                interaction.user.id,
                interaction.id,
            )
            try:
                sender = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
                await sender(embed=error_embed("I could not open your ticket. Please try again."))
            except discord.HTTPException:
                log.exception("Could not send the DM dropdown failure response for interaction %s.", interaction.id)

    async def _handle_selection(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        user = interaction.user
        if user.id != self.user_id:
            await interaction.followup.send(
                embed=error_embed("This assistance panel belongs to another user."),
            )
            return

        category = self.bot.get_channel(TICKET_CATEGORY_ID)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(embed=error_embed("I could not connect your ticket just now. Please try again shortly."))
            return
        guild = category.guild

        selected_key = self.values[0]

        # Discord keeps a user's last selection highlighted unless the source
        # message is refreshed. Replace the view immediately so this member can
        # select the same category again after their ticket is closed.
        if interaction.message is not None:
            try:
                await interaction.message.edit(view=DMAssistancePanelView(self.bot, user.id))
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                log.warning("Unable to reset assistance dropdown on message %s", interaction.message.id)

        try:
            _, created = await open_dm_ticket(self.bot, user, selected_key)
        except Exception as exc:
            log.exception(
                "Could not open DM assistance ticket for user %s in category %s.",
                user.id,
                selected_key,
            )
            self.bot._dm_prompted_users.discard(user.id)
            await interaction.followup.send(
                embed=error_embed(f"Failed to create your ticket: {exc}"),
            )
            return

        self.bot._dm_prompted_users.discard(user.id)
        if created:
            await interaction.followup.send(embed=connected_embed())
        else:
            await interaction.followup.send(
                embed=success_embed("You are still connected to your existing support ticket. Send your next message here and I will forward it to the same ticket."),
            )


class DMAssistancePanelView(discord.ui.View):
    def __init__(self, bot: "DeltaBot", user_id: int) -> None:
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.add_item(AssistanceSelect(bot, user_id))

    async def on_timeout(self) -> None:
        self.bot._dm_prompted_users.discard(self.user_id)


class ServerAssistanceSelect(discord.ui.Select):
    """Public panel selector that immediately opens or reuses a DM ticket."""

    def __init__(self, bot: "DeltaBot") -> None:
        self.bot = bot
        options = [
            discord.SelectOption(
                label=cfg["label"],
                value=key,
                emoji=cfg["emoji"],
                description=cfg["description"],
            )
            for key, cfg in TICKET_CONFIG.items()
        ]
        super().__init__(
            placeholder="Select an Assistance Category",
            options=options,
            custom_id="delta:server_assistance_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            await self._handle_selection(interaction)
        except Exception:
            log.exception(
                "Server assistance dropdown failed for user %s (interaction %s).",
                interaction.user.id,
                interaction.id,
            )
            try:
                sender = interaction.followup.send if interaction.response.is_done() else interaction.response.send_message
                await sender(
                    embed=error_embed("I could not open your ticket. Please try again."),
                    ephemeral=True,
                )
            except discord.HTTPException:
                log.exception("Could not send the server dropdown failure response for interaction %s.", interaction.id)

    async def _handle_selection(self, interaction: discord.Interaction) -> None:
        selected_key = self.values[0]
        cfg = TICKET_CONFIG[selected_key]
        await interaction.response.defer(ephemeral=True)
        try:
            # Confirm that DMs are open before creating the private staff channel,
            # then replace this temporary line with the final connection notice.
            dm_message = await interaction.user.send("Connecting you to Delta Support...")
        except discord.Forbidden:
            await interaction.followup.send(
                embed=error_embed("I could not send you a DM. Enable direct messages from this server and try again."),
                ephemeral=True,
            )
            return
        try:
            _, created = await open_dm_ticket(self.bot, interaction.user, selected_key)
            notice = connected_embed() if created else success_embed(
                "You are still connected to your existing support ticket. Send your message here and it will go to the same support team."
            )
            await dm_message.edit(content=None, embed=notice)
        except (discord.HTTPException, ValueError) as exc:
            log.exception(
                "Could not open server assistance ticket for user %s in category %s.",
                interaction.user.id,
                selected_key,
            )
            try:
                await dm_message.edit(content="Delta Support could not open your ticket. Please try again.")
            except discord.HTTPException:
                pass
            await interaction.followup.send(
                embed=error_embed(f"The ticket could not be opened: {exc}"), ephemeral=True
            )
            return

        await interaction.followup.send(
            embed=success_embed(
                f"Support is ready in your DMs for your **{cfg['label']}** request."
            ),
            ephemeral=True,
        )
        if interaction.message is not None:
            try:
                await interaction.message.edit(view=ServerAssistancePanelView(self.bot))
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                pass


class ServerAssistancePanelView(discord.ui.View):
    def __init__(self, bot: "DeltaBot") -> None:
        super().__init__(timeout=None)
        self.add_item(ServerAssistanceSelect(bot))


class NonMemberView(discord.ui.View):
    """Actions shown to people who DM the bot before joining the server."""

    def __init__(self, bot: "DeltaBot", user_id: int) -> None:
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        def named_emoji(name: str) -> discord.Emoji | None:
            return next((emoji for emoji in bot.emojis if emoji.name == name), None)

        join = discord.ui.Button(
            label="Join Delta Air Lines",
            style=discord.ButtonStyle.link,
            url=INVITE_URL,
            emoji=named_emoji("ExternalLink~1") or named_emoji("ExternalLink"),
        )
        self.add_item(join)
        self.create_ticket.emoji = named_emoji("Ticket~1") or named_emoji("Ticket")

    @discord.ui.button(
        label="Create Ticket",
        style=discord.ButtonStyle.success,
    )
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This button belongs to another user.")
            return
        await interaction.response.send_message(
            "Please join Delta Air Lines first. Once you have joined, press this button again or DM me to create a ticket.",
            view=NonMemberView(self.bot, self.user_id),
        )


# ════════════════════════════════════════════════════════════════════════════════
# SLASH COMMANDS
# ════════════════════════════════════════════════════════════════════════════════

def staff_only() -> app_commands.check:
    async def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not isinstance(member, discord.Member):
            return False
        bot = interaction.client
        restriction = getattr(bot, "ticket_restrictions", {}).get(member.id)
        if restriction is not None:
            kind, expires_at = restriction
            if expires_at is None or expires_at > time.time():
                return False
            bot.ticket_restrictions.pop(member.id, None)
        return is_staff(member) or is_admin(member)
    return app_commands.check(predicate)


def admin_only() -> app_commands.check:
    async def predicate(interaction: discord.Interaction) -> bool:
        return isinstance(interaction.user, discord.Member) and is_admin(interaction.user)
    return app_commands.check(predicate)


def register_commands(tree: app_commands.CommandTree) -> None:
    # Clear commands owned by this module before rebuilding the tree. This makes
    # registration safe if startup is retried or the tree was populated earlier,
    # instead of letting CommandAlreadyRegistered terminate the deployment.
    for command_name in (
        "assistance",
        "panel",
        "hr",
        "leadership",
        "close",
        "reply",
        "connected",
        "unavailable",
        "format",
        "resolved",
        "revoke",
        "ticket",
        "tickets",
        "version",
        "authentication-control",
        "economy",
    ):
        tree.remove_command(command_name, type=discord.AppCommandType.chat_input)

    @tree.command(
        name="panel",
        description="Post the Assistance Panel with your chosen top and bottom banners.",
    )
    @staff_only()
    @app_commands.describe(
        top_banner="The image to display above the panel message.",
        bottom_banner="The image to display below the message and above the dropdown.",
    )
    async def panel(
        interaction: discord.Interaction,
        top_banner: discord.Attachment,
        bottom_banner: discord.Attachment,
    ) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("The Assistance Panel can only be posted in a server text channel."),
                ephemeral=True,
            )
            return
        if any(
            attachment.content_type is not None
            and not attachment.content_type.startswith("image/")
            for attachment in (top_banner, bottom_banner)
        ):
            await interaction.response.send_message(
                embed=error_embed("Both banner attachments must be image files."),
                ephemeral=True,
            )
            return
        await interaction.response.defer(ephemeral=True)
        try:
            banner, bottom = await asyncio.gather(top_banner.to_file(), bottom_banner.to_file())
            await interaction.channel.send(file=banner)
            await interaction.channel.send(PANEL_MESSAGE)
            await interaction.channel.send(
                file=bottom,
                view=ServerAssistancePanelView(interaction.client),
            )
        except (discord.HTTPException, ValueError) as exc:
            log.error("Could not post the Assistance Panel assets: %s", exc)
            await interaction.followup.send(
                embed=error_embed("The Assistance Panel images could not be loaded. Please try again."),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=success_embed("The private DM Assistance Panel was posted successfully."),
            ephemeral=True,
        )

    @tree.command(name="version", description="Show the running HelpDesk status and release.")
    @staff_only()
    async def version(interaction: discord.Interaction) -> None:
        bot = interaction.client
        uptime = format_uptime(time.monotonic() - bot.started_monotonic)
        latency_ms = round(bot.latency * 1000)
        await interaction.response.send_message(
            embed=_base_embed(
                title=f"{SUPPORT_EMOJI}  HelpDesk Status",
                description=(
                    f"**Version:** `{BOT_VERSION}`\n"
                    f"**Git commit:** `{deployed_source()}`\n"
                    f"**Uptime:** `{uptime}`\n"
                    f"**Discord latency:** `{latency_ms} ms`"
                ),
            ),
            ephemeral=True,
        )

    # /reply
    @tree.command(name="reply", description="Send a reply to the ticket customer's DMs.")
    @staff_only()
    @app_commands.describe(message="The message to send to the customer.")
    async def reply(
        interaction: discord.Interaction,
        message: app_commands.Range[str, 1, 2000],
    ) -> None:
        channel = interaction.channel
        member = interaction.user
        x_emoji = delta_status_emoji(interaction.guild, success=False)
        if not isinstance(channel, discord.TextChannel) or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                f"{x_emoji} Use `/reply` inside a ticket channel.",
                ephemeral=True,
            )
            return

        try:
            fresh_channel = await channel.guild.fetch_channel(channel.id)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
            await interaction.response.send_message(
                f"{x_emoji} I could not load this ticket: {exc}", ephemeral=True
            )
            return
        if not isinstance(fresh_channel, discord.TextChannel):
            await interaction.response.send_message(
                f"{x_emoji} This is not a ticket channel.", ephemeral=True
            )
            return

        topic = fresh_channel.topic or ""
        owner_id = get_topic_value(topic, DM_TICKET_OWNER_MARKER)
        claimed_id = get_topic_value(topic, DM_TICKET_CLAIM_MARKER)
        added_support_ids = get_ticket_support_ids(topic)
        member_overwrite = fresh_channel.overwrites_for(member)
        explicitly_added = (
            member in fresh_channel.overwrites
            and member_overwrite.view_channel is True
            and member_overwrite.send_messages is True
        )
        if owner_id is None:
            await interaction.response.send_message(
                f"{x_emoji} This channel does not have a ticket customer.", ephemeral=True
            )
            return
        if (
            claimed_id != str(member.id)
            and member.id not in added_support_ids
            and not explicitly_added
        ):
            await interaction.response.send_message(
                f"{x_emoji} Claim this ticket or ask the claimant to add you with "
                "`/ticket control` before using `/reply`.",
                ephemeral=True,
            )
            return

        if interaction.id in interaction.client.processed_reply_interactions:
            await interaction.response.send_message(
                f"{CHECKMARK_EMOJI} This reply was already delivered.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)
        interaction.client.processed_reply_interactions.add(interaction.id)
        if not await deliver_support_reply(interaction.client, owner_id, message):
            interaction.client.processed_reply_interactions.discard(interaction.id)
            await interaction.followup.send(
                f"{x_emoji} The reply could not be delivered to the customer's DMs.",
                ephemeral=True,
            )
            return

        staff_embed = attributed_staff_reply_embed(
            message, owner_id, member, interaction.created_at
        )
        await fresh_channel.send(embed=staff_embed)
        await interaction.followup.send(
            f"{CHECKMARK_EMOJI} Reply delivered to the customer.", ephemeral=True
        )

    # /format — all prewritten customer notices in one command
    format_choices = [
        app_commands.Choice(name=label, value=key)
        for key, label in SUPPORT_FORMAT_LABELS.items()
    ]

    @tree.command(
        name="format",
        description="Send a prewritten Delta support notice to this ticket's customer.",
    )
    @staff_only()
    @app_commands.describe(format="The notice format to send.")
    @app_commands.choices(format=format_choices)
    async def format_notice(
        interaction: discord.Interaction,
        format: app_commands.Choice[str],
    ) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("Use `/format` inside a ticket channel."),
                ephemeral=True,
            )
            return
        if get_ticket_owner_id(channel) is None:
            await interaction.response.send_message(
                embed=error_embed("This channel does not have a ticket customer."),
                ephemeral=True,
            )
            return

        # Construct one customer-safe embed and use the exact same payload for
        # the DM and staff-side record. No agent name, mention, avatar, or ID is
        # included in any customer-facing format.
        embed = support_format_embed(format.value)
        delivered = await send_embed_to_ticket_owner(interaction.client, channel, embed)
        await interaction.response.send_message(
            embed=success_embed(
                f"The **{format.name}** notice was delivered to the customer's DMs."
                if delivered else
                "The notice was posted here, but the customer's DMs could not be reached."
            ),
            ephemeral=True,
        )
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    # /ticket control and /ticket admin — consolidated ticket operations
    ticket_group = app_commands.Group(name="ticket", description="Manage support tickets.")

    control_choices = [
        app_commands.Choice(name="Add Customer", value="add_customer"),
        app_commands.Choice(name="Remove Customer", value="remove_customer"),
        app_commands.Choice(name="Add Support", value="add_support"),
        app_commands.Choice(name="Remove Support", value="remove_support"),
        app_commands.Choice(name="Close Ticket", value="close"),
    ]
    admin_choices = [
        *control_choices,
        app_commands.Choice(name="Claim for Support", value="claim"),
        app_commands.Choice(name="Unclaim Ticket", value="unclaim"),
        app_commands.Choice(name="Punish Member", value="punish"),
        app_commands.Choice(name="Remove Punishment", value="unpunish"),
        app_commands.Choice(name="Undo Last Admin Action", value="undo"),
    ]
    punishment_choices = [
        app_commands.Choice(name="Temporary ban", value="temporary ban"),
        app_commands.Choice(name="Timeout", value="timeout"),
        app_commands.Choice(name="Permanent ban", value="permanent ban"),
    ]

    async def current_ticket(
        interaction: discord.Interaction,
        *,
        claimant_only: bool,
    ) -> tuple[discord.TextChannel, discord.Member] | None:
        channel = interaction.channel
        member = interaction.user
        if not isinstance(channel, discord.TextChannel) or not isinstance(member, discord.Member):
            await interaction.response.send_message(
                embed=error_embed("Use this command inside the ticket you want to control."),
                ephemeral=True,
            )
            return None
        try:
            fresh_channel = await channel.guild.fetch_channel(channel.id)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
            await interaction.response.send_message(
                embed=error_embed(f"I could not load this ticket: {exc}"),
                ephemeral=True,
            )
            return None
        if not isinstance(fresh_channel, discord.TextChannel) or not is_ticket_channel(fresh_channel):
            await interaction.response.send_message(
                embed=error_embed("This command can only be used in the ticket channel that was created for the customer."),
                ephemeral=True,
            )
            return None
        if claimant_only and get_topic_value(
            fresh_channel.topic or "", DM_TICKET_CLAIM_MARKER
        ) != str(member.id):
            await interaction.response.send_message(
                embed=error_embed("Only the support member who claimed this ticket can use `/ticket control`."),
                ephemeral=True,
            )
            return None
        return fresh_channel, member

    async def add_ticket_customer(
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        customer: discord.Member,
    ) -> str:
        await channel.edit(
            topic=set_topic_value(channel.topic or "", DM_TICKET_OWNER_MARKER, str(customer.id)),
            reason=f"Customer added by {interaction.user}",
        )
        try:
            await customer.send(
                f"You have been added to Delta Support ticket **#{channel.name}**. "
                "Reply in this DM to contact the support team."
            )
            delivery = " The customer was notified by DM."
        except (discord.Forbidden, discord.HTTPException):
            delivery = " Their DMs are closed, so they could not be notified."
        await channel.send(f"{interaction.user.mention} added customer {customer.mention} (`{customer.id}`).")
        return f"Added {customer.mention} as the ticket customer.{delivery}"

    async def remove_ticket_customer(
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        customer: discord.Member | None,
    ) -> str:
        owner_id = get_ticket_owner_id(channel)
        if owner_id is None:
            raise ValueError("This ticket does not have a customer to remove.")
        if customer is not None and customer.id != owner_id:
            raise ValueError("The selected member is not this ticket's customer.")
        owner = channel.guild.get_member(owner_id)
        await channel.edit(
            topic=set_topic_value(channel.topic or "", DM_TICKET_OWNER_MARKER, None),
            reason=f"Customer removed by {interaction.user}",
        )
        if owner is not None:
            await channel.set_permissions(owner, overwrite=None)
        label = owner.mention if owner is not None else f"`{owner_id}`"
        await channel.send(f"{interaction.user.mention} removed customer {label}.")
        return f"Removed {label} as the ticket customer."

    async def add_ticket_support(
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        member: discord.Member,
    ) -> str:
        if not (is_staff(member) or is_admin(member)):
            raise ValueError("The selected member must have the support or admin role.")
        support_ids = get_ticket_support_ids(channel.topic or "")
        support_ids.add(member.id)
        await channel.edit(
            topic=set_ticket_support_ids(channel.topic or "", support_ids),
            reason=f"Support member added by {interaction.user}",
        )
        await channel.set_permissions(
            member, view_channel=True, send_messages=True, read_message_history=True
        )
        await channel.send(f"{interaction.user.mention} added support member {member.mention}.")
        return f"Added {member.mention}. They can now use `/reply` in this ticket."

    async def remove_ticket_support(
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        member: discord.Member,
    ) -> str:
        topic = channel.topic or ""
        support_ids = get_ticket_support_ids(topic)
        claimed_id = get_topic_value(topic, DM_TICKET_CLAIM_MARKER)
        if member.id not in support_ids and claimed_id != str(member.id):
            raise ValueError("The selected member is not assigned to this ticket.")
        support_ids.discard(member.id)
        topic = set_ticket_support_ids(topic, support_ids)
        if claimed_id == str(member.id):
            topic = set_topic_value(topic, DM_TICKET_CLAIM_MARKER, None)
        await channel.edit(topic=topic, reason=f"Support member removed by {interaction.user}")
        await channel.set_permissions(member, overwrite=None)
        await channel.send(f"{interaction.user.mention} removed support member {member.mention}.")
        return f"Removed {member.mention} from this ticket."

    @ticket_group.command(name="control", description="Run a control action in your claimed ticket.")
    @staff_only()
    @app_commands.describe(command="The ticket action to run.", member="Customer or support member for this action.")
    @app_commands.choices(command=control_choices)
    async def ticket_control(
        interaction: discord.Interaction,
        command: app_commands.Choice[str],
        member: discord.Member | None = None,
    ) -> None:
        selected = await current_ticket(interaction, claimant_only=True)
        if selected is None:
            return
        channel, actor = selected
        if command.value == "close":
            await interaction.response.send_modal(CloseReasonModal(channel, actor))
            return
        if command.value in {"add_customer", "add_support", "remove_support"} and member is None:
            await interaction.response.send_message(
                embed=error_embed("Select a member for that command."), ephemeral=True
            )
            return
        try:
            if command.value == "add_customer":
                result = await add_ticket_customer(interaction, channel, member)
            elif command.value == "remove_customer":
                result = await remove_ticket_customer(interaction, channel, member)
            elif command.value == "add_support":
                result = await add_ticket_support(interaction, channel, member)
            else:
                result = await remove_ticket_support(interaction, channel, member)
        except (discord.Forbidden, discord.HTTPException, ValueError) as exc:
            await interaction.response.send_message(embed=error_embed(str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(embed=success_embed(result), ephemeral=True)

    @ticket_group.command(name="admin", description="Run an administrative ticket action.")
    @admin_only()
    @app_commands.describe(
        command="The administrative action to run.",
        member="Customer or support member for this action.",
        punishment="Restriction type when using Punish Member.",
        minutes="Restriction length for a temporary punishment.",
    )
    @app_commands.choices(command=admin_choices, punishment=punishment_choices)
    async def ticket_admin(
        interaction: discord.Interaction,
        command: app_commands.Choice[str],
        member: discord.Member | None = None,
        punishment: app_commands.Choice[str] | None = None,
        minutes: app_commands.Range[int, 1, 525600] = 60,
    ) -> None:
        if command.value == "undo":
            if not interaction.client.admin_undo_actions:
                await interaction.response.send_message(
                    embed=error_embed("There is no recent admin action to undo."), ephemeral=True
                )
                return
            record = interaction.client.admin_undo_actions.pop()
            if record[0] == "punish":
                _, user_id, previous = record
                if previous is None:
                    interaction.client.ticket_restrictions.pop(user_id, None)
                else:
                    interaction.client.ticket_restrictions[user_id] = previous
                result = f"Restored the previous ticket restriction state for `{user_id}`."
            else:
                _, channel_id, old_topic, member_id, old_overwrite = record
                target = interaction.client.get_channel(channel_id)
                guild = interaction.guild
                restored_member = guild.get_member(member_id) if guild and member_id else None
                if not isinstance(target, discord.TextChannel):
                    await interaction.response.send_message(
                        embed=error_embed("That ticket action can no longer be undone."), ephemeral=True
                    )
                    return
                await target.edit(topic=old_topic or None, reason=f"Admin action undone by {interaction.user}")
                if restored_member is not None and old_overwrite is not None:
                    await target.set_permissions(restored_member, overwrite=old_overwrite)
                result = f"Restored the previous state of {target.mention}."
            await interaction.response.send_message(embed=success_embed(result), ephemeral=True)
            return

        if command.value in {"punish", "unpunish"}:
            if member is None:
                await interaction.response.send_message(
                    embed=error_embed("Select a member for that command."), ephemeral=True
                )
                return
            previous = interaction.client.ticket_restrictions.get(member.id)
            if command.value == "unpunish":
                interaction.client.admin_undo_actions.append(("punish", member.id, previous))
                interaction.client.ticket_restrictions.pop(member.id, None)
                result = f"Removed all ticket restrictions from {member.mention}."
            else:
                if punishment is None:
                    await interaction.response.send_message(
                        embed=error_embed("Select a punishment type."), ephemeral=True
                    )
                    return
                interaction.client.admin_undo_actions.append(("punish", member.id, previous))
                permanent = punishment.value == "permanent ban"
                expires = None if permanent else time.time() + minutes * 60
                interaction.client.ticket_restrictions[member.id] = (punishment.value, expires)
                duration = "permanently" if permanent else f"for {minutes} minute(s)"
                result = f"{member.mention} received a {punishment.value} {duration}."
            await interaction.response.send_message(embed=success_embed(result), ephemeral=True)
            return

        selected = await current_ticket(interaction, claimant_only=False)
        if selected is None:
            return
        channel, actor = selected
        if command.value == "close":
            await interaction.response.send_modal(CloseReasonModal(channel, actor))
            return
        if command.value in {"add_customer", "add_support", "remove_support", "claim"} and member is None:
            await interaction.response.send_message(
                embed=error_embed("Select a member for that command."), ephemeral=True
            )
            return

        old_topic = channel.topic or ""
        old_overwrite = channel.overwrites_for(member) if member is not None else None
        interaction.client.admin_undo_actions.append(
            ("ticket", channel.id, old_topic, member.id if member else None, old_overwrite)
        )
        try:
            if command.value == "add_customer":
                result = await add_ticket_customer(interaction, channel, member)
            elif command.value == "remove_customer":
                result = await remove_ticket_customer(interaction, channel, member)
            elif command.value == "add_support":
                result = await add_ticket_support(interaction, channel, member)
            elif command.value == "remove_support":
                result = await remove_ticket_support(interaction, channel, member)
            elif command.value == "claim":
                if not (is_staff(member) or is_admin(member)):
                    raise ValueError("The selected member must have the support or admin role.")
                topic = set_topic_value(channel.topic or "", DM_TICKET_CLAIM_MARKER, str(member.id))
                await channel.edit(topic=topic, reason=f"Ticket assigned by {interaction.user}")
                result = f"Assigned this ticket to {member.mention}."
            else:
                topic = set_topic_value(channel.topic or "", DM_TICKET_CLAIM_MARKER, None)
                await channel.edit(topic=topic, reason=f"Ticket unclaimed by {interaction.user}")
                result = "Removed the current ticket claim."
        except (discord.Forbidden, discord.HTTPException, ValueError) as exc:
            interaction.client.admin_undo_actions.pop()
            await interaction.response.send_message(embed=error_embed(str(exc)), ephemeral=True)
            return
        await interaction.response.send_message(embed=success_embed(result), ephemeral=True)

    tree.add_command(ticket_group)

    # Global error handler
    @tree.error
    async def on_app_command_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                embed=error_embed(
                    "You do not have permission to use this command.\n"
                    "This command is restricted to **Delta Air Lines Staff** only."
                ),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=error_embed(f"An unexpected error occurred: {error}"),
                ephemeral=True,
            )


# ═══════════════════���════════════════════════════════════════════════════════════
# BOT CLASS & ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("delta-helpdesk")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.moderation = True


class DeltaCommandTree(app_commands.CommandTree):
    """Command tree that safely replaces stale or duplicate local commands."""

    def add_command(self, command, *args, **kwargs) -> None:
        # A previously mis-resolved merge left duplicate decorators in the
        # deployed source. Enforce replacement at the tree itself so no command
        # decorator can crash startup with CommandAlreadyRegistered.
        kwargs["override"] = True
        super().add_command(command, *args, **kwargs)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Reject application commands invoked outside the configured server."""
        return interaction.guild_id == GUILD_ID


class DeltaBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            tree_cls=DeltaCommandTree,
        )
        self._dm_prompted_users: set[int] = set()
        # Runtime ticket sanctions. Values are (kind, UNIX expiry); None expiry is permanent.
        self.ticket_restrictions: dict[int, tuple[str, float | None]] = {}
        self.admin_undo_actions: list[tuple] = []
        self.processed_dm_messages: set[int] = set()
        self.processed_reply_interactions: set[int] = set()
        self.started_monotonic = time.monotonic()

    async def setup_hook(self) -> None:
        self.add_view(TicketActionView())
        self.add_view(ServerAssistancePanelView(self))
        register_commands(self.tree)
        target_guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=target_guild)
        self.tree.clear_commands(guild=None)
        await self.tree.sync()
        synced = await self.tree.sync(guild=target_guild)
        log.info("Synced %d application command(s) to guild %s.", len(synced), GUILD_ID)

    async def on_ready(self) -> None:
        global XMARK_EMOJI
        # Resolve the server-owned X mark once so every later error embed uses
        # the same custom status language as successful CheckMark responses.
        XMARK_EMOJI = delta_status_emoji(self.get_guild(GUILD_ID), success=False)
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id if self.user else "unknown")
        log.info(
            "Delta Air Lines HelpDesk %s is online | branch=%s | commit=%s | host=%s.",
            BOT_VERSION,
            deployed_branch(),
            deployed_source(),
            hosting_environment(),
        )
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                # Discord activity names do not render custom emoji markup.
                name="Delta Air Lines Support",
            )
        )

        authorized_guild = self.get_guild(GUILD_ID)
        self._validate_startup_configuration(authorized_guild)
        await self._post_release_update()

        for guild in self.guilds:
            if guild.id != GUILD_ID:
                log.warning(
                    "Ignoring unauthorized guild %s (%s); no commands are synced there.",
                    guild.name,
                    guild.id,
                )

    def _validate_startup_configuration(self, guild: discord.Guild | None) -> None:
        """Log every invalid Discord resource ID without stopping the bot."""
        if guild is None:
            log.warning(
                "Startup validation: guild %s was not found; all dependent resources are unavailable.",
                GUILD_ID,
            )
            return

        checks = (
            ("ticket category", TICKET_CATEGORY_ID, discord.CategoryChannel),
            ("transcript/log channel", TRANSCRIPT_CHANNEL_ID, discord.TextChannel),
        )
        invalid = False
        for label, resource_id, expected_type in checks:
            resource = guild.get_channel(resource_id)
            if not isinstance(resource, expected_type):
                invalid = True
                log.warning(
                    "Startup validation: configured %s ID %s is missing or has the wrong type.",
                    label,
                    resource_id,
                )
        for label, role_id in (("staff role", STAFF_ROLE_ID), ("admin role", ADMIN_ROLE_ID)):
            if guild.get_role(role_id) is None:
                invalid = True
                log.warning(
                    "Startup validation: configured %s ID %s was not found.",
                    label,
                    role_id,
                )
        if not invalid:
            log.info("Startup validation passed for guild %s (%s).", guild.name, guild.id)

    async def _post_release_update(self) -> None:
        """Post this release once to the update/transcript channel."""
        channel = self.get_channel(UPDATE_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            try:
                fetched = await self.fetch_channel(UPDATE_CHANNEL_ID)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
                log.warning("Could not find update channel %s: %s", UPDATE_CHANNEL_ID, exc)
                return
            channel = fetched if isinstance(fetched, discord.TextChannel) else None
        if channel is None or channel.guild.id != GUILD_ID or self.user is None:
            return

        marker = f"Update {BOT_VERSION}"
        try:
            pinned = await channel.pins()
            recent = [message async for message in channel.history(limit=200)]
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning("Could not check existing update announcements: %s", exc)
            return
        if any(
            message.author.id == self.user.id and marker in message.content
            for message in (*pinned, *recent)
        ):
            return

        try:
            announcement = await channel.send(UPDATE_MESSAGE)
            try:
                await announcement.pin(reason=f"Delta Support Bot release {BOT_VERSION}")
            except (discord.Forbidden, discord.HTTPException):
                log.warning("Posted update %s but could not pin it.", BOT_VERSION)
            log.info("Posted release update %s to channel %s.", BOT_VERSION, UPDATE_CHANNEL_ID)
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.warning("Could not post release update %s: %s", BOT_VERSION, exc)

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Keep unauthorized guilds inert without ever removing the bot itself."""
        if guild.id != GUILD_ID:
            log.warning(
                "Joined unauthorized guild %s (%s); commands and tickets are disabled there.",
                guild.name,
                guild.id,
            )

    def _is_lounge(self, channel: discord.abc.GuildChannel | discord.Thread) -> bool:
        if channel.guild.id != GUILD_ID:
            return False
        if LOUNGE_CHANNEL_ID:
            return channel.id == LOUNGE_CHANNEL_ID
        return isinstance(channel, discord.TextChannel) and channel.name.casefold() == "lounge"

    async def _send_server_log(
        self,
        title: str,
        description: str,
        *,
        color: int = DELTA_BLUE,
    ) -> None:
        """Send a server event to the configured logs channel without disrupting it."""
        channel = self.get_channel(TRANSCRIPT_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            log.warning("Could not write %s log: channel %s is unavailable.", title, TRANSCRIPT_CHANNEL_ID)
            return
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text=FOOTER_TEXT)
        embed.timestamp = discord.utils.utcnow()
        try:
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
            log.warning("Could not write %s log: %s", title, exc)

    async def _moderate_lounge_message(self, message: discord.Message) -> bool:
        """Delete configured offensive language in #lounge and record the action."""
        if not isinstance(message.channel, discord.TextChannel) or not self._is_lounge(message.channel):
            return False
        blocked_term = find_blocked_term(message.content)
        if blocked_term is None:
            return False

        self._automod_deletions.add(message.id)
        if len(self._automod_deletions) > 10_000:
            self._automod_deletions.pop()
        try:
            await message.delete(reason="Delta AutoMod: offensive language in #lounge")
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
            self._automod_deletions.discard(message.id)
            log.warning("AutoMod could not delete message %s: %s", message.id, exc)
            return False

        try:
            await message.channel.send(
                f"{message.author.mention}, that message was removed because offensive language "
                "is not allowed in this channel.",
                delete_after=8,
                allowed_mentions=discord.AllowedMentions(users=True),
            )
        except (discord.Forbidden, discord.HTTPException):
            log.warning("AutoMod removed message %s but could not post its warning.", message.id)

        await self._send_server_log(
            "AutoMod Action",
            f"**Member:** {message.author} (`{message.author.id}`)\n"
            f"**Channel:** {message.channel.mention}\n"
            f"**Matched rule:** `{blocked_term}`\n"
            f"**Message:** {safe_log_text(message.content)}",
            color=DELTA_RED,
        )
        return True

    async def on_member_join(self, member: discord.Member) -> None:
        if member.guild.id == GUILD_ID:
            await self._send_server_log(
                "Member Joined",
                f"**Member:** {member.mention} (`{member.id}`)\n"
                f"**Account created:** {discord.utils.format_dt(member.created_at, 'F')}",
            )

    async def on_member_remove(self, member: discord.Member) -> None:
        if member.guild.id == GUILD_ID:
            await self._send_server_log(
                "Member Left",
                f"**Member:** {member} (`{member.id}`)",
                color=DELTA_RED,
            )

    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        if guild.id == GUILD_ID:
            await self._send_server_log(
                "Moderation — Member Banned",
                f"**Member:** {user} (`{user.id}`)",
                color=DELTA_RED,
            )

    async def on_member_unban(self, guild: discord.Guild, user: discord.User) -> None:
        if guild.id == GUILD_ID:
            await self._send_server_log(
                "Moderation — Member Unbanned",
                f"**Member:** {user} (`{user.id}`)",
            )

    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        if after.guild.id != GUILD_ID:
            return
        changes: list[str] = []
        if before.nick != after.nick:
            changes.append(f"**Nickname:** `{before.nick or before.name}` → `{after.nick or after.name}`")
        if before.roles != after.roles:
            before_ids = {role.id for role in before.roles}
            after_ids = {role.id for role in after.roles}
            added = [role.mention for role in after.roles if role.id not in before_ids]
            removed = [role.name for role in before.roles if role.id not in after_ids]
            if added:
                changes.append(f"**Roles added:** {', '.join(added)}")
            if removed:
                changes.append(f"**Roles removed:** {', '.join(removed)}")
        if before.timed_out_until != after.timed_out_until:
            timeout = (
                discord.utils.format_dt(after.timed_out_until, "F")
                if after.timed_out_until is not None
                else "Removed"
            )
            changes.append(f"**Timeout:** {timeout}")
        if changes:
            await self._send_server_log(
                "Moderation — Member Updated",
                f"**Member:** {after.mention} (`{after.id}`)\n" + "\n".join(changes),
            )

    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if (
            before.guild is None
            or before.guild.id != GUILD_ID
            or before.author.bot
            or before.content == after.content
        ):
            return
        if await self._moderate_lounge_message(after):
            return
        await self._send_server_log(
            "Message Edited",
            f"**Member:** {after.author} (`{after.author.id}`)\n"
            f"**Channel:** {after.channel.mention}\n"
            f"**Before:** {safe_log_text(before.content)}\n"
            f"**After:** {safe_log_text(after.content)}\n"
            f"[Jump to message]({after.jump_url})",
        )

    async def on_message_delete(self, message: discord.Message) -> None:
        if message.id in self._automod_deletions:
            self._automod_deletions.discard(message.id)
            return
        if message.guild is None or message.guild.id != GUILD_ID or message.author.bot:
            return
        await self._send_server_log(
            "Message Deleted",
            f"**Member:** {message.author} (`{message.author.id}`)\n"
            f"**Channel:** {message.channel.mention}\n"
            f"**Message:** {safe_log_text(message.content)}",
            color=DELTA_RED,
        )

    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        """Record uncached deletions that do not produce on_message_delete."""
        if payload.cached_message is not None or payload.guild_id != GUILD_ID:
            return
        if payload.message_id in self._automod_deletions:
            self._automod_deletions.discard(payload.message_id)
            return
        channel = self.get_channel(payload.channel_id)
        channel_text = getattr(channel, "mention", f"`{payload.channel_id}`")
        await self._send_server_log(
            "Message Deleted",
            f"**Message ID:** `{payload.message_id}`\n"
            f"**Channel:** {channel_text}\n"
            "**Message:** *(content was not cached)*",
            color=DELTA_RED,
        )

    async def on_message(self, message: discord.Message) -> None:
        """Relay customer DMs and claimed support-channel replies."""
        if message.author.bot:
            return

        if message.guild is not None and await self._moderate_lounge_message(message):
            return

        if isinstance(message.channel, discord.DMChannel):
            if message.id in self.processed_dm_messages:
                return
            self.processed_dm_messages.add(message.id)
            if len(self.processed_dm_messages) > 10_000:
                self.processed_dm_messages.pop()

            target_guild = self.get_guild(GUILD_ID)
            if target_guild is None:
                await message.channel.send(embed=error_embed("I could not connect your ticket just now. Please try again shortly."))
                return
            try:
                member = target_guild.get_member(message.author.id) or await target_guild.fetch_member(
                    message.author.id
                )
            except discord.NotFound:
                await message.channel.send(NON_MEMBER_MESSAGE, view=NonMemberView(self, message.author.id))
                return
            except discord.HTTPException as exc:
                log.warning("Could not verify server membership for %s: %s", message.author.id, exc)
                await message.channel.send(embed=error_embed("I could not verify your server membership."))
                return

            category = self.get_channel(TICKET_CATEGORY_ID)
            if (
                not isinstance(category, discord.CategoryChannel)
                or category.guild.id != target_guild.id
            ):
                await message.channel.send(embed=error_embed("I could not connect your ticket just now. Please try again shortly."))
                return

            restriction = self.ticket_restrictions.get(message.author.id)
            if restriction is not None:
                kind, expires_at = restriction
                if expires_at is None or expires_at > time.time():
                    duration = "permanently" if expires_at is None else f"for another {max(1, int((expires_at - time.time()) / 60) + 1)} minute(s)"
                    await message.channel.send(f"You have been **{kind}** from creating tickets {duration}.")
                    return
                self.ticket_restrictions.pop(message.author.id, None)

            ticket = await find_existing_ticket(category.guild, member)
            if ticket is not None:
                try:
                    await relay_customer_message(message, ticket)
                except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
                    log.error("Could not relay DM from %s: %s", message.author.id, exc)
                    await message.channel.send(embed=error_embed("I could not forward that message. Please try again."))
                return

            if message.author.id not in self._dm_prompted_users:
                self._dm_prompted_users.add(message.author.id)
                await message.channel.send(
                    "<:Support:1540927430179553321> **Choose one assistance category below.**\n"
                    "Your conversation stays in this DM while Delta Support responds from a private channel.",
                    view=DMAssistancePanelView(self, message.author.id),
                )
            return

        if isinstance(message.channel, discord.TextChannel):
            # Ticket-channel chat is internal discussion. Only /reply deliberately
            # sends content to the customer, so ordinary staff messages receive no
            # relay, reaction, or warning.
            return



def run_health_server() -> None:
    """Tiny HTTP server so Render's free Web Service sees an open port."""
    port = int(os.getenv("PORT", "8080"))

    class Handler(BaseHTTPRequestHandler):
        _HTML = b"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Delta Air Lines HelpDesk &mdash; Status</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0a0a0a;
      color: #f0f0f0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 24px;
    }
    .card {
      background: #161616;
      border: 1px solid #2a2a2a;
      border-radius: 12px;
      padding: 40px 48px;
      text-align: center;
      max-width: 440px;
      width: 90%;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      background: #0f2e1a;
      color: #4ade80;
      border: 1px solid #166534;
      border-radius: 999px;
      padding: 6px 16px;
      font-size: 13px;
      font-weight: 600;
      margin-bottom: 20px;
    }
    .dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      background: #4ade80;
      animation: pulse 2s ease-in-out infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.3; }
    }
    h1 {
      font-size: 22px;
      font-weight: 700;
      color: #ffffff;
      margin-bottom: 8px;
    }
    .airline {
      color: #C8102E;
      font-weight: 800;
    }
    p {
      font-size: 14px;
      color: #888;
      line-height: 1.6;
    }
    .divider {
      height: 3px;
      background: linear-gradient(90deg, #C8102E, #003087);
      border-radius: 2px;
      margin-top: 28px;
    }
    footer {
      font-size: 12px;
      color: #444;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="badge"><span class="dot"></span>All Systems Operational</div>
    <h1><span class="airline">Delta Air Lines</span><br>HelpDesk Bot</h1>
    <p>The Discord support bot is running and actively serving tickets.<br>Version __BOT_VERSION__ &bull; Source __SOURCE__<br>Keep Climbing.</p>
    <div class="divider"></div>
  </div>
  <footer>Delta Air Lines &mdash; Automated Service Monitor</footer>
</body>
</html>"""

        def _body(self) -> bytes:
            return self._HTML.replace(
                b"__BOT_VERSION__", BOT_VERSION.encode("ascii")
            ).replace(b"__SOURCE__", deployed_source().encode("ascii"))

        def _send_headers(self, body: bytes) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("X-Delta-Bot-Version", BOT_VERSION)
            self.send_header("X-Git-Commit", deployed_source())
            self.end_headers()

        def do_GET(self) -> None:
            body = self._body()
            self._send_headers(body)
            self.wfile.write(body)

        def do_HEAD(self) -> None:
            self._send_headers(self._body())

        def log_message(self, *args) -> None:
            pass  # Silence HTTP access logs

    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


def run_bot_forever(token: str) -> None:
    """Restart the Discord client when a temporary network failure stops it."""
    while True:
        bot = DeltaBot()
        try:
            bot.run(token, log_handler=None)
        except discord.LoginFailure:
            # A revoked or malformed token requires an operator to update Render.
            raise
        except (aiohttp.ClientError, discord.HTTPException, OSError) as exc:
            log.error(
                "Discord connection stopped (%s). Restarting in %d seconds.",
                exc,
                DISCORD_RECONNECT_DELAY,
            )
            time.sleep(DISCORD_RECONNECT_DELAY)
        else:
            log.info("Discord client shut down normally.")
            return


def main() -> None:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError(
            "DISCORD_TOKEN is not set. Copy .env.example to .env and fill in your bot token."
        )

    # Start the health-check server in a background thread
    thread = threading.Thread(target=run_health_server, daemon=True)
    thread.start()
    log.info(
        "Starting Delta Air Lines HelpDesk %s | branch=%s | commit=%s | host=%s.",
        BOT_VERSION,
        deployed_branch(),
        deployed_source(),
        hosting_environment(),
    )
    log.info("Health-check server started.")

    run_bot_forever(token)


if __name__ == "__main__":
    main()
