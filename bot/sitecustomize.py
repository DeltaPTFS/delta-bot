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

try:
    import discord
    from discord import app_commands
except Exception as exc:  # pragma: no cover - defensive import hook
    log.warning("Delta interaction auto-ack patch was not installed: %s", exc)
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
