"""Runtime presence override for Delta HelpDesk.

Loaded from config.py after the stable 2.6.0 ticket runtime controls.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("delta-helpdesk.presence")

WATCHING_STATUS = "staff forget to claim tickets"
OLD_WATCHING_STATUS = "Delta Air Lines Support"

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
            shard_id: int | None = None,
        ) -> Any:
            if (
                isinstance(activity, discord.Activity)
                and activity.type == discord.ActivityType.watching
                and activity.name == OLD_WATCHING_STATUS
            ):
                activity = discord.Activity(
                    type=discord.ActivityType.watching,
                    name=WATCHING_STATUS,
                )
            return await _original_change_presence(
                self,
                activity=activity,
                status=status,
                shard_id=shard_id,
            )

        discord.Client.change_presence = _change_presence_with_delta_status
        discord.Client._delta_presence_status_patch_installed = True
