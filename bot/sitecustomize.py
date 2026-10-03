"""Runtime safety patches for Discord interaction acknowledgement.

Python imports ``sitecustomize`` automatically from the script directory before
``main.py`` runs. Keeping this patch isolated lets the production entry point
stay focused on bot logic while still protecting every deployment from Discord's
three-second interaction acknowledgement window.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger("delta-helpdesk.interactions")

GREY_R_MENTION = "<@1263248306264608871>"
RAY_C_MENTION = "<@874702650845843466>"

SUPPORT_INSTRUCTIONS = (
    "1. Claim the ticket before handling it.\n"
    "2. Use `/reply` to respond to the customer through the ticket.\n"
    "3. Analyze the customer request carefully and use the correct command/action.\n"
    "4. SkyMiles sign-ups must be completed through the website.\n"
    f"5. If the SkyMiles website is down, ping {GREY_R_MENTION}.\n"
    f"6. For partnership requests, ping {GREY_R_MENTION} and {RAY_C_MENTION}."
)

try:
    import discord
    from discord import app_commands
except Exception as exc:  # pragma: no cover - defensive import hook
    log.warning("Delta runtime patches were not installed: %s", exc)
else:
    if not getattr(discord.InteractionResponse, "_delta_auto_ack_installed", False):
        _original_send_message = discord.InteractionResponse.send_message
        _original_command_invoke = app_commands.Command._invoke_with_namespace

        async def _send_message_or_followup(
            self: discord.InteractionResponse,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            """Send normally, or use a follow-up after an automatic defer.

            A slow command may already have been acknowledged by the auto-defer
            watchdog below. In that case Discord rejects a second initial
            response, so we transparently send the same payload as a follow-up.
            """
            if self.is_done():
                interaction = getattr(self, "_parent", None)
                if interaction is not None:
                    return await interaction.followup.send(*args, **kwargs)
            return await _original_send_message(self, *args, **kwargs)

        async def _auto_defer_if_still_pending(
            interaction: discord.Interaction,
            command_name: str,
            namespace: Any,
        ) -> None:
            await asyncio.sleep(2.25)
            if interaction.response.is_done():
                return

            # Modal commands must answer with the modal as the first response.
            # Do not auto-defer ticket close actions, because a deferred
            # interaction cannot later open Discord's close-reason modal.
            selected_command = getattr(getattr(namespace, "command", None), "value", None)
            if command_name in {"ticket control", "ticket admin"} and selected_command == "close":
                return

            try:
                await interaction.response.defer(ephemeral=True)
                log.info(
                    "Auto-deferred slow interaction %s for command %s.",
                    interaction.id,
                    command_name,
                )
            except (discord.InteractionResponded, discord.NotFound, discord.HTTPException):
                return
            except Exception as exc:  # pragma: no cover - defensive safety net
                log.warning(
                    "Could not auto-defer interaction %s for command %s: %s",
                    interaction.id,
                    command_name,
                    exc,
                )

        async def _invoke_with_auto_defer(
            self: app_commands.Command,
            interaction: discord.Interaction,
            namespace: app_commands.Namespace,
        ) -> Any:
            command_name = getattr(self, "qualified_name", getattr(self, "name", "unknown"))
            watchdog = asyncio.create_task(
                _auto_defer_if_still_pending(interaction, command_name, namespace)
            )
            try:
                return await _original_command_invoke(self, interaction, namespace)
            finally:
                watchdog.cancel()

        discord.InteractionResponse.send_message = _send_message_or_followup
        app_commands.Command._invoke_with_namespace = _invoke_with_auto_defer
        discord.InteractionResponse._delta_auto_ack_installed = True

    if not getattr(app_commands.CommandTree, "_delta_close_command_patch_installed", False):
        _original_tree_sync = app_commands.CommandTree.sync

        STAFF_ROLE_ID = 1539005030189891684
        ADMIN_ROLE_ID = 1539005297417519205
        DM_TICKET_OWNER_MARKER = "Delta DM Ticket Owner:"
        DELTA_RED = 0xC8102E
        DELTA_BLUE = 0x003087
        FOOTER_TEXT = "Delta Air Lines • Keep Climbing"

        def _member_has_role(member: discord.Member, role_id: int) -> bool:
            return any(role.id == role_id for role in member.roles)

        def _activity_embed(
            *,
            title: str,
            description: str,
            color: int = DELTA_BLUE,
        ) -> discord.Embed:
            embed = discord.Embed(title=title, description=description, color=color)
            embed.set_footer(text=FOOTER_TEXT)
            return embed

        @app_commands.command(name="close", description="Close the current support ticket.")
        @app_commands.describe(reason="Reason for closing the ticket.")
        async def _delta_close_command(
            interaction: discord.Interaction,
            reason: str = "Closed by staff command.",
        ) -> None:
            channel = interaction.channel
            member = interaction.user
            if not isinstance(channel, discord.TextChannel) or not isinstance(member, discord.Member):
                await interaction.response.send_message(
                    "Use `/close` inside a ticket channel.",
                    ephemeral=True,
                )
                return

            if not (_member_has_role(member, STAFF_ROLE_ID) or _member_has_role(member, ADMIN_ROLE_ID)):
                await interaction.response.send_message(
                    "Only Delta support staff or admins can close tickets.",
                    ephemeral=True,
                )
                return

            topic = channel.topic or ""
            if DM_TICKET_OWNER_MARKER not in topic:
                await interaction.response.send_message(
                    "This command can only be used inside a customer ticket channel.",
                    ephemeral=True,
                )
                return

            await interaction.response.send_message(
                f"Closing this ticket in **5 seconds**. Reason: {reason}",
                ephemeral=True,
            )
            await channel.send(
                embed=_activity_embed(
                    title="Ticket Command Activity",
                    description=(
                        "**Command:** `/close`\n"
                        f"**Used By:** {member.mention} (`{member.id}`)\n"
                        f"**Reason:** {reason}"
                    ),
                    color=DELTA_RED,
                )
            )
            await channel.send(
                embed=_activity_embed(
                    title="Ticket Closing",
                    description=(
                        "This ticket has been marked as **closed** and will be deleted in **5 seconds**.\n\n"
                        f"**Reason:** {reason}"
                    ),
                    color=DELTA_RED,
                )
            )
            await asyncio.sleep(5)
            try:
                await channel.delete(reason=f"Ticket closed by {member}: {reason}")
            except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
                log.warning("Could not delete ticket %s with /close: %s", channel.id, exc)

        def _ensure_delta_close_command(tree: app_commands.CommandTree) -> None:
            existing = tree.get_command("close", type=discord.AppCommandType.chat_input)
            if existing is None:
                tree.add_command(_delta_close_command, override=True)

        async def _sync_with_delta_close_command(
            self: app_commands.CommandTree,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            _ensure_delta_close_command(self)
            return await _original_tree_sync(self, *args, **kwargs)

        app_commands.CommandTree.sync = _sync_with_delta_close_command
        app_commands.CommandTree._delta_close_command_patch_installed = True

    if not getattr(discord.TextChannel, "_delta_ticket_instruction_patch_installed", False):
        _original_text_channel_send = discord.TextChannel.send

        def _is_private_support_ticket_embed(embed: discord.Embed) -> bool:
            title = embed.title or ""
            if "Private DM Support" not in title:
                return False
            return any((field.name or "").strip() == "Support Instructions" for field in embed.fields)

        def _apply_support_instruction_update(embed: discord.Embed) -> bool:
            if not _is_private_support_ticket_embed(embed):
                return False
            for index, field in enumerate(embed.fields):
                if (field.name or "").strip() == "Support Instructions":
                    embed.set_field_at(
                        index,
                        name=field.name,
                        value=SUPPORT_INSTRUCTIONS,
                        inline=field.inline,
                    )
                    return True
            return False

        async def _send_with_ticket_instruction_patch(
            self: discord.TextChannel,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            embed = kwargs.get("embed")
            embeds = kwargs.get("embeds")
            support_embed: discord.Embed | None = None

            if isinstance(embed, discord.Embed) and _apply_support_instruction_update(embed):
                support_embed = embed
            elif isinstance(embeds, list):
                for possible_embed in embeds:
                    if isinstance(possible_embed, discord.Embed) and _apply_support_instruction_update(possible_embed):
                        support_embed = possible_embed
                        break

            if support_embed is not None and "Partner Request" in (support_embed.title or ""):
                # Mentions inside embeds do not always notify users. For
                # partnership tickets, place Grey R. and Ray C. in the actual
                # message content so Discord sends real pings.
                existing_content = kwargs.get("content")
                partnership_ping = (
                    f"{GREY_R_MENTION} {RAY_C_MENTION} "
                    "Partnership request opened — please review this ticket."
                )
                kwargs["content"] = (
                    f"{existing_content}\n{partnership_ping}"
                    if existing_content
                    else partnership_ping
                )
                kwargs["allowed_mentions"] = discord.AllowedMentions(users=True, roles=True)

            return await _original_text_channel_send(self, *args, **kwargs)

        discord.TextChannel.send = _send_with_ticket_instruction_patch
        discord.TextChannel._delta_ticket_instruction_patch_installed = True
