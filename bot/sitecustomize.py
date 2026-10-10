"""Runtime safety patches for Delta HelpDesk.

Python imports ``sitecustomize`` automatically from the script directory before
``main.py`` runs. This file keeps deployment-safe patches out of the main bot
entry point while protecting interactions, tickets, and logging.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

log = logging.getLogger("delta-helpdesk.interactions")

GREY_R_MENTION = "<@1263248306264608871>"
RAY_C_MENTION = "<@874702650845843466>"

BASE_SUPPORT_INSTRUCTIONS = (
    "1. **Claim the ticket** before handling the request.\n"
    "2. Use **`/reply`** to respond to the customer through the ticket.\n"
    "3. Analyze the customer's request carefully and use the correct command or action."
)

def support_instructions_for(title: str) -> str:
    if "General Inquir" in title or "General Support" in title:
        return (
            BASE_SUPPORT_INSTRUCTIONS
            + "\n4. **SkyMiles sign-ups must be completed on the website.**"
            + f"\n5. If the SkyMiles website is down, ping {GREY_R_MENTION}."
        )
    if "Partner Request" in title or "Partnership" in title:
        return (
            BASE_SUPPORT_INSTRUCTIONS
            + f"\n4. For **partnership requests**, ping {GREY_R_MENTION} and {RAY_C_MENTION}."
        )
    return BASE_SUPPORT_INSTRUCTIONS

try:
    import discord
    from discord import app_commands
except Exception as exc:  # pragma: no cover - defensive import hook
    log.warning("Delta runtime patches were not installed: %s", exc)
else:
    STAFF_ROLE_ID = 1539005030189891684
    ADMIN_ROLE_ID = 1539005297417519205
    TRANSCRIPT_CHANNEL_ID = 1539005101941850274

    DM_TICKET_OWNER_MARKER = "Delta DM Ticket Owner:"
    DM_TICKET_CATEGORY_MARKER = "Delta Ticket Category:"
    DM_TICKET_CLAIM_MARKER = "Delta Ticket Claimed By:"

    DELTA_RED = 0xC8102E
    DELTA_BLUE = 0x003087
    FOOTER_TEXT = "Delta Air Lines • Keep Climbing"

    CLAIM_LOCKS: dict[int, asyncio.Lock] = {}

    # Standalone revoke stays removed, but ticket admin punish/unpunish remains
    # available and is logged by the command audit hook below.
    REMOVED_ROOT_COMMANDS = {"revoke"}

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

    def _format_namespace_value(value: Any) -> str:
        if isinstance(value, app_commands.Choice):
            return f"{value.name} (`{value.value}`)"
        if isinstance(value, discord.Member):
            return f"{value.mention} (`{value.id}`)"
        if isinstance(value, discord.User):
            return f"{value.mention} (`{value.id}`)"
        if isinstance(value, discord.Role):
            return f"{value.mention} (`{value.id}`)"
        if isinstance(value, discord.TextChannel):
            return f"{value.mention} (`{value.id}`)"
        if isinstance(value, discord.Attachment):
            return f"{value.filename} ({value.url})"
        return str(value)

    def _namespace_lines(namespace: Any) -> list[str]:
        lines: list[str] = []
        raw = getattr(namespace, "__dict__", {})
        for key, value in raw.items():
            if key.startswith("_") or key in {"interaction", "self"} or value is None:
                continue
            safe = _format_namespace_value(value)
            if len(safe) > 250:
                safe = safe[:247] + "..."
            lines.append(f"**{key}:** {safe}")
        return lines

    async def _send_to_log_channel(
        client: discord.Client,
        *,
        title: str,
        description: str,
        color: int = DELTA_BLUE,
    ) -> None:
        channel = client.get_channel(TRANSCRIPT_CHANNEL_ID)
        if channel is None:
            try:
                channel = await client.fetch_channel(TRANSCRIPT_CHANNEL_ID)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
                log.warning("Could not fetch Delta log channel: %s", exc)
                return
        if not isinstance(channel, discord.TextChannel):
            return
        try:
            await channel.send(embed=_activity_embed(title=title, description=description, color=color))
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
            log.warning("Could not send Delta log entry: %s", exc)

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

    async def _log_slash_command(
        interaction: discord.Interaction,
        command_name: str,
        namespace: Any,
    ) -> None:
        user = interaction.user
        channel = interaction.channel
        guild = interaction.guild

        description = [
            f"**Command:** `/{command_name}`",
            f"**Used By:** {user.mention} (`{user.id}`)",
        ]
        if guild is not None:
            description.append(f"**Server:** {guild.name} (`{guild.id}`)")
        if isinstance(channel, discord.TextChannel):
            description.append(f"**Channel:** {channel.mention} (`{channel.id}`)")
            owner_id = _get_topic_value(channel.topic or "", DM_TICKET_OWNER_MARKER)
            if owner_id is not None:
                description.append(f"**Ticket Customer ID:** `{owner_id}`")
        options = _namespace_lines(namespace)
        if options:
            description.append("**Options:**")
            description.extend(options)

        message = "\n".join(description)
        await _send_to_log_channel(
            interaction.client,
            title="Slash Command Activity",
            description=message,
            color=DELTA_BLUE,
        )

        if isinstance(channel, discord.TextChannel) and _is_ticket_channel(channel):
            try:
                await channel.send(
                    embed=_activity_embed(
                        title="Ticket Command Activity",
                        description=message,
                        color=DELTA_BLUE,
                    ),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
                log.warning("Could not post ticket command activity: %s", exc)

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
        description = (
            f"**Ticket:** {channel.mention} (`{channel.id}`)\n"
            f"**Support:** {member.mention}\n"
            f"**Support ID:** `{member.id}`"
        )
        if owner_id is not None:
            description += f"\n**Customer ID:** `{owner_id}`"
        if sender is not None:
            try:
                await sender(title, description, color=color)
                return
            except Exception as exc:  # pragma: no cover - defensive runtime patch
                log.warning("Could not send claim server log through bot helper: %s", exc)
        await _send_to_log_channel(interaction.client, title=title, description=description, color=color)

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
        if not _member_has_role(member, STAFF_ROLE_ID):
            await _reply_once(interaction, "Only authorized Delta support staff can claim tickets.")
            return

        # Acknowledge before waiting for another claim or Discord's channel API.
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        lock = CLAIM_LOCKS.setdefault(channel.id, asyncio.Lock())
        async with lock:
            try:
                fresh_channel = await channel.guild.fetch_channel(channel.id)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
                await _reply_once(interaction, f"I could not refresh this ticket: {exc}")
                return
            from config import GUILD_ID, TICKET_CATEGORY_ID
            if (
                not isinstance(fresh_channel, discord.TextChannel)
                or fresh_channel.guild.id != GUILD_ID
                or fresh_channel.category_id != TICKET_CATEGORY_ID
                or not _is_ticket_channel(fresh_channel)
            ):
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

    async def _block_removed_root_command(
        interaction: discord.Interaction,
        command_name: str,
        namespace: Any,
    ) -> bool:
        root_name = command_name.split()[0]
        if root_name in REMOVED_ROOT_COMMANDS:
            await _reply_once(interaction, "This standalone moderation command has been removed. Use `/ticket admin` punishment controls when needed.")
            return True
        return False

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
            selected_command = getattr(getattr(namespace, "command", None), "value", None)
            if command_name == "close" or (
                command_name in {"ticket control", "ticket admin"} and selected_command == "close"
            ):
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
            if await _block_removed_root_command(interaction, command_name, namespace):
                return None
            if await _block_invalid_ticket_admin_claims(interaction, command_name, namespace):
                return None

            watchdog = asyncio.create_task(
                _auto_defer_if_still_pending(interaction, command_name, namespace)
            )
            try:
                return await _original_command_invoke(self, interaction, namespace)
            finally:
                watchdog.cancel()
                # Modal commands must respond before potentially slow audit I/O.
                try:
                    await _log_slash_command(interaction, command_name, namespace)
                except Exception as exc:  # pragma: no cover - logging must not break commands
                    log.warning("Could not log slash command %s: %s", command_name, exc)

        discord.InteractionResponse.send_message = _send_message_or_followup
        app_commands.Command._invoke_with_namespace = _invoke_with_auto_defer
        discord.InteractionResponse._delta_auto_ack_installed = True

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

    if not getattr(discord.Guild, "_delta_ticket_create_log_installed", False):
        _original_create_text_channel = discord.Guild.create_text_channel

        async def _create_text_channel_with_ticket_log(
            self: discord.Guild,
            name: str,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            channel = await _original_create_text_channel(self, name, *args, **kwargs)
            if isinstance(channel, discord.TextChannel) and _is_ticket_channel(channel):
                owner_id = _get_topic_value(channel.topic or "", DM_TICKET_OWNER_MARKER)
                category_key = _get_topic_value(channel.topic or "", DM_TICKET_CATEGORY_MARKER)
                await _send_to_log_channel(
                    self._state._get_client(),
                    title="Ticket Created",
                    description=(
                        f"**Ticket:** {channel.mention} (`{channel.id}`)\n"
                        f"**Channel Name:** `{channel.name}`\n"
                        f"**Customer ID:** `{owner_id or 'unknown'}`\n"
                        f"**Category:** `{category_key or 'unknown'}`"
                    ),
                    color=DELTA_BLUE,
                )
            return channel

        discord.Guild.create_text_channel = _create_text_channel_with_ticket_log
        discord.Guild._delta_ticket_create_log_installed = True

    if not getattr(discord.TextChannel, "_delta_ticket_delete_log_installed", False):
        _original_text_channel_delete = discord.TextChannel.delete

        async def _delete_with_ticket_log(
            self: discord.TextChannel,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            if _is_ticket_channel(self):
                owner_id = _get_topic_value(self.topic or "", DM_TICKET_OWNER_MARKER)
                category_key = _get_topic_value(self.topic or "", DM_TICKET_CATEGORY_MARKER)
                reason = kwargs.get("reason") or "No reason provided."
                await _send_to_log_channel(
                    self._state._get_client(),
                    title="Ticket Deleted",
                    description=(
                        f"**Ticket ID:** `{self.id}`\n"
                        f"**Channel Name:** `{self.name}`\n"
                        f"**Customer ID:** `{owner_id or 'unknown'}`\n"
                        f"**Category:** `{category_key or 'unknown'}`\n"
                        f"**Reason:** {reason}"
                    ),
                    color=DELTA_RED,
                )
            return await _original_text_channel_delete(self, *args, **kwargs)

        discord.TextChannel.delete = _delete_with_ticket_log
        discord.TextChannel._delta_ticket_delete_log_installed = True

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
                        value=support_instructions_for(embed.title or ""),
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
