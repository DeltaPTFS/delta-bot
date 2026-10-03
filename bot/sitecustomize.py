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
    STAFF_ROLE_ID = 1539005030189891684
    ADMIN_ROLE_ID = 1539005297417519205
    DM_TICKET_OWNER_MARKER = "Delta DM Ticket Owner:"
    DM_TICKET_CATEGORY_MARKER = "Delta Ticket Category:"
    DM_TICKET_CLAIM_MARKER = "Delta Ticket Claimed By:"
    DELTA_RED = 0xC8102E
    DELTA_BLUE = 0x003087
    FOOTER_TEXT = "Delta Air Lines • Keep Climbing"
    CLAIM_LOCKS: dict[int, asyncio.Lock] = {}

    def _member_has_role(member: discord.Member, role_id: int) -> bool:
        return any(role.id == role_id for role in member.roles)

    def _is_staff_or_admin(member: discord.Member) -> bool:
        return _member_has_role(member, STAFF_ROLE_ID) or _member_has_role(member, ADMIN_ROLE_ID)

    def _is_admin(member: discord.Member) -> bool:
        return _member_has_role(member, ADMIN_ROLE_ID)

    def _get_topic_value(topic: str, marker: str) -> str | None:
        for line in topic.splitlines():
            if line.startswith(marker):
                return line.removeprefix(marker).strip() or None
        return None

    def _set_topic_value(topic: str, marker: str, value: str | None) -> str:
        lines = [line for line in topic.splitlines() if not line.startswith(marker)]
        if value is not None:
            lines.append(f"{marker} {value}")
        return "\n".join(lines)

    def _is_ticket_channel(channel: discord.TextChannel) -> bool:
        topic = channel.topic or ""
        return (
            _get_topic_value(topic, DM_TICKET_OWNER_MARKER) is not None
            or _get_topic_value(topic, DM_TICKET_CATEGORY_MARKER) is not None
        )

    def _activity_embed(
        *,
        title: str,
        description: str,
        color: int = DELTA_BLUE,
    ) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text=FOOTER_TEXT)
        return embed

    async def _reply_once(
        interaction: discord.Interaction,
        message: str,
        *,
        ephemeral: bool = True,
    ) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(message, ephemeral=ephemeral)

    async def _send_claim_server_log(
        interaction: discord.Interaction,
        *,
        title: str,
        channel: discord.TextChannel,
        member: discord.Member,
        owner_id: str | None,
        color: int,
    ) -> None:
        sender = getattr(interaction.client, "_send_server_log", None)
        if sender is None:
            return
        description = (
            f"**Ticket:** {channel.mention} (`{channel.id}`)\n"
            f"**Support:** {member.mention}\n"
            f"**Support ID:** `{member.id}`"
        )
        if owner_id is not None:
            description += f"\n**Customer ID:** `{owner_id}`"
        try:
            await sender(title, description, color=color)
        except Exception as exc:  # pragma: no cover - defensive runtime patch
            log.warning("Could not send claim server log: %s", exc)

    async def _run_claim_action(
        interaction: discord.Interaction,
        *,
        unclaim: bool = False,
        source: str = "/claim",
    ) -> None:
        channel = interaction.channel
        member = interaction.user
        if not isinstance(channel, discord.TextChannel) or not isinstance(member, discord.Member):
            await _reply_once(interaction, f"Use `{source}` inside a ticket channel.")
            return
        if not _is_staff_or_admin(member):
            await _reply_once(interaction, "Only Delta support staff or admins can claim tickets.")
            return

        lock = CLAIM_LOCKS.setdefault(channel.id, asyncio.Lock())
        async with lock:
            try:
                fresh_channel = await channel.guild.fetch_channel(channel.id)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
                await _reply_once(interaction, f"I could not refresh this ticket: {exc}")
                return
            if not isinstance(fresh_channel, discord.TextChannel) or not _is_ticket_channel(fresh_channel):
                await _reply_once(interaction, "This command can only be used inside a customer ticket channel.")
                return

            topic = fresh_channel.topic or ""
            owner_id = _get_topic_value(topic, DM_TICKET_OWNER_MARKER)
            claimed_id = _get_topic_value(topic, DM_TICKET_CLAIM_MARKER)

            if unclaim:
                if claimed_id is None:
                    await _reply_once(interaction, "This ticket is not currently claimed.")
                    return
                if claimed_id != str(member.id) and not _is_admin(member):
                    await _reply_once(interaction, f"Only <@{claimed_id}> or an admin can unclaim this ticket.")
                    return
                new_topic = _set_topic_value(topic, DM_TICKET_CLAIM_MARKER, None)
                action_word = "unclaimed"
                title = "Ticket Unclaimed"
                color = DELTA_RED
                status = f"This ticket has been unclaimed by {member.mention}."
            else:
                if claimed_id == str(member.id):
                    await _reply_once(interaction, "You already claimed this ticket.")
                    return
                if claimed_id is not None:
                    await _reply_once(interaction, f"This ticket is already claimed by <@{claimed_id}>.")
                    return
                new_topic = _set_topic_value(topic, DM_TICKET_CLAIM_MARKER, str(member.id))
                action_word = "claimed"
                title = "Ticket Claimed"
                color = DELTA_BLUE
                status = f"This ticket has been claimed by {member.mention}."

            try:
                await fresh_channel.edit(
                    topic=new_topic,
                    reason=f"Ticket {action_word} by {member}",
                )
            except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
                await _reply_once(interaction, f"I could not update this ticket claim: {exc}")
                return

        await _reply_once(interaction, f"Ticket {action_word} successfully.")
        await fresh_channel.send(
            embed=_activity_embed(
                title="Ticket Command Activity",
                description=(
                    f"**Command:** `{source}`\n"
                    f"**Action:** Ticket {action_word}\n"
                    f"**Used By:** {member.mention} (`{member.id}`)"
                ),
                color=color,
            )
        )
        await fresh_channel.send(
            embed=_activity_embed(
                title=title,
                description=status,
                color=color,
            )
        )
        await _send_claim_server_log(
            interaction,
            title=title,
            channel=fresh_channel,
            member=member,
            owner_id=owner_id,
            color=color,
        )

    async def _delta_claim_button_callback(interaction: discord.Interaction) -> None:
        await _run_claim_action(interaction, source="Claim Ticket Button")

    def _patch_claim_button_view(view: Any) -> None:
        children = getattr(view, "children", None)
        if not isinstance(children, list):
            return
        for item in children:
            if getattr(item, "custom_id", None) == "delta:claim_ticket":
                item.label = "Claim Ticket"
                item.style = discord.ButtonStyle.primary
                item.callback = _delta_claim_button_callback

    async def _block_invalid_ticket_admin_claims(
        interaction: discord.Interaction,
        command_name: str,
        namespace: Any,
    ) -> bool:
        if command_name != "ticket admin":
            return False
        selected_command = getattr(getattr(namespace, "command", None), "value", None)
        if selected_command not in {"claim", "unclaim"}:
            return False
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            return False
        topic = channel.topic or ""
        claimed_id = _get_topic_value(topic, DM_TICKET_CLAIM_MARKER)
        if selected_command == "claim" and claimed_id is not None:
            await _reply_once(interaction, f"This ticket is already claimed by <@{claimed_id}>.")
            return True
        if selected_command == "unclaim" and claimed_id is None:
            await _reply_once(interaction, "This ticket is not currently claimed.")
            return True
        return False

    if not getattr(discord.InteractionResponse, "_delta_auto_ack_installed", False):
        _original_send_message = discord.InteractionResponse.send_message
        _original_command_invoke = app_commands.Command._invoke_with_namespace

        async def _send_message_or_followup(
            self: discord.InteractionResponse,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            """Send normally, or use a follow-up after an automatic defer."""
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
            if await _block_invalid_ticket_admin_claims(interaction, command_name, namespace):
                return None
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

    if not getattr(app_commands.CommandTree, "_delta_ticket_command_patch_installed", False):
        _original_tree_sync = app_commands.CommandTree.sync

        @app_commands.command(name="close", description="Close the current support ticket.")
        @app_commands.describe(reason="Reason for closing the ticket.")
        async def _delta_close_command(
            interaction: discord.Interaction,
            reason: str = "Closed by staff command.",
        ) -> None:
            channel = interaction.channel
            member = interaction.user
            if not isinstance(channel, discord.TextChannel) or not isinstance(member, discord.Member):
                await interaction.response.send_message("Use `/close` inside a ticket channel.", ephemeral=True)
                return
            if not _is_staff_or_admin(member):
                await interaction.response.send_message("Only Delta support staff or admins can close tickets.", ephemeral=True)
                return
            if not _is_ticket_channel(channel):
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

        @app_commands.command(name="claim", description="Claim the current support ticket.")
        async def _delta_claim_command(interaction: discord.Interaction) -> None:
            await _run_claim_action(interaction, source="/claim")

        @app_commands.command(name="unclaim", description="Unclaim the current support ticket.")
        async def _delta_unclaim_command(interaction: discord.Interaction) -> None:
            await _run_claim_action(interaction, unclaim=True, source="/unclaim")

        def _ensure_ticket_commands(tree: app_commands.CommandTree) -> None:
            for command in (_delta_close_command, _delta_claim_command, _delta_unclaim_command):
                existing = tree.get_command(command.name, type=discord.AppCommandType.chat_input)
                if existing is None:
                    tree.add_command(command, override=True)

        async def _sync_with_ticket_commands(
            self: app_commands.CommandTree,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            _ensure_ticket_commands(self)
            return await _original_tree_sync(self, *args, **kwargs)

        app_commands.CommandTree.sync = _sync_with_ticket_commands
        app_commands.CommandTree._delta_ticket_command_patch_installed = True

    if not getattr(discord.ui.View, "_delta_claim_guard_installed", False):
        _original_view_scheduled_task = discord.ui.View._scheduled_task

        async def _scheduled_task_with_claim_guard(
            self: discord.ui.View,
            item: Any,
            interaction: discord.Interaction,
        ) -> Any:
            if getattr(item, "custom_id", None) == "delta:claim_ticket":
                return await _delta_claim_button_callback(interaction)
            return await _original_view_scheduled_task(self, item, interaction)

        discord.ui.View._scheduled_task = _scheduled_task_with_claim_guard
        discord.ui.View._delta_claim_guard_installed = True

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
            view = kwargs.get("view")
            _patch_claim_button_view(view)
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
