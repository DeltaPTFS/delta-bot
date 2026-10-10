"""Runtime presence override for Delta HelpDesk.

This keeps the bot activity text configurable without touching the main
entrypoint. It runs when config.py imports this optional runtime extension.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("delta-helpdesk.presence")

WATCHING_STATUS = "staff forget to claim tickets"

try:
    import discord
except Exception as exc:  # pragma: no cover
    log.warning("Delta presence patch was not installed: %s", exc)
else:
    if not getattr(discord.Client, "_delta_presence_status_patch_installed", False):
        _original_change_presence = discord.Client.change_presence

        async def _change_presence_with_delta_status(
            self: discord.Client,
            *,
            activity: Any = None,
            status: discord.Status | None = None,
        ) -> Any:
            if (
                isinstance(activity, discord.Activity)
                and activity.type == discord.ActivityType.watching
                and activity.name == "Delta Air Lines Support"
            ):
                activity = discord.Activity(
                    type=discord.ActivityType.watching,
                    name=WATCHING_STATUS,
                )
            return await _original_change_presence(
                self,
                activity=activity,
                status=status,
            )

        discord.Client.change_presence = _change_presence_with_delta_status
        discord.Client._delta_presence_status_patch_installed = True
