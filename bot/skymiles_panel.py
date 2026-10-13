"""Delta SkyMiles enrollment announcement for the HelpDesk bot.

The command posts the user's approved copy, an optional image above and below,
and an accessible link button to the official SkyMiles website.
"""
from __future__ import annotations

import discord

SKYMILES_SITE = "https://roblox-delta-web.vercel.app"
SKYMILES_SIGNUP_MESSAGE = """## <:DeltaLogo:1540927958116601980> Delta Air Lines | SkyMiles Sign-Up <:SkyTeamLogo:1540927923618316359>

-# <:Blank:1540951736062312529> <:DownwardShift:1539450554684801044> 1021 N Outer Loop Rd, East Point, GA, 30344.

> <:BArrow:1540951845147639809> **Ready to join Delta SkyMiles?**

Getting started only takes a few steps.

<:Identification:1544505969575198821> **Verify Your Accounts**
When you enter the SkyMiles website, you’ll be asked to verify both your **Discord** and **Roblox** accounts.

<:ExternalLink:1540927590418612366> **Automatic Sign-In**
Once both accounts are verified, you’ll be **automatically signed in** to your SkyMiles account.

<:Checklist:1544506010406752296> **New to SkyMiles?**
If this is your first time joining, you’ll be shown a quick **tutorial** covering your SkyMiles account, bookings, balance, and other features.

> **[Join Delta SkyMiles](https://roblox-delta-web.vercel.app)**

<:WingPinLogo:1540927847709802607> **Keep Climbing, Delta Air Lines.**"""


def signup_view() -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(
        style=discord.ButtonStyle.link,
        label="Join Delta SkyMiles",
        emoji=discord.PartialEmoji(name="ExternalLink", id=1540927590418612366),
        url=SKYMILES_SITE,
    ))
    return view


def validate_banner(attachment: discord.Attachment | None) -> bool:
    if attachment is None:
        return True
    return (
        (attachment.content_type or "").startswith("image/")
        or attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif"))
    )


async def publish_skymiles(
    channel: discord.TextChannel,
    *,
    top_banner: discord.Attachment | None = None,
    bottom_banner: discord.Attachment | None = None,
) -> None:
    # Banners are optional; reject non-images and never accept arbitrary URLs.
    if not validate_banner(top_banner) or not validate_banner(bottom_banner):
        raise ValueError("Both optional banners must be image attachments.")
    if top_banner is not None:
        await channel.send(file=await top_banner.to_file())
    if bottom_banner is None:
        await channel.send(SKYMILES_SIGNUP_MESSAGE, view=signup_view(),
                           allowed_mentions=discord.AllowedMentions.none())
    else:
        await channel.send(SKYMILES_SIGNUP_MESSAGE,
                           allowed_mentions=discord.AllowedMentions.none())
        await channel.send(file=await bottom_banner.to_file(), view=signup_view())
