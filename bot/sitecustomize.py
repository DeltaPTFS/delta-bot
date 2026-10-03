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
DM_TICKET_OWNER_MARKER = "Delta DM Ticket Owner:"
DM_TICKET_CATEGORY_MARKER = "Delta Ticket Category:"
DM_TICKET_CLAIM_MARKER = "Delta Ticket Claimed By:"
DM_TICKET_SUPPORT_MARKER = "Delta Ticket Support:"

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
    def _topic_value(topic: str, marker: str) -> str | None:
        for line in topic.splitlines():
            if line.startswith(marker):
                return line[len(marker):].strip() or None
        return None

    def _support_ids(topic: str) -> set[int]:
        raw = _topic_value(topic, DM_TICKET_SUPPORT_MARKER)
        if raw is None:
            return set()
        ids: set[int] = set()
        for piece in raw.replace(",", " ").split():
            if piece.isdigit():
                ids.add(int(piece))
        return ids

    def _is_ticket_channel(channel: discord.abc.GuildChannel | None) -> bool:
        return isinstance(channel, discord.TextChannel) and (
            _topic_value(channel.topic or "", DM_TICKET_OWNER_MARKER) is not None
            or _topic_value(channel.topic or "", DM_TICKET_CATEGORY_MARKER) is not None
        )

    def _namespace_summary(namespace: Any) -> str:
        values: list[str] = []
        for name in ("command", "action", "member", "format", "punishment", "message_id"):
            value = getattr(namespace, name, None)
            if value is None:
                continue
            if hasattr(value, "value"):
                value = value.value
            if hasattr(value, "mention"):
                value = value.mention
            values.append(f"**{name.replace('_', ' ').title()}:** {value}")
        return "\n".join(values) if values else "No command options recorded."

    async def _send_ticket_audit(
        channel: discord.TextChannel,
        *,
        title: str,
        actor: discord.abc.User | None = None,
        details: str = "",
        color: int = 0x003087,
    ) -> None:
        if not _is_ticket_channel(channel):
            return
        description = []
        if actor is not None:
            description.append(f"**Action By:** {actor.mention} (`{actor.id}`)")
        owner_id = _topic_value(channel.topic or "", DM_TICKET_OWNER_MARKER)
        if owner_id is not None:
            description.append(f"**Customer ID:** `{owner_id}`")
        if details:
            description.append(details)
        embed = discord.Embed(
            title=f"Ticket Audit | {title}",
            description="\n".join(description) if description else "Action recorded.",
            color=color,
        )
        embed.set_footer(text="Delta Air Lines • Ticket Command Record")
        try:
            await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
                _delta_audit_skip=True,
            )
        except TypeError:
            await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except (discord.Forbidden, discord.NotFound, discord.HTTPException) as exc:
            log.warning("Could not post ticket audit log in %s: %s", channel.id, exc)

    def _member_can_control_reply(channel: discord.TextChannel, member: discord.Member) -> bool:
        if member.guild_permissions.manage_messages or member.guild_permissions.administrator:
            return True
        topic = channel.topic or ""
        return (
            _topic_value(topic, DM_TICKET_CLAIM_MARKER) == str(member.id)
            or member.id in _support_ids(topic)
        )

    async def _reply_control_callback(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        message_id: str,
        new_message: str | None = None,
    ) -> None:
        channel = interaction.channel
        member = interaction.user
        if not isinstance(channel, discord.TextChannel) or not isinstance(member, discord.Member) or not _is_ticket_channel(channel):
            await interaction.response.send_message(
                "Use `/reply-control` inside the ticket channel.",
                ephemeral=True,
            )
            return
        if not _member_can_control_reply(channel, member):
            await interaction.response.send_message(
                "Only the claimant, assigned support, or a member with Manage Messages can control replies.",
                ephemeral=True,
            )
            return
        if not message_id.isdigit():
            await interaction.response.send_message("Enter a valid Discord message ID.", ephemeral=True)
            return
        try:
            target = await channel.fetch_message(int(message_id))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
            await interaction.response.send_message(f"I could not find that reply record: {exc}", ephemeral=True)
            return
        if interaction.client.user is not None and target.author.id != interaction.client.user.id:
            await interaction.response.send_message(
                "That message is not a HelpDesk bot reply record.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        action_value = action.value
        if action_value == "delete":
            try:
                await target.delete(reason=f"Reply record deleted by {member}")
            except (discord.Forbidden, discord.HTTPException) as exc:
                await interaction.followup.send(f"Could not delete that reply record: {exc}", ephemeral=True)
                return
            await _send_ticket_audit(
                channel,
                title="/reply-control delete",
                actor=member,
                details=f"**Message ID:** `{message_id}`",
                color=0xC8102E,
            )
            await interaction.followup.send("Reply record deleted from the ticket.", ephemeral=True)
            return

        if not new_message:
            await interaction.followup.send("Enter the new message when using edit.", ephemeral=True)
            return
        if target.embeds:
            embed = target.embeds[0]
            embed.description = f"{embed.description or ''}\n\n**Edited Reply:**\n{new_message[:3500]}"
            embed.set_footer(text=f"Edited by {member} ({member.id})")
            try:
                await target.edit(embed=embed)
            except (discord.Forbidden, discord.HTTPException) as exc:
                await interaction.followup.send(f"Could not edit that reply record: {exc}", ephemeral=True)
                return
        else:
            try:
                await target.edit(content=new_message[:2000])
            except (discord.Forbidden, discord.HTTPException) as exc:
                await interaction.followup.send(f"Could not edit that reply record: {exc}", ephemeral=True)
                return
        await _send_ticket_audit(
            channel,
            title="/reply-control edit",
            actor=member,
            details=f"**Message ID:** `{message_id}`",
            color=0x003087,
        )
        await interaction.followup.send("Reply record edited in the ticket.", ephemeral=True)

    def _install_reply_control_command(tree: app_commands.CommandTree) -> None:
        if getattr(tree, "_delta_reply_control_installed", False):
            return

        command = app_commands.command(
            name="reply-control",
            description="Edit or delete a HelpDesk reply record inside this ticket.",
        )(_reply_control_callback)
        command = app_commands.describe(
            action="Choose whether to edit or delete the reply record.",
            message_id="The Discord message ID of the bot reply record in this ticket.",
            new_message="Required only when editing the reply record.",
        )(command)
        command = app_commands.choices(
            action=[
                app_commands.Choice(name="Edit Reply Record", value="edit"),
                app_commands.Choice(name="Delete Reply Record", value="delete"),
            ]
        )(command)
        try:
            tree.add_command(command, override=True)
            tree._delta_reply_control_installed = True
        except Exception as exc:
            log.warning("Could not install /reply-control command: %s", exc)

    if not getattr(discord.InteractionResponse, "_delta_auto_ack_installed", False):
        _original_send_message = discord.InteractionResponse.send_message
        _original_command_invoke = app_commands.Command._invoke_with_namespace
        _original_tree_sync = app_commands.CommandTree.sync

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
                result = await _original_command_invoke(self, interaction, namespace)
                channel = interaction.channel
                if isinstance(channel, discord.TextChannel) and _is_ticket_channel(channel):
                    if command_name.startswith("ticket") or command_name.startswith("reply") or command_name == "format":
                        await _send_ticket_audit(
                            channel,
                            title=f"/{command_name}",
                            actor=interaction.user,
                            details=_namespace_summary(namespace),
                        )
                return result
            finally:
                watchdog.cancel()

        async def _sync_with_reply_control(self: app_commands.CommandTree, *args: Any, **kwargs: Any) -> Any:
            _install_reply_control_command(self)
            return await _original_tree_sync(self, *args, **kwargs)

        discord.InteractionResponse.send_message = _send_message_or_followup
        app_commands.Command._invoke_with_namespace = _invoke_with_auto_defer
        app_commands.CommandTree.sync = _sync_with_reply_control
        discord.InteractionResponse._delta_auto_ack_installed = True

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
            audit_skip = kwargs.pop("_delta_audit_skip", False)
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

            message = await _original_text_channel_send(self, *args, **kwargs)

            if not audit_skip:
                audit_embed = embed if isinstance(embed, discord.Embed) else None
                title = audit_embed.title if audit_embed else ""
                description = audit_embed.description if audit_embed else ""
                if title and ("Ticket Claimed" in title or "Ticket Unclaimed" in title):
                    await _send_ticket_audit(
                        self,
                        title=title.replace("<:Support:1540927430179553321>", "").strip(),
                        details=description or f"**Message ID:** `{message.id}`",
                        color=0x003087 if "Claimed" in title else 0xC8102E,
                    )

            return message

        discord.TextChannel.send = _send_with_ticket_instruction_patch
        discord.TextChannel._delta_ticket_instruction_patch_installed = True
