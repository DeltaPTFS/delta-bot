"""
embeds.py — Factory functions for every Delta-branded embed used by the bot.
"""

from __future__ import annotations

import discord
from config import (
    DELTA_RED, DIVIDER_URL, FOOTER_TEXT, MAILING_ADDRESS, BANNER_URL
)


def _base_embed(title: str = "", description: str = "") -> discord.Embed:
    """Return an embed pre-loaded with Delta branding."""
    embed = discord.Embed(
        title=title,
        description=description,
        color=DELTA_RED,
    )
    embed.set_footer(text=FOOTER_TEXT)
    return embed


# ── Assistance Panel ──────────────────────────────────────────────────────────

def assistance_panel_embed() -> discord.Embed:
    """Main embed shown on the Assistance Panel message."""
    embed = _base_embed(
        title="✈️  Delta Air Lines — HelpDesk",
        description=(
            "Welcome to the **Delta Air Lines Support Centre**.\n\n"
            "Our dedicated team is here to assist you with any questions, "
            "concerns, or requests you may have. Please select a category "
            "from the dropdown menu below to open a private support ticket.\n\n"
            "A member of our support team will be with you as soon as possible. "
            "Thank you for choosing Delta Air Lines — *Keep Climbing.*"
        ),
    )
    embed.add_field(name="📬 Mailing Address", value=MAILING_ADDRESS, inline=False)
    embed.set_image(url=DIVIDER_URL)
    return embed


def assistance_panel_banner_embed() -> discord.Embed:
    """Top banner embed (full Delta banner image)."""
    embed = discord.Embed(color=DELTA_RED)
    embed.set_image(url=BANNER_URL)
    return embed


# ── General Inquiries ─────────────────────────────────────────────────────────

def general_inquiries_welcome(member: discord.Member) -> discord.Embed:
    embed = _base_embed(
        title="📋  General Inquiries — Support Ticket",
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
    embed.set_image(url=DIVIDER_URL)
    return embed


# ── Generic ticket welcome (for categories without a custom embed) ─────────────

def generic_ticket_welcome(member: discord.Member, label: str, emoji: str) -> discord.Embed:
    embed = _base_embed(
        title=f"{emoji}  {label} — Support Ticket",
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
    embed.set_image(url=DIVIDER_URL)
    return embed


# ── Ticket closed ─────────────────────────────────────────────────────────────

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
    embed.set_image(url=DIVIDER_URL)
    return embed


def ticket_closed_channel() -> discord.Embed:
    embed = _base_embed(
        title="🔒  Ticket Closing",
        description=(
            "This ticket has been marked as **closed** and will be deleted shortly.\n\n"
            "Thank you for contacting Delta Air Lines Support."
        ),
    )
    embed.set_image(url=DIVIDER_URL)
    return embed


# ── Error / info embeds ───────────────────────────────────────────────────────

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
    embed = discord.Embed(
        title="❌  Error",
        description=message,
        color=DELTA_RED,
    )
    embed.set_footer(text=FOOTER_TEXT)
    return embed


def success_embed(message: str) -> discord.Embed:
    embed = discord.Embed(
        title="✅  Success",
        description=message,
        color=DELTA_RED,
    )
    embed.set_footer(text=FOOTER_TEXT)
    return embed
