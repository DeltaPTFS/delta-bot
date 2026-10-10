"""Exercise ticket commands and the ready-to-announcement path without Discord I/O."""

from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))

import discord
from discord import app_commands
import main
import deployment_update_guard
import runtime_ticket_controls
import sitecustomize


async def history(messages=(), failure=None):
    if failure is not None:
        raise failure
    for message in messages:
        yield message


def forbidden():
    return discord.Forbidden(SimpleNamespace(status=403, reason="Forbidden"), "Missing permissions")


class StartupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = main.DeltaBot()
        self.bot._connection.user = SimpleNamespace(id=123)
        main.register_commands(self.bot.tree)
        self.channel = MagicMock(spec=discord.TextChannel)
        self.channel.id = 456
        self.channel.name = "general-support-example"
        self.channel.mention = "<#456>"
        self.channel.category_id = main.TICKET_CATEGORY_ID
        self.channel.guild = MagicMock(spec=discord.Guild)
        self.channel.guild.id = main.GUILD_ID
        self.channel.topic = f"{main.DM_TICKET_OWNER_MARKER} 789\n{main.DM_TICKET_CATEGORY_MARKER} general_inquiries"
        self.channel.guild.fetch_channel = AsyncMock(return_value=self.channel)
        self.channel.edit = AsyncMock(side_effect=self.edit_topic)
        self.channel.send = AsyncMock(return_value=SimpleNamespace(id=1000))
        self.channel.history.side_effect = lambda **kwargs: history()
        self.member = MagicMock(spec=discord.Member)
        self.member.id = 321
        self.member.mention = "<@321>"
        self.member.roles = [SimpleNamespace(id=main.STAFF_ROLE_ID)]
        self.interaction = MagicMock(spec=discord.Interaction)
        self.interaction.user = self.member
        self.interaction.channel = self.channel
        self.interaction.guild = self.channel.guild
        self.interaction.guild_id = main.GUILD_ID
        self.interaction.client = self.bot
        self.interaction.response.is_done.return_value = False
        self.interaction.response.defer = AsyncMock(side_effect=self.defer)
        self.interaction.response.send_modal = AsyncMock()
        self.interaction.response.send_message = AsyncMock()
        self.interaction.followup.send = AsyncMock()
        self.bot._send_server_log = AsyncMock()
        sitecustomize.CLAIM_LOCKS.clear()

    async def asyncTearDown(self):
        await self.bot.close()

    async def defer(self, **kwargs):
        self.interaction.response.is_done.return_value = True

    async def edit_topic(self, *, topic, reason):
        self.channel.topic = topic
        return self.channel

    async def test_setup_syncs_all_commands_only_to_authorized_guild(self):
        synced = []

        async def remote_sync(tree, *, guild=None):
            names = {command.name for command in tree.get_commands(guild=guild)}
            synced.append((getattr(guild, "id", None), names))
            return tree.get_commands(guild=guild)

        with patch.object(app_commands.CommandTree, "sync", remote_sync):
            await self.bot.setup_hook()
        self.assertEqual(synced[0], (None, set()))
        self.assertEqual(synced[1], (main.GUILD_ID, {
            "panel", "version", "reply", "format", "ticket",
            "claim", "unclaim", "close", "ping", "message", "msg",
        }))
        self.assertEqual(self.bot.tree.get_commands(), [])
        admin = self.bot.tree.get_command("ticket", guild=discord.Object(id=main.GUILD_ID)).get_command("admin")
        choices = next(parameter.choices for parameter in admin.parameters if parameter.name == "command")
        self.assertTrue({"ban_support", "unban_support"}.issubset({choice.value for choice in choices}))

    async def test_registration_is_repeatable(self):
        main.register_commands(self.bot.tree)
        runtime_ticket_controls.register_extra_commands(self.bot.tree)
        runtime_ticket_controls.register_extra_commands(self.bot.tree)
        names = [command.name for command in self.bot.tree.get_commands()]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue({"claim", "unclaim", "close"}.issubset(names))

    async def test_claim_defers_and_persists_owner(self):
        await self.bot.tree.get_command("claim").callback(self.interaction)
        self.interaction.response.defer.assert_awaited_once_with(ephemeral=True)
        self.assertEqual(main.get_topic_value(self.channel.topic, main.DM_TICKET_CLAIM_MARKER), "321")
        self.bot._send_server_log.assert_awaited_once()

    async def test_claim_does_not_unclaim_on_repeat(self):
        self.channel.topic += f"\n{main.DM_TICKET_CLAIM_MARKER} 321"
        await self.bot.tree.get_command("claim").callback(self.interaction)
        self.channel.edit.assert_not_awaited()
        self.assertIn("already claimed", self.interaction.followup.send.call_args.args[0])

    async def test_claim_cannot_take_another_agent_ticket(self):
        self.channel.topic += f"\n{main.DM_TICKET_CLAIM_MARKER} 999"
        await self.bot.tree.get_command("claim").callback(self.interaction)
        self.channel.edit.assert_not_awaited()
        self.assertEqual(main.get_topic_value(self.channel.topic, main.DM_TICKET_CLAIM_MARKER), "999")

    async def test_claim_rejects_non_ticket_channel(self):
        self.channel.category_id = 0
        await self.bot.tree.get_command("claim").callback(self.interaction)
        self.channel.edit.assert_not_awaited()

    async def test_unclaim_removes_own_claim(self):
        self.channel.topic += f"\n{main.DM_TICKET_CLAIM_MARKER} 321"
        await self.bot.tree.get_command("unclaim").callback(self.interaction)
        self.assertIsNone(main.get_topic_value(self.channel.topic, main.DM_TICKET_CLAIM_MARKER))

    async def test_unclaim_rejects_other_agent(self):
        self.channel.topic += f"\n{main.DM_TICKET_CLAIM_MARKER} 999"
        await self.bot.tree.get_command("unclaim").callback(self.interaction)
        self.channel.edit.assert_not_awaited()

    async def test_non_staff_and_restricted_staff_fail_command_checks(self):
        for name in ("claim", "unclaim", "close"):
            command = self.bot.tree.get_command(name)
            self.member.roles = []
            self.assertFalse(await command._check_can_run(self.interaction))
            self.member.roles = [SimpleNamespace(id=main.STAFF_ROLE_ID)]
            self.bot.ticket_restrictions[self.member.id] = ("banned", None)
            self.assertFalse(await command._check_can_run(self.interaction))
            self.bot.ticket_restrictions.clear()

    async def test_close_opens_existing_modal_before_audit(self):
        command = self.bot.tree.get_command("close")
        self.interaction.command = command

        async def audit(*args):
            self.interaction.response.send_modal.assert_awaited_once()

        with patch.object(sitecustomize, "_log_slash_command", audit):
            await command._invoke_with_namespace(self.interaction, SimpleNamespace())
        modal = self.interaction.response.send_modal.call_args.args[0]
        self.assertIsInstance(modal, main.CloseReasonModal)
        self.interaction.response.defer.assert_not_awaited()

    async def test_close_rejects_non_ticket_channel(self):
        self.channel.topic = ""
        await self.bot.tree.get_command("close").callback(self.interaction)
        self.interaction.response.send_modal.assert_not_awaited()
        self.interaction.response.send_message.assert_awaited_once()

    async def test_presence_reaches_real_discord_client_method(self):
        self.bot.ws = SimpleNamespace(change_presence=AsyncMock())
        activity = discord.Activity(type=discord.ActivityType.watching, name="Tickets are boarding ✈️")
        await self.bot.change_presence(activity=activity)
        self.bot.ws.change_presence.assert_awaited_once_with(activity=activity, status="online")
        self.bot.ws = None

    async def test_ready_posts_announcement_even_if_presence_fails(self):
        self.bot.change_presence = AsyncMock(side_effect=TypeError("broken presence"))
        self.bot.get_channel = MagicMock(return_value=self.channel)
        self.bot.fetch_user = AsyncMock(return_value=SimpleNamespace(send=AsyncMock()))
        await self.bot.on_ready()
        self.channel.send.assert_awaited_once()
        self.assertIn("Delta HelpDesk — Update", self.channel.send.call_args.args[0])
        self.assertIn(f"Update {main.BOT_VERSION}", self.channel.send.call_args.args[0])
        self.bot.fetch_user.return_value.send.assert_awaited_once()

    async def test_release_skips_existing_deployment(self):
        existing = SimpleNamespace(author=self.bot.user, content=main.build_release_update_message())
        self.channel.history.side_effect = lambda **kwargs: history([existing])
        self.bot.get_channel = MagicMock(return_value=self.channel)
        await self.bot._post_release_update()
        self.channel.send.assert_not_awaited()

    async def test_release_posts_despite_missing_history_permission(self):
        self.channel.history.side_effect = lambda **kwargs: history(failure=forbidden())
        self.bot.get_channel = MagicMock(return_value=self.channel)
        await self.bot._post_release_update()
        self.channel.send.assert_awaited_once()

    async def test_release_keeps_message_limit_and_deployment_marker(self):
        self.bot.get_channel = MagicMock(return_value=self.channel)
        with patch.object(main, "build_release_update_message", return_value="x" * 5000):
            await self.bot._post_release_update()
        content = self.channel.send.call_args.args[0]
        self.assertLessEqual(len(content), 2000)
        self.assertIn(f"Deployment ID: `{main.deployed_source()}`", content)

    async def test_release_text_passes_real_ticket_log_filters(self):
        self.channel.id = main.UPDATE_CHANNEL_ID
        text = main.build_release_update_message()
        raw_send = AsyncMock(return_value=SimpleNamespace(id=1000))
        with patch.object(deployment_update_guard, "_previous_send", raw_send):
            await discord.TextChannel.send(self.channel, text)
            raw_send.assert_awaited_once_with(self.channel, text)
            await discord.TextChannel.send(self.channel, embed=discord.Embed(title="Member Joined"))
            self.assertEqual(raw_send.await_count, 1)


if __name__ == "__main__":
    unittest.main()
