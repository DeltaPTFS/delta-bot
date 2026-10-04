"""Ensure HelpDesk deployment update messages can post to the log channel.

This optional runtime patch preserves the ticket-only server-log filter while
explicitly allowing official HelpDesk deployment announcements.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("delta-helpdesk.deployment-update")

try:
    import discord
except Exception as exc:  # pragma: no cover
    log.warning("Delta deployment update guard was not installed: %s", exc)
else:
    UPDATE_CHANNEL_ID = 1539005101941850274
    DEPLOYMENT_MARKERS = (
        "Delta HelpDesk — Update",
        "HelpDesk Version",
        "Deployment ID:",
    )

    if not getattr(discord.TextChannel, "_delta_deployment_update_guard_installed", False):
        _previous_send = discord.TextChannel.send

        async def _send_with_deployment_update_allowlist(
            self: discord.TextChannel,
            *args: Any,
            **kwargs: Any,
        ) -> Any:
            content = ""
            if args and isinstance(args[0], str):
                content = args[0]
            elif isinstance(kwargs.get("content"), str):
                content = kwargs["content"]

            # The update message is text-based. Keeping this guard loaded before
            # ticket-only log filters makes the official version announcement
            # pass through normally while regular non-ticket embeds stay filtered.
            if self.id == UPDATE_CHANNEL_ID and any(marker in content for marker in DEPLOYMENT_MARKERS):
                return await _previous_send(self, *args, **kwargs)

            return await _previous_send(self, *args, **kwargs)

        discord.TextChannel.send = _send_with_deployment_update_allowlist
        discord.TextChannel._delta_deployment_update_guard_installed = True
