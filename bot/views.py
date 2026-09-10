"""
views.py — All discord.py UI components (Views, Selects, Buttons).
"""

from __future__ import annotations

import asyncio
import discord

from config import TICKET_CONFIG
from embeds import (
    general_inquiries_welcome,
    generic_ticket_welcome,
    ticket_closed_channel,
    ticket_closed_dm,
    already_open_ticket,
    error_embed,
)
from utils import find_existing_ticket, create_ticket_channel, can_close_ticket


# ── Close Ticket Button ───────────────────────────────────────────────────────

class CloseTicketButton(discord.ui.View):
    """Persistent view with a single '🔒 Close Ticket' button."""

    def __init__(self) -> None:
        # timeout=None makes the view persist across bot restarts
        super().__init__(timeout=None)

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

        await _close_ticket(interaction, channel, member)


# ── Assistance Panel Dropdown ─────────────────────────────────────────────────

class AssistanceSelect(discord.ui.Select):
    """Dropdown listing all support categories."""

    def __init__(self) -> None:
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
        await interaction.response.defer(ephemeral=True)

        member = interaction.user
        guild  = interaction.guild

        if not isinstance(member, discord.Member) or guild is None:
            await interaction.followup.send(
                embed=error_embed("This panel can only be used inside a server."),
                ephemeral=True,
            )
            return

        selected_key = self.values[0]
        cfg = TICKET_CONFIG[selected_key]

        # Duplicate-ticket guard
        existing = await find_existing_ticket(guild, member)
        if existing is not None:
            await interaction.followup.send(
                embed=already_open_ticket(existing),
                ephemeral=True,
            )
            return

        # Create the ticket channel
        try:
            channel = await create_ticket_channel(
                guild=guild,
                member=member,
                prefix=cfg["prefix"],
                support_role_id=cfg["role_id"],
            )
        except Exception as exc:
            await interaction.followup.send(
                embed=error_embed(f"Failed to create your ticket: {exc}"),
                ephemeral=True,
            )
            return

        # Ping creator + support role
        support_role = guild.get_role(cfg["role_id"])
        ping_text = (
            f"{member.mention} {support_role.mention if support_role else ''}"
        ).strip()
        await channel.send(ping_text)

        # Post the category-specific welcome embed
        if selected_key == "general_inquiries":
            embed = general_inquiries_welcome(member)
        else:
            embed = generic_ticket_welcome(member, cfg["label"], cfg["emoji"])

        await channel.send(embed=embed, view=CloseTicketButton())

        # Confirm to the user (ephemeral)
        await interaction.followup.send(
            content=f"✅  Your ticket has been created: {channel.mention}",
            ephemeral=True,
        )


class AssistancePanelView(discord.ui.View):
    """Persistent view that wraps the AssistanceSelect dropdown."""

    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(AssistanceSelect())


# ── Internal helper ───────────────────────────────────────────────────────────

async def _close_ticket(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    closer: discord.Member,
) -> None:
    """
    DM the ticket owner, post a closing embed, wait 5 s, then delete channel.
    Called from both the Close Button and the /close slash command.
    """
    # Identify the ticket owner from channel topic
    topic = channel.topic or ""
    owner: discord.Member | None = None
    for part in topic.split():
        if part.isdigit():
            owner = channel.guild.get_member(int(part))
            break

    # Acknowledge the interaction first
    await interaction.response.send_message(
        embed=ticket_closed_channel(),
        ephemeral=False,
    )

    # DM the owner
    if owner is not None:
        try:
            await owner.send(embed=ticket_closed_dm(channel.name))
        except discord.Forbidden:
            pass  # User has DMs disabled — non-fatal

    await asyncio.sleep(5)
    try:
        await channel.delete(
            reason=f"Ticket closed by {closer} ({closer.id})"
        )
    except discord.NotFound:
        pass  # Already deleted
