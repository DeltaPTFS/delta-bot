"""Announce live website deployments in the designated Discord release channel."""
from __future__ import annotations

import asyncio
import logging
import re

import aiohttp
import discord
from config import GUILD_ID, UPDATE_CHANNEL_ID

log = logging.getLogger("delta-helpdesk.website-release")
RELEASE_URL = "https://roblox-delta-web.vercel.app/release-info"
WEBSITE_URL = "https://roblox-delta-web.vercel.app"
MARKER = "Website Deployment ID:"
POLL_SECONDS = 300


async def monitor_website_releases(bot):
    """Poll only the live production URL; never announce preview deployments."""
    last_seen = None
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
        while not bot.is_closed():
            try:
                await bot.wait_until_ready()
                async with session.get(RELEASE_URL, allow_redirects=False, headers={"Cache-Control": "no-cache"}) as response:
                    if response.status != 200:
                        raise ValueError("Production release metadata unavailable")
                    data = await response.json()
                if not isinstance(data, dict):
                    raise ValueError("Invalid deployment metadata")
                sha = data.get("commit", "")
                if data.get("environment") != "production" or not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
                    raise ValueError("Invalid production deployment metadata")
                if sha != last_seen:
                    channel = bot.get_channel(UPDATE_CHANNEL_ID)
                    if channel is None:
                        channel = await bot.fetch_channel(UPDATE_CHANNEL_ID)
                    if not isinstance(channel, discord.TextChannel) or channel.guild.id != GUILD_ID or bot.user is None:
                        raise ValueError("Authorized update channel unavailable")
                    marker = f"{MARKER} `{sha}`"
                    # Fail closed if history cannot be checked; retries are safe.
                    already_posted = False
                    async for message in channel.history(limit=500):
                        if message.author.id == bot.user.id and marker in message.content:
                            already_posted = True
                            break
                    if not already_posted:
                        summary = discord.utils.escape_markdown(str(data.get("summary") or "Website update")[:280])
                        notice = (
                            "## <:DeltaLogo:1540927958116601980> Delta Website — Update\n\n"
                            f"> **{summary}**\n\n"
                            "**Status:** Production deployment online\n"
                            f"**Website:** {WEBSITE_URL}\n"
                            f"-# {marker}\n"
                            "<:WingPinLogo:1540927847709802607> **Keep Climbing, Delta Air Lines.**"
                        )
                        sent = await channel.send(notice, allowed_mentions=discord.AllowedMentions.none(), suppress_embeds=True)
                        if sent is None:
                            raise ValueError("Website release notice was suppressed")
                    last_seen = sha
            except (aiohttp.ClientError, asyncio.TimeoutError, discord.HTTPException, ValueError, OSError) as exc:
                log.warning("Website release check deferred: %s", exc)
            await asyncio.sleep(POLL_SECONDS)
