"""
Delta Air Lines HelpDesk Discord Bot — Single-file version
All configuration, embeds, views, and commands in one file.

Usage:
    python main.py

Requires a .env file with:
    DISCORD_TOKEN=your_bot_token_here
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# ════════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════════

DELTA_RED       = 0xC8102E
FOOTER_TEXT     = "Delta Air Lines • Keep Climbing"
MAILING_ADDRESS = "P.O. Box 20980, Department 980, Atlanta, GA 30320-2980"

BANNER_URL = os.getenv("BANNER_URL", "")
DIVIDER_URL = os.getenv("DIVIDER_URL", "")

GUILD_ID = 1538738611988467782
TICKET_CATEGORY_ID = 1543674278711529562
STAFF_ROLE_ID = 1539005030189891684

# Backward-compatible name used by earlier command permission checks.
BOT_COMMAND_ROLE_ID = STAFF_ROLE_ID

PARTNERSHIP_REPRESENTATIVES_ROLE_ID = 1528809872672690247
TRANSCRIPT_CHANNEL_ID = 1543674377953087649
UPDATES_CHANNEL_ID = 1524489806711754752
UPDATES_ROLE_ID = 1530210954422518042
TICKET_CLOSE_DELAY      = 5
RATING_TIMEOUT          = 15 * 24 * 60 * 60
DISCORD_RECONNECT_DELAY = 15
DM_TICKET_OWNER_MARKER  = "Delta DM Ticket Owner:"
DM_TICKET_CATEGORY_MARKER = "Delta Ticket Category:"
DM_TICKET_CLAIM_MARKER  = "Delta Ticket Claimed By:"

# Each key maps to a ticket category. Add new rows here to add new categories.
TICKET_CONFIG: dict[str, dict] = {
    "general_inquiries": {
        "label":       "General Inquiries",
        "prefix":      "general-support",
        "role_id":     STAFF_ROLE_ID,
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


def assistance_panel_banner_embed() -> discord.Embed:
    embed = discord.Embed(color=DELTA_RED)
    _set_brand_image(embed, BANNER_URL)
    return embed


def assistance_panel_embed() -> discord.Embed:
    embed = _base_embed(
        title="✈️  Delta Air Lines — HelpDesk",
        description=(
            "Welcome to the **Delta Air Lines Support Centre**.\n\n"
            "Our dedicated team is here to assist you with any questions, "
            "concerns, or requests you may have. Select the category that best "
            "matches your request below.\n\n"
            "For your privacy, the conversation will not take place in this channel. "
            "The bot will send you a direct message asking you to confirm the ticket, "
            "and all further communication will remain in your DMs."
        ),
    )
    embed.add_field(
        name="🔐 Private & Secure",
        value="Only you and the assigned Delta Support team can take part in the conversation.",
        inline=False,
    )
    embed.add_field(
        name="📨 Before You Begin",
        value="Please make sure your Discord privacy settings allow direct messages from this server.",
        inline=False,
    )
    embed.add_field(name="📬 Mailing Address", value=MAILING_ADDRESS, inline=False)
    _set_brand_image(embed, DIVIDER_URL)
    return embed


def general_inquiries_welcome(member: discord.Member) -> discord.Embed:
    embed = _base_embed(
        title="📋  General Inquiries | Support Ticket",
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
    embed.add_field(name="📬 Mailing Address", value=MAILING_ADDRESS, inline=False)
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
    embed.add_field(name="📬 Mailing Address", value=MAILING_ADDRESS, inline=False)
    _set_brand_image(embed, DIVIDER_URL)
    return embed


def ticket_closed_dm(ticket_name: str) -> discord.Embed:
    embed = _base_embed(
        title="🔒  Ticket Closed",
        description=(
            f"Your support ticket **#{ticket_name}** has been successfully closed.\n\n"
            "Thank you for contacting **Delta Air Lines Support**. "
            "We hope we were able to assist you today. "
            "If you need further assistance, please don't hesitate to open a new ticket.\n\n"
            "*Delta Air Lines — Keep Climbing.*"
        ),
    )
    embed.add_field(name="📬 Mailing Address", value=MAILING_ADDRESS, inline=False)
    _set_brand_image(embed, DIVIDER_URL)
    return embed


def ticket_closed_channel() -> discord.Embed:
    embed = _base_embed(
        title="🔒  Ticket Closing",
        description=(
            f"This ticket has been marked as **closed** and will be deleted in "
            f"**{TICKET_CLOSE_DELAY} seconds**.\n\n"
            "Thank you for contacting Delta Air Lines Support."
        ),
    )
    _set_brand_image(embed, DIVIDER_URL)
    return embed


def already_open_ticket(channel: discord.TextChannel) -> discord.Embed:
    embed = _base_embed(
        title="⚠️  Active Ticket Found",
        description=(
            f"You already have an open support ticket: {channel.mention}\n\n"
            "Please continue your conversation there. "
            "If you believe this is an error, contact a staff member."
        ),
    )
    return embed


def error_embed(message: str) -> discord.Embed:
    embed = discord.Embed(title="❌  Error", description=message, color=DELTA_RED)
    embed.set_footer(text=FOOTER_TEXT)
    return embed


def success_embed(message: str) -> discord.Embed:
    embed = discord.Embed(title="✅  Success", description=message, color=DELTA_RED)
    embed.set_footer(text=FOOTER_TEXT)
    return embed


# ════════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ════════════════════════════════════════════════════════════════════════════════

def is_staff(member: discord.Member) -> bool:
    return any(role.id == BOT_COMMAND_ROLE_ID for role in member.roles)


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
    return is_staff(member) or get_ticket_owner_id(channel) == member.id


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
    parts.extend(f"📎 [{attachment.filename}]({attachment.url})" for attachment in message.attachments)
    description = "\n".join(parts) or "*(No text content)*"
    return description if len(description) <= 4000 else f"{description[:3997]}..."


async def relay_customer_message(message: discord.Message, channel: discord.TextChannel) -> None:
    embed = _base_embed(
        title="📨  New Customer Message",
        description=relay_description(message),
    )
    embed.set_author(name=str(message.author), icon_url=message.author.display_avatar.url)
    embed.add_field(name="Customer ID", value=str(message.author.id), inline=False)
    _set_brand_image(embed, DIVIDER_URL)
    embed.timestamp = message.created_at
    await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    await message.add_reaction("✅")


async def relay_support_message(
    client: discord.Client,
    message: discord.Message,
    owner_id: str,
) -> None:
    try:
        user = client.get_user(int(owner_id)) or await client.fetch_user(int(owner_id))
        embed = _base_embed(
            title="💬  Delta Support Reply",
            description=relay_description(message),
        )
        display_name = getattr(message.author, "display_name", message.author.name)
        embed.set_author(name=display_name, icon_url=message.author.display_avatar.url)
        embed.add_field(
            name="Private Support Conversation",
            value="Reply directly in this DM to send another message to your assigned support agent.",
            inline=False,
        )
        _set_brand_image(embed, DIVIDER_URL)
        embed.timestamp = message.created_at
        await user.send(embed=embed)
        await message.add_reaction("✅")
    except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
        await message.add_reaction("❌")
        log.warning("Could not relay support message to %s: %s", owner_id, exc)


async def open_dm_ticket(
    bot: "DeltaBot",
    user: discord.abc.User,
    category_key: str,
) -> discord.TextChannel:
    """Create and introduce a staff relay channel for a confirmed DM ticket."""
    category = bot.get_channel(TICKET_CATEGORY_ID)
    if not isinstance(category, discord.CategoryChannel):
        raise ValueError("The configured ticket category could not be found.")
    guild = category.guild
    existing = await find_existing_ticket(guild, user)
    if existing is not None:
        return existing

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
            "3. A ✅ confirms delivery to the customer."
        ),
        inline=False,
    )
    _set_brand_image(embed, DIVIDER_URL)
    await channel.send(embed=embed, view=TicketActionView())
    return channel


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
    rating_line = f"{rating} / 5 ⭐" if rating is not None else "No rating given"
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
        stars = "⭐" * rating if rating else "—"
        log_embed = _base_embed(
            title="📋  Ticket Transcript",
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
                title="⭐  Rate Your Support Experience",
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
        ("1 ⭐", 1, discord.ButtonStyle.secondary),
        ("2 ⭐", 2, discord.ButtonStyle.secondary),
        ("3 ⭐", 3, discord.ButtonStyle.secondary),
        ("4 ⭐", 4, discord.ButtonStyle.success),
        ("5 ⭐", 5, discord.ButtonStyle.success),
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
                label=label, style=style, custom_id=f"delta:rating:{value}"
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
                title="✅  Rating Submitted",
                description=(
                    f"Thank you! You rated your support experience **{stars} / 5 ⭐**.\n\n"
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
        rating_line = f"**Rating:** {'⭐' * stars} ({stars} / 5 ⭐)"
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
            self.claim_ticket.label = "🙋  Unclaim Ticket"
            self.claim_ticket.style = discord.ButtonStyle.secondary

    # ── Claim / Unclaim ────────────────────────────────────────────────────────────
    @discord.ui.button(
        label="🙋  Claim Ticket",
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

        # Serialise claim changes per channel so two agents cannot claim the same
        # ticket at the same time.
        lock = self._claim_locks.setdefault(channel.id, asyncio.Lock())
        async with lock:
            topic = channel.topic or ""
            claimed_id = get_topic_value(topic, DM_TICKET_CLAIM_MARKER)
            owner_id = get_topic_value(topic, DM_TICKET_OWNER_MARKER)
            if claimed_id is not None and claimed_id != str(member.id):
                await interaction.response.send_message(
                    embed=error_embed("This ticket has already been claimed by another support agent."),
                    ephemeral=True,
                )
                return

            unclaiming = claimed_id == str(member.id)
            new_claim = None if unclaiming else str(member.id)
            await channel.edit(
                topic=set_topic_value(topic, DM_TICKET_CLAIM_MARKER, new_claim),
                reason=f"Ticket {'unclaimed' if unclaiming else 'claimed'} by {member}",
            )

        if unclaiming:
            await interaction.response.send_message(
                embed=success_embed("You have unclaimed this ticket."), ephemeral=True
            )
            status_embed = _base_embed(
                title="🔓  Ticket Unclaimed",
                description=f"This ticket has been unclaimed by {member.mention}.",
            )
            owner_title = "🔓  Support Agent Disconnected"
            owner_message = (
                "The support agent handling your ticket has unclaimed it. "
                "Another agent can now assist you."
            )
        else:
            await interaction.response.send_message(
                embed=success_embed("You have claimed this ticket."), ephemeral=True
            )
            status_embed = _base_embed(
                title="🙋  Ticket Claimed",
                description=(
                    f"This ticket has been claimed by {member.mention}.\n\n"
                    "They will be assisting the customer through the DM relay."
                ),
            )
            owner_title = "🙋  Support Agent Connected"
            owner_message = (
                f"**{member.display_name}** has claimed your ticket and will now assist you here in DMs."
            )

        _set_brand_image(status_embed, DIVIDER_URL)
        await channel.send(embed=status_embed)
        if interaction.message is not None:
            await interaction.message.edit(view=TicketActionView(claimed=not unclaiming))
        await notify_ticket_owner(
            interaction.client, owner_id, owner_title, owner_message
        )

    # ── Close ──────────────────────────────────────────────────────────────────────
    @discord.ui.button(
        label="🔒  Close Ticket",
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
            placeholder="✈️  Select an Assistance Category",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="delta:assistance_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        user = interaction.user
        if user.id != self.user_id:
            await interaction.followup.send(
                embed=error_embed("This assistance panel belongs to another user."),
            )
            return

        category = self.bot.get_channel(TICKET_CATEGORY_ID)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(embed=error_embed("The ticket system is unavailable right now."))
            return
        guild = category.guild

        selected_key = self.values[0]
        cfg = TICKET_CONFIG[selected_key]

        # Discord keeps a user's last selection highlighted unless the source
        # message is refreshed. Replace the view immediately so this member can
        # select the same category again after their ticket is closed.
        if interaction.message is not None:
            try:
                await interaction.message.edit(view=DMAssistancePanelView(self.bot, user.id))
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                log.warning("Unable to reset assistance dropdown on message %s", interaction.message.id)

        try:
            await open_dm_ticket(self.bot, user, selected_key)
        except Exception as exc:
            self.bot._dm_prompted_users.discard(user.id)
            await interaction.followup.send(
                embed=error_embed(f"Failed to create your ticket: {exc}"),
            )
            return

        self.bot._dm_prompted_users.discard(user.id)
        await interaction.followup.send(
            embed=success_embed(
                f"Your **{cfg['label']}** ticket is open. Send your next message in this DM and I will forward it to support."
            ),
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
    """Public panel selector that moves the confirmation into the user's DMs."""

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
            placeholder="✈️  Select an Assistance Category",
            options=options,
            custom_id="delta:server_assistance_select",
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        selected_key = self.values[0]
        cfg = TICKET_CONFIG[selected_key]
        prompt = _base_embed(
            title="✈️  Confirm Your Private Support Request",
            description=(
                f"You selected **{cfg['label']}** from the Delta Assistance Panel.\n\n"
                "Would you like us to create a private support ticket? Your conversation "
                "will take place entirely in this DM and will only be shared with the "
                "appropriate Delta Support team."
            ),
        )
        prompt.add_field(
            name="Selected Department",
            value=f"{cfg['emoji']} {cfg['label']}",
            inline=False,
        )
        _set_brand_image(prompt, DIVIDER_URL)
        try:
            await interaction.user.send(
                embed=prompt,
                view=DMTicketPromptView(self.bot, interaction.user.id, selected_key),
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed(
                    "I could not send you a DM. Enable direct messages from server members and try again."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=success_embed(
                "I sent a private confirmation to your DMs. Open it and choose **Yes, make a ticket** to continue."
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


class DMTicketPromptView(discord.ui.View):
    def __init__(
        self,
        bot: "DeltaBot",
        user_id: int,
        category_key: str | None = None,
    ) -> None:
        super().__init__(timeout=600)
        self.bot = bot
        self.user_id = user_id
        self.category_key = category_key

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(embed=error_embed("This prompt belongs to another user."))
        return False

    @discord.ui.button(label="✅ Yes, make a ticket", style=discord.ButtonStyle.success)
    async def yes(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if self.category_key is not None:
            cfg = TICKET_CONFIG[self.category_key]
            await interaction.response.defer()
            try:
                await open_dm_ticket(self.bot, interaction.user, self.category_key)
            except Exception as exc:
                self.bot._dm_prompted_users.discard(self.user_id)
                await interaction.followup.send(
                    embed=error_embed(f"Your private ticket could not be created: {exc}")
                )
                return
            self.bot._dm_prompted_users.discard(self.user_id)
            confirmation = _base_embed(
                title="✅  Your Private Support Ticket Is Open",
                description=(
                    f"Your request has been routed to **{cfg['label']}**. A support agent "
                    "will review it as soon as possible.\n\n"
                    "Continue by sending your question, details, and any relevant attachments "
                    "directly in this DM. A ✅ reaction means your message was delivered to support."
                ),
            )
            confirmation.add_field(
                name="What Happens Next?",
                value="An agent will claim your ticket, and their replies will appear here automatically.",
                inline=False,
            )
            _set_brand_image(confirmation, DIVIDER_URL)
            await interaction.edit_original_response(embed=confirmation, view=None)
            self.stop()
            return

        await interaction.response.edit_message(
            embed=_base_embed(
                title="📋  Choose Your Support Department",
                description=(
                    "Select the category that best matches your request. This helps us route "
                    "your private conversation to the right support team without delay."
                ),
            ),
            view=None,
        )
        await interaction.followup.send(embed=assistance_panel_banner_embed())
        await interaction.followup.send(
            embed=assistance_panel_embed(),
            view=DMAssistancePanelView(self.bot, self.user_id),
        )
        self.stop()

    @discord.ui.button(label="❌ No, not now", style=discord.ButtonStyle.secondary)
    async def no(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.bot._dm_prompted_users.discard(self.user_id)
        await interaction.response.edit_message(
            embed=success_embed("No ticket was created. You can message me again whenever you need support."),
            view=None,
        )
        self.stop()

    async def on_timeout(self) -> None:
        self.bot._dm_prompted_users.discard(self.user_id)


# ════════════════════════════════════════════════════════════════════════════════
# SLASH COMMANDS
# ════════════════════════════════════════════════════════════════════════════════

def staff_only() -> app_commands.check:
    async def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not isinstance(member, discord.Member):
            return False
        return is_staff(member)
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
        "connected",
        "resolved",
        "revoke",
    ):
        tree.remove_command(command_name, type=discord.AppCommandType.chat_input)

    @tree.command(
        name="panel",
        description="Post the private DM Assistance Panel in this channel.",
    )
    @staff_only()
    async def panel(interaction: discord.Interaction) -> None:
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("The Assistance Panel can only be posted in a server text channel."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(
            embed=success_embed("The private DM Assistance Panel was posted successfully."),
            ephemeral=True,
        )
        await interaction.channel.send(embed=assistance_panel_banner_embed())
        await interaction.channel.send(
            embed=assistance_panel_embed(),
            view=ServerAssistancePanelView(interaction.client),
        )

    async def post_positions(
        interaction: discord.Interaction,
        message: str,
    ) -> None:
        """Post a position list publicly from a staff-only slash command."""
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("This command can only be used in a text channel."),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(message)

    @tree.command(name="hr", description="Post the available Human Resources positions.")
    @staff_only()
    async def hr(interaction: discord.Interaction) -> None:
        await post_positions(interaction, HR_POSITIONS_MESSAGE)

    @tree.command(name="leadership", description="Post the available leadership positions.")
    @staff_only()
    async def leadership(interaction: discord.Interaction) -> None:
        await post_positions(interaction, LEADERSHIP_POSITIONS_MESSAGE)

    # /tickets — register an existing channel with the ticket system
    ticket_category_choices = [
        app_commands.Choice(name=cfg["label"], value=key)
        for key, cfg in TICKET_CONFIG.items()
    ]

    @tree.command(name="tickets", description="Add or remove a channel from the ticket system.")
    @staff_only()
    @app_commands.describe(
        channel="The channel to configure.",
        action="Whether to add or remove the channel.",
        category="The kind of tickets handled in this channel.",
    )
    @app_commands.choices(
        action=[
            app_commands.Choice(name="Add", value="add"),
            app_commands.Choice(name="Remove", value="remove"),
        ],
        category=ticket_category_choices,
    )
    async def tickets(
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        action: app_commands.Choice[str],
        category: app_commands.Choice[str],
    ) -> None:
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                embed=error_embed("This command must be used inside a server."),
                ephemeral=True,
            )
            return

        marker_prefix = "Delta ticket category:"
        topic_lines = [
            line for line in (channel.topic or "").splitlines()
            if not line.startswith(marker_prefix)
        ]

        try:
            if action.value == "remove":
                await channel.edit(
                    topic="\n".join(topic_lines) or None,
                    reason=f"Removed from ticket system by {interaction.user}",
                )
                message = f"{channel.mention} was removed from the ticket system."
            else:
                destination = guild.get_channel(TICKET_CATEGORY_ID)
                if not isinstance(destination, discord.CategoryChannel):
                    raise ValueError("The configured ticket category could not be found.")

                cfg = TICKET_CONFIG[category.value]
                staff_role = guild.get_role(STAFF_ROLE_ID)
                await channel.set_permissions(
                    guild.default_role,
                    view_channel=False,
                    reason=f"Restricted to support by {interaction.user}",
                )
                category_role = guild.get_role(cfg["role_id"])
                if category_role is not None and category_role != staff_role:
                    await channel.set_permissions(
                        category_role,
                        overwrite=None,
                        reason=f"Restricted to support by {interaction.user}",
                    )
                for role in {staff_role} - {None}:
                    await channel.set_permissions(
                        role,
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_channels=True,
                        reason=f"Added to ticket system by {interaction.user}",
                    )
                topic_lines.append(f"{marker_prefix} {category.value}")
                await channel.edit(
                    category=destination,
                    topic="\n".join(topic_lines),
                    reason=f"Added to ticket system by {interaction.user}",
                )
                await channel.send(
                    embed=success_embed(
                        f"This channel now uses the **{cfg['label']}** ticket functions."
                    ),
                    view=TicketActionView(),
                )
                message = (
                    f"{channel.mention} was added as a **{cfg['label']}** ticket channel."
                )
        except (discord.Forbidden, discord.HTTPException, ValueError) as exc:
            await interaction.response.send_message(
                embed=error_embed(f"The ticket channel could not be updated: {exc}"),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=success_embed(message), ephemeral=True
        )

    # /close
    @tree.command(name="close", description="Close the current support ticket.")
    async def close(interaction: discord.Interaction) -> None:
        channel = interaction.channel
        member  = interaction.user

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("This command can only be used inside a ticket channel."),
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

    # /connected
    @tree.command(name="connected", description="Notify the user that an agent has connected (staff only).")
    @staff_only()
    async def connected(interaction: discord.Interaction) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("This command must be used inside a ticket channel."),
                ephemeral=True,
            )
            return
        embed = _base_embed(
            title="🛫  Your Support Agent Is Connected",
            description=(
                "A **Delta Air Lines Support Agent** is now actively reviewing your "
                "private ticket and is ready to assist you.\n\n"
                "Continue sending your questions, details, screenshots, or documents "
                "in this DM. Everything you send will be delivered securely to the agent."
            ),
        )
        embed.add_field(
            name="📨 Message Delivery",
            value="Look for a ✅ reaction to confirm that your message reached the support channel.",
            inline=False,
        )
        _set_brand_image(embed, DIVIDER_URL)
        delivered = await send_embed_to_ticket_owner(interaction.client, channel, embed)
        await interaction.response.send_message(
            embed=success_embed(
                "The connected notice was delivered to the customer's DMs."
                if delivered else
                "The notice was posted here, but the customer's DMs could not be reached."
            ),
            ephemeral=True,
        )
        await channel.send(embed=embed)

    # /resolved
    @tree.command(name="resolved", description="Mark the ticket as resolved (staff only).")
    @staff_only()
    async def resolved(interaction: discord.Interaction) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("This command must be used inside a ticket channel."),
                ephemeral=True,
            )
            return
        embed = _base_embed(
            title="✅  Your Support Request Was Resolved",
            description=(
                "A Delta Support team member has marked your request as **resolved**. "
                "We hope the information and assistance provided addressed your needs."
            ),
        )
        embed.add_field(
            name="Need More Assistance?",
            value=(
                "If something remains unresolved, reply in this DM before the ticket is closed. "
                "You can also begin a new request later from the Assistance Panel."
            ),
            inline=False,
        )
        embed.add_field(name="Thank You", value="Thank you for contacting Delta Air Lines Support — *Keep Climbing.*", inline=False)
        _set_brand_image(embed, DIVIDER_URL)
        delivered = await send_embed_to_ticket_owner(interaction.client, channel, embed)
        await interaction.response.send_message(
            embed=success_embed(
                "The resolution notice was delivered to the customer's DMs."
                if delivered else
                "The notice was posted here, but the customer's DMs could not be reached."
            ),
            ephemeral=True,
        )
        await channel.send(embed=embed)

    # /revoke — leadership only: remove a user's access from a ticket channel
    @tree.command(name="revoke", description="Revoke a user's access to this ticket (leadership only).")
    @staff_only()
    @app_commands.describe(user="The member to remove from this ticket.")
    async def revoke(interaction: discord.Interaction, user: discord.Member) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("This command must be used inside a ticket channel."),
                ephemeral=True,
            )
            return

        # Prevent revoking the ticket owner
        topic = channel.topic or ""
        if str(user.id) in topic:
            await interaction.response.send_message(
                embed=error_embed("You cannot revoke the ticket owner's access."),
                ephemeral=True,
            )
            return

        try:
            await channel.set_permissions(user, overwrite=None, reason=f"Access revoked by {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=error_embed("I don't have permission to manage this channel's permissions."),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=success_embed(f"{user.mention}'s access to this ticket has been revoked."),
            ephemeral=True,
        )
        embed = _base_embed(
            title="🚫  Access Revoked",
            description=f"{user.mention} has had their access to this ticket removed by {interaction.user.mention}.",
        )
        _set_brand_image(embed, DIVIDER_URL)
        await channel.send(embed=embed)

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
        log.info("Logged in as %s (ID: %s)", self.user, self.user.id if self.user else "unknown")
        log.info("Delta Air Lines HelpDesk is online and ready.")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="✈️  Delta Air Lines Support",
            )
        )

        for guild in tuple(self.guilds):
            if guild.id != GUILD_ID:
                log.warning("Leaving unauthorized guild %s (%s).", guild.name, guild.id)
                await guild.leave()

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """Immediately leave every server except the configured target guild."""
        if guild.id != GUILD_ID:
            log.warning("Declining unauthorized guild %s (%s).", guild.name, guild.id)
            await guild.leave()

    async def on_message(self, message: discord.Message) -> None:
        """Relay customer DMs and claimed support-channel replies."""
        if message.author.bot:
            return

        if isinstance(message.channel, discord.DMChannel):
            target_guild = self.get_guild(GUILD_ID)
            if target_guild is None:
                await message.channel.send(embed=error_embed("The ticket system is unavailable right now."))
                return
            try:
                member = target_guild.get_member(message.author.id) or await target_guild.fetch_member(
                    message.author.id
                )
            except discord.NotFound:
                await message.channel.send(
                    embed=error_embed("This bot is only available to members of its support server.")
                )
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
                await message.channel.send(embed=error_embed("The ticket system is unavailable right now."))
                return

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
                prompt = _base_embed(
                    title="✈️  Welcome to Delta Air Lines Support",
                    description=(
                        "Thank you for contacting us. Our support team can assist with general "
                        "questions, applications, partnerships, purchases, roles, and technical issues.\n\n"
                        "Would you like to create a **private support ticket**? If you continue, "
                        "your messages will be securely relayed to the appropriate support team."
                    ),
                )
                prompt.add_field(
                    name="🔐 Your Privacy",
                    value="The support conversation will remain in this DM; you will not be added to a server ticket channel.",
                    inline=False,
                )
                prompt.add_field(
                    name="⏱️ What Happens Next",
                    value="Choose Yes, select a department, and send the details of your request.",
                    inline=False,
                )
                _set_brand_image(prompt, DIVIDER_URL)
                await message.channel.send(
                    embed=prompt,
                    view=DMTicketPromptView(self, message.author.id),
                )
            return

        if isinstance(message.channel, discord.TextChannel):
            topic = message.channel.topic or ""
            owner_id = get_topic_value(topic, DM_TICKET_OWNER_MARKER)
            if owner_id is None:
                return

            claimed_id = get_topic_value(topic, DM_TICKET_CLAIM_MARKER)
            if claimed_id is None:
                await message.add_reaction("⏳")
                await message.channel.send(
                    embed=error_embed("Claim this ticket before sending a reply to the customer."),
                    delete_after=8,
                )
                return
            if claimed_id != str(message.author.id):
                await message.add_reaction("❌")
                await message.channel.send(
                    embed=error_embed("Only the support agent who claimed this ticket can reply."),
                    delete_after=8,
                )
                return
            await relay_support_message(self, message, owner_id)



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
    <p>The Discord support bot is running and actively serving tickets.<br>Keep Climbing.</p>
    <div class="divider"></div>
  </div>
  <footer>Delta Air Lines &mdash; Automated Service Monitor</footer>
</body>
</html>"""

        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(self._HTML)))
            self.end_headers()
            self.wfile.write(self._HTML)

        def do_HEAD(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(self._HTML)))
            self.end_headers()

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
    log.info("Health-check server started.")

    run_bot_forever(token)


if __name__ == "__main__":
    main()
