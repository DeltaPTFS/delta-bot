"""
commands.py — All slash commands registered by the Delta HelpDesk bot.

Staff-only commands are guarded with the staff_only() check.
"""

from __future__ import annotations

import discord
from discord import app_commands

from config import STAFF_ROLE_ID
from embeds import (
    assistance_panel_banner_embed,
    assistance_panel_embed,
    error_embed,
    success_embed,
)
from tickets import handle_close_from_command
from views import AssistancePanelView


# ── Guard ─────────────────────────────────────────────────────────────────────

def staff_only() -> app_commands.check:
    """App-command check: caller must have the STAFF_ROLE_ID."""
    async def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user
        if not isinstance(member, discord.Member):
            return False
        return any(role.id == STAFF_ROLE_ID for role in member.roles)

    return app_commands.check(predicate)


# ── Command registration ──────────────────────────────────────────────────────

def register_commands(tree: app_commands.CommandTree) -> None:
    """Attach all slash commands to the provided command tree."""

    # ── /assistance ──────────────────────────────────────────────────────────
    assistance_group = app_commands.Group(
        name="assistance",
        description="Delta Air Lines Assistance Panel commands (staff only).",
    )

    @assistance_group.command(name="panel", description="Post the Delta HelpDesk Assistance Panel.")
    @staff_only()
    async def assistance_panel(interaction: discord.Interaction) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("This command can only be used in a text channel."),
                ephemeral=True,
            )
            return

        # Acknowledge with an ephemeral confirmation so the command invocation
        # doesn't litter the channel.
        await interaction.response.send_message(
            embed=success_embed("Assistance Panel posted successfully."),
            ephemeral=True,
        )

        # Post the full-width banner first, then the panel embed with dropdown.
        await channel.send(embed=assistance_panel_banner_embed())
        await channel.send(embed=assistance_panel_embed(), view=AssistancePanelView())

    tree.add_command(assistance_group)

    # ── /close ───────────────────────────────────────────────────────────────
    @tree.command(name="close", description="Close the current support ticket.")
    async def close(interaction: discord.Interaction) -> None:
        await handle_close_from_command(interaction)

    # ── /connected ───────────────────────────────────────────────────────────
    @tree.command(name="connected", description="Mark a ticket as connected / acknowledged (staff only).")
    @staff_only()
    async def connected(interaction: discord.Interaction) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("This command must be used inside a ticket channel."),
                ephemeral=True,
            )
            return

        # Ephemeral confirmation for staff
        await interaction.response.send_message(
            embed=success_embed("Message sent successfully."),
            ephemeral=True,
        )
        # Public Delta-branded embed in the ticket
        embed = discord.Embed(
            title="🛫  Agent Connected",
            description=(
                "A **Delta Air Lines Support Agent** has connected to your ticket "
                "and will be assisting you shortly.\n\n"
                "Please feel free to continue describing your issue."
            ),
            color=0xC8102E,
        )
        embed.set_footer(text="Delta Air Lines • Keep Climbing")
        await channel.send(embed=embed)

    # ── /resolved ────────────────────────────────────────────────────────────
    @tree.command(name="resolved", description="Mark a ticket as resolved (staff only).")
    @staff_only()
    async def resolved(interaction: discord.Interaction) -> None:
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                embed=error_embed("This command must be used inside a ticket channel."),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            embed=success_embed("Message sent successfully."),
            ephemeral=True,
        )
        embed = discord.Embed(
            title="✅  Ticket Resolved",
            description=(
                "Your support request has been marked as **resolved** by our team.\n\n"
                "If you have any further questions, please open a new ticket. "
                "Thank you for flying with Delta Air Lines — *Keep Climbing.*"
            ),
            color=0xC8102E,
        )
        embed.set_footer(text="Delta Air Lines • Keep Climbing")
        await channel.send(embed=embed)

    # ── Error handler for staff_only failures ─────────────────────────────────
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
