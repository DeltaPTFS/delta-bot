"""Extra runtime controls for Delta HelpDesk tickets.

Loaded from config.py after the base config is imported. This module keeps the
server-log channel ticket-only and adds ticket reply controls without touching
main.py's command registration directly.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("delta-helpdesk.ticket-controls")

try:
    import discord
    from discord import app_commands
except Exception as exc:  # pragma: no cover
    log.warning("Delta ticket controls were not installed: %s", exc)
else:
    STAFF_ROLE_ID = 1539005030189891684
    ADMIN_ROLE_ID = 1539005297417519205
    TRANSCRIPT_CHANNEL_ID = 1539005101941850274
    DM_TICKET_OWNER_MARKER = "Delta DM Ticket Owner:"
    DM_TICKET_CATEGORY_MARKER = "Delta Ticket Category:"
    DELTA_BLUE = 0x003087
    DELTA_RED = 0xC8102E
    FOOTER_TEXT = "Delta Air Lines • Keep Climbing"

    def _has_role(member: discord.Member, role_id: int) -> bool:
        return any(role.id == role_id for role in member.roles)

    def _is_staff_or_admin(member: discord.Member) -> bool:
        return _has_role(member, STAFF_ROLE_ID) or _has_role(member, ADMIN_ROLE_ID)

    def _is_admin(member: discord.Member) -> bool:
        return _has_role(member, ADMIN_ROLE_ID)

    def _topic_value(topic: str, marker: str) -> str | None:
        for line in topic.splitlines():
            if line.startswith(marker):
                return line.removeprefix(marker).strip() or None
        return None

    def _is_ticket_channel(channel: discord.TextChannel) -> bool:
        topic = channel.topic or ""
        return (
            _topic_value(topic, DM_TICKET_OWNER_MARKER) is not None
            or _topic_value(topic, DM_TICKET_CATEGORY_MARKER) is not None
        )

    def _ticket_owner_id(channel: discord.TextChannel) -> str | None:
        return _topic_value(channel.topic or "", DM_TICKET_OWNER_MARKER)

    def _embed(title: str, description: str, *, color: int = DELTA_BLUE) -> discord.Embed:
        embed = discord.Embed(title=title, description=description, color=color)
        embed.set_footer(text=FOOTER_TEXT)
        return embed

    def _reply_dm_embed(content: str) -> discord.Embed:
        safe = content if len(content) <= 4000 else f"{content[:3997]}..."
        return _embed("Delta Support Reply", f"💬 **Delta Support Reply**\n\n{safe}", color=DELTA_BLUE)

    def _reply_staff_embed(content: str, author: discord.Member | None, owner_id: str | None) -> discord.Embed:
        safe = content if len(content) <= 4000 else f"{content[:3997]}..."
        embed = _embed("Support Reply Record", safe, color=DELTA_BLUE)
        if author is not None:
            embed.set_author(name=str(author), icon_url=author.display_avatar.url)
        if owner_id is not None:
            embed.add_field(name="Customer ID", value=f"`{owner_id}`", inline=True)
        return embed

    def _ensure_store(client: discord.Client) -> None:
        if not hasattr(client, "delta_reply_records"):
            client.delta_reply_records = {}
        if not hasattr(client, "delta_deleted_reply_records"):
            client.delta_deleted_reply_records = {}
        if not hasattr(client, "delta_reply_sequence"):
            client.delta_reply_sequence = 0

    def _latest_record(
        client: discord.Client,
        channel_id: int,
        *,
        author_id: int | None = None,
        include_deleted: bool = False,
    ) -> dict[str, Any] | None:
        _ensure_store(client)
        records = list(client.delta_reply_records.get(channel_id, []))
        if include_deleted:
            records += list(client.delta_deleted_reply_records.get(channel_id, []))
        for record in sorted(records, key=lambda item: item.get("seq", 0), reverse=True):
            if author_id is not None and record.get("author_id") != author_id:
                continue
            if not include_deleted and record.get("deleted"):
                continue
            return record
        return None

    async def _reply_once(interaction: discord.Interaction, message: str, *, ephemeral: bool = True) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(message, ephemeral=ephemeral)

    async def _fetch_message(client: discord.Client, channel_id: int | None, message_id: int | None) -> discord.Message | None:
        if channel_id is None or message_id is None:
            return None
        channel = client.get_channel(channel_id)
        if channel is None:
            try:
                channel = await client.fetch_channel(channel_id)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                return None
        if not hasattr(channel, "fetch_message"):
            return None
        try:
            return await channel.fetch_message(message_id)
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            return None

    async def _send_ticket_log(client: discord.Client, title: str, description: str, *, color: int = DELTA_BLUE) -> None:
        channel = client.get_channel(TRANSCRIPT_CHANNEL_ID)
        if channel is None:
            try:
                channel = await client.fetch_channel(TRANSCRIPT_CHANNEL_ID)
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                return
        if isinstance(channel, discord.TextChannel):
            await channel.send(embed=_embed(title, description, color=color), allowed_mentions=discord.AllowedMentions.none())

    async def _run_message_action(
        interaction: discord.Interaction,
        *,
        action: str,
        content: str | None = None,
        target_member: discord.Member | None = None,
        admin_override: bool = False,
    ) -> None:
        channel = interaction.channel
        actor = interaction.user
        if not isinstance(channel, discord.TextChannel) or not isinstance(actor, discord.Member) or not _is_ticket_channel(channel):
            await _reply_once(interaction, "Use this command inside a ticket channel.")
            return
        if admin_override and not _is_admin(actor):
            await _reply_once(interaction, "Only Founders can use `/msg config admin`.")
            return
        if not admin_override and not _has_role(actor, STAFF_ROLE_ID):
            await _reply_once(interaction, "Only members with the Delta Support role can manage ticket replies.")
            return
        author_id = None if admin_override else actor.id
        if target_member is not None:
            author_id = target_member.id
        record = _latest_record(interaction.client, channel.id, author_id=author_id, include_deleted=admin_override)
        if record is None:
            await _reply_once(interaction, "No reply record was found for that request.")
            return

        if action == "edit":
            if not content:
                await _reply_once(interaction, "Add the new reply text.")
                return
            staff_message = await _fetch_message(interaction.client, record.get("channel_id"), record.get("staff_message_id"))
            dm_message = await _fetch_message(interaction.client, record.get("dm_channel_id"), record.get("dm_message_id"))
            if staff_message is not None:
                await staff_message.edit(embed=_reply_staff_embed(content, actor, record.get("owner_id")), content=None, allowed_mentions=discord.AllowedMentions.none())
            if dm_message is not None:
                await dm_message.edit(embed=_reply_dm_embed(content), content=None, allowed_mentions=discord.AllowedMentions.none())
            record["content"] = content
            record["deleted"] = False
            await channel.send(embed=_embed("Ticket Reply Edited", f"**Edited By:** {actor.mention} (`{actor.id}`)\n**Reply Author ID:** `{record.get('author_id')}`"), allowed_mentions=discord.AllowedMentions.none())
            await _reply_once(interaction, "Reply record edited.")
            return

        if action == "delete":
            staff_message = await _fetch_message(interaction.client, record.get("channel_id"), record.get("staff_message_id"))
            dm_message = await _fetch_message(interaction.client, record.get("dm_channel_id"), record.get("dm_message_id"))
            if staff_message is not None:
                await staff_message.delete(reason=f"Reply record deleted by {actor}")
            if dm_message is not None:
                await dm_message.delete()
            record["deleted"] = True
            _ensure_store(interaction.client)
            deleted = interaction.client.delta_deleted_reply_records.setdefault(channel.id, [])
            if record not in deleted:
                deleted.append(record)
            await channel.send(embed=_embed("Ticket Reply Deleted", f"**Deleted By:** {actor.mention} (`{actor.id}`)\n**Reply Author ID:** `{record.get('author_id')}`", color=DELTA_RED), allowed_mentions=discord.AllowedMentions.none())
            await _reply_once(interaction, "Reply record deleted.")
            return

        if action == "restore":
            content = record.get("content") or "Restored reply."
            owner_id = record.get("owner_id") or _ticket_owner_id(channel)
            staff = await channel.send(embed=_reply_staff_embed(content, actor, owner_id), allowed_mentions=discord.AllowedMentions.none())
            record["staff_message_id"] = staff.id
            record["channel_id"] = channel.id
            if owner_id is not None and str(owner_id).isdigit():
                try:
                    user = interaction.client.get_user(int(owner_id)) or await interaction.client.fetch_user(int(owner_id))
                    dm = await user.send(embed=_reply_dm_embed(content), allowed_mentions=discord.AllowedMentions.none())
                    record["dm_message_id"] = dm.id
                    record["dm_channel_id"] = dm.channel.id
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    pass
            record["deleted"] = False
            await channel.send(embed=_embed("Ticket Reply Restored", f"**Restored By:** {actor.mention} (`{actor.id}`)\n**Reply Author ID:** `{record.get('author_id')}`"), allowed_mentions=discord.AllowedMentions.none())
            await _reply_once(interaction, "Deleted reply restored.")
            return
        await _reply_once(interaction, "Unknown message action.")

    async def _handle_support_ban(interaction: discord.Interaction, namespace: Any) -> bool:
        selected = getattr(getattr(namespace, "command", None), "value", None)
        if selected not in {"ban_support", "unban_support"}:
            return False
        actor = interaction.user
        target = getattr(namespace, "member", None)
        if not isinstance(actor, discord.Member) or not _is_admin(actor):
            await _reply_once(interaction, "Only Founders can ban or unban support from tickets.")
            return True
        if not isinstance(target, discord.Member):
            await _reply_once(interaction, "Select a support member for that command.")
            return True
        if not hasattr(interaction.client, "ticket_restrictions"):
            interaction.client.ticket_restrictions = {}
        if not hasattr(interaction.client, "admin_undo_actions"):
            interaction.client.admin_undo_actions = []
        previous = interaction.client.ticket_restrictions.get(target.id)
        interaction.client.admin_undo_actions.append(("punish", target.id, previous))
        if selected == "ban_support":
            interaction.client.ticket_restrictions[target.id] = ("support ban", None)
            title = "Support Banned From Tickets"
            result = f"{target.mention} has been banned from ticket support commands."
            color = DELTA_RED
        else:
            interaction.client.ticket_restrictions.pop(target.id, None)
            title = "Support Unbanned From Tickets"
            result = f"{target.mention} has been unbanned from ticket support commands."
            color = DELTA_BLUE
        await _reply_once(interaction, result)
        await _send_ticket_log(interaction.client, title, f"**Support:** {target.mention} (`{target.id}`)\n**Action By:** {actor.mention} (`{actor.id}`)", color=color)
        return True

    if not getattr(discord.InteractionResponse, "_delta_ticket_controls_invoke_installed", False):
        _previous_invoke = app_commands.Command._invoke_with_namespace

        async def _invoke_with_ticket_controls(self: app_commands.Command, interaction: discord.Interaction, namespace: app_commands.Namespace) -> Any:
            command_name = getattr(self, "qualified_name", getattr(self, "name", "unknown"))
            if command_name == "ticket admin" and await _handle_support_ban(interaction, namespace):
                return None
            return await _previous_invoke(self, interaction, namespace)

        app_commands.Command._invoke_with_namespace = _invoke_with_ticket_controls
        discord.InteractionResponse._delta_ticket_controls_invoke_installed = True

    if not getattr(app_commands.CommandTree, "_delta_ticket_extra_commands_installed", False):
        _previous_sync = app_commands.CommandTree.sync

        @app_commands.command(name="ping", description="Ping the customer who opened the current ticket.")
        async def _ping_customer(interaction: discord.Interaction) -> None:
            channel = interaction.channel
            actor = interaction.user
            if not isinstance(channel, discord.TextChannel) or not isinstance(actor, discord.Member) or not _is_ticket_channel(channel):
                await _reply_once(interaction, "Use `/ping` inside a ticket channel.")
                return
            if not _has_role(actor, STAFF_ROLE_ID):
                await _reply_once(interaction, "Only members with the Delta Support role can ping ticket customers.")
                return
            owner_id = _ticket_owner_id(channel)
            if owner_id is None:
                await _reply_once(interaction, "This ticket does not have a customer to ping.")
                return
            await channel.send(f"<@{owner_id}> Delta Support is requesting your attention in this ticket.")
            await _reply_once(interaction, "Ticket customer pinged.")

        message_group = app_commands.Group(name="message", description="Edit or delete your recent ticket reply.")
        msg_group = app_commands.Group(name="msg", description="Founder reply override tools.")
        msg_config_group = app_commands.Group(name="config", description="Reply override configuration.")
        action_choices = [
            app_commands.Choice(name="Edit Recent Reply", value="edit"),
            app_commands.Choice(name="Delete Recent Reply", value="delete"),
        ]
        admin_action_choices = [
            app_commands.Choice(name="Restore Deleted Reply", value="restore"),
            app_commands.Choice(name="Edit Reply", value="edit"),
            app_commands.Choice(name="Delete Reply", value="delete"),
        ]

        @message_group.command(name="config", description="Edit or delete the latest reply you sent in this ticket.")
        @app_commands.describe(action="Action to run.", content="New text when editing.")
        @app_commands.choices(action=action_choices)
        async def _message_config(interaction: discord.Interaction, action: app_commands.Choice[str], content: str | None = None) -> None:
            await _run_message_action(interaction, action=action.value, content=content)

        @message_group.command(name="edit", description="Edit the latest reply you sent in this ticket.")
        @app_commands.describe(content="New reply text.")
        async def _message_edit(interaction: discord.Interaction, content: str) -> None:
            await _run_message_action(interaction, action="edit", content=content)

        @msg_config_group.command(name="admin", description="Founder override for ticket replies.")
        @app_commands.describe(action="Action to run.", member="Reply author to target.", content="New text when editing.")
        @app_commands.choices(action=admin_action_choices)
        async def _msg_config_admin(interaction: discord.Interaction, action: app_commands.Choice[str], member: discord.Member | None = None, content: str | None = None) -> None:
            await _run_message_action(interaction, action=action.value, content=content, target_member=member, admin_override=True)

        msg_group.add_command(msg_config_group)

        def _patch_ticket_admin_choices(tree: app_commands.CommandTree) -> None:
            ticket_group = tree.get_command("ticket", type=discord.AppCommandType.chat_input)
            if ticket_group is None:
                return
            admin_command = None
            for command in getattr(ticket_group, "commands", []):
                if getattr(command, "name", None) == "admin":
                    admin_command = command
                    break
            if admin_command is None:
                return
            for parameter in getattr(admin_command, "parameters", []):
                if getattr(parameter, "name", None) != "command":
                    continue
                choices = list(getattr(parameter, "choices", None) or [])
                values = {getattr(choice, "value", None) for choice in choices}
                if "ban_support" not in values:
                    choices.append(app_commands.Choice(name="Ban Support", value="ban_support"))
                if "unban_support" not in values:
                    choices.append(app_commands.Choice(name="Unban Support", value="unban_support"))
                parameter.choices = choices

        def _ensure_extra_commands(tree: app_commands.CommandTree) -> None:
            _patch_ticket_admin_choices(tree)
            for command in (_ping_customer,):
                if tree.get_command(command.name, type=discord.AppCommandType.chat_input) is None:
                    tree.add_command(command, override=True)
            for group in (message_group, msg_group):
                if tree.get_command(group.name, type=discord.AppCommandType.chat_input) is None:
                    tree.add_command(group, override=True)

        async def _sync_with_extra_commands(self: app_commands.CommandTree, *args: Any, **kwargs: Any) -> Any:
            _ensure_extra_commands(self)
            return await _previous_sync(self, *args, **kwargs)

        app_commands.CommandTree.sync = _sync_with_extra_commands
        app_commands.CommandTree._delta_ticket_extra_commands_installed = True

    if not getattr(discord.User, "_delta_reply_dm_tracker_installed", False):
        _previous_user_send = discord.User.send

        async def _user_send_tracker(self: discord.User, *args: Any, **kwargs: Any) -> Any:
            result = await _previous_user_send(self, *args, **kwargs)
            try:
                client = self._state._get_client()
                data = getattr(client, "_delta_current_reply", None)
                if isinstance(data, dict) and result is not None:
                    data["dm_message_id"] = result.id
                    data["dm_channel_id"] = result.channel.id
            except Exception as exc:  # pragma: no cover
                log.warning("Could not track reply DM message: %s", exc)
            return result

        discord.User.send = _user_send_tracker
        discord.User._delta_reply_dm_tracker_installed = True

    if not getattr(discord.TextChannel, "_delta_ticket_controls_send_installed", False):
        _previous_channel_send = discord.TextChannel.send

        async def _send_filter_and_tracker(self: discord.TextChannel, *args: Any, **kwargs: Any) -> Any:
            embed = kwargs.get("embed")
            if self.id == TRANSCRIPT_CHANNEL_ID and isinstance(embed, discord.Embed):
                title = embed.title or ""
                description = embed.description or ""
                ticket_related = title.startswith("Ticket") or "**Ticket" in description or "ticket" in description.casefold()
                release_update = "Delta HelpDesk — Update" in title or "HelpDesk Version" in title or "Deployment ID:" in description
                if not ticket_related and not release_update:
                    return None

            result = await _previous_channel_send(self, *args, **kwargs)

            try:
                client = self._state._get_client()
                data = getattr(client, "_delta_current_reply", None)
                if isinstance(data, dict) and data.get("channel_id") == self.id and result is not None:
                    _ensure_store(client)
                    client.delta_reply_sequence += 1
                    record = {
                        "seq": client.delta_reply_sequence,
                        "channel_id": self.id,
                        "staff_message_id": result.id,
                        "author_id": data.get("author_id"),
                        "owner_id": data.get("owner_id"),
                        "content": data.get("content") or "",
                        "dm_message_id": data.get("dm_message_id"),
                        "dm_channel_id": data.get("dm_channel_id"),
                        "deleted": False,
                    }
                    client.delta_reply_records.setdefault(self.id, []).append(record)
            except Exception as exc:  # pragma: no cover
                log.warning("Could not track ticket reply: %s", exc)
            return result

        discord.TextChannel.send = _send_filter_and_tracker
        discord.TextChannel._delta_ticket_controls_send_installed = True
