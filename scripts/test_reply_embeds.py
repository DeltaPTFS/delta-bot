"""Regression checks for customer privacy and private ticket attribution."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))

import main  # noqa: E402
import config  # noqa: E402


class _Avatar:
    url = "https://example.com/support.png"


class _Agent:
    display_name = "Example Agent"
    display_avatar = _Avatar()

    def __str__(self) -> str:
        return "Example Agent (@private_support_username)"


class _Emoji:
    name = "XMark"

    def __str__(self) -> str:
        return "<:XMark:123456789012345678>"


class _Guild:
    emojis = [_Emoji()]


class _DMUser:
    def __init__(self) -> None:
        self.args = ()
        self.kwargs = {}

    async def send(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs


class _Client:
    def __init__(self, user: _DMUser) -> None:
        self.user = user

    def get_user(self, user_id: int) -> _DMUser:
        return self.user


staff = main.attributed_staff_reply_embed("Hello.", 123, _Agent())
customer = main.anonymous_support_reply_embed("Hello.")

staff_payload = str(staff.to_dict())
customer_payload = str(customer.to_dict())

assert "Example Agent" in staff_payload
assert "private_support_username" in staff_payload
assert "Customer Response" not in staff_payload
assert "123" in staff_payload
assert "Customer ID" in staff_payload
assert "Delta Support" in customer_payload
assert "Delta Support Reply" in customer_payload
assert "Example Agent" not in customer_payload
assert "Customer ID" not in customer_payload

dm_user = _DMUser()
assert asyncio.run(main.deliver_support_reply(_Client(dm_user), "123", customer))
assert dm_user.args == ()
assert dm_user.kwargs["embed"] is customer

assert main.delta_status_emoji(_Guild(), success=True) == main.CHECKMARK_EMOJI
assert main.delta_status_emoji(_Guild(), success=False) == str(_Emoji())
assert main.success_embed("Delivered").title.startswith(main.CHECKMARK_EMOJI)
main.XMARK_EMOJI = main.delta_status_emoji(_Guild(), success=False)
assert main.error_embed("Failed").title.startswith(str(_Emoji()))
assert main.BOT_VERSION == config.BOT_VERSION
assert main.format_uptime(90_061) == "1d 1h 1m 1s"
assert main.deployed_source() != "local/unknown"
topic = f"{main.DM_TICKET_OWNER_MARKER} 123"
topic = main.set_ticket_support_ids(topic, {456, 789})
assert main.get_ticket_support_ids(topic) == {456, 789}
topic = main.set_ticket_support_ids(topic, {789})
assert main.get_ticket_support_ids(topic) == {789}

bot = main.DeltaBot()
main.register_commands(bot.tree)
commands = {command.name: command for command in bot.tree.get_commands()}
assert set(commands) == {"panel", "version", "claim", "close", "reply", "format", "ticket"}
assert {command.name for command in commands["ticket"].commands} == {"control", "admin"}

control = next(command for command in commands["ticket"].commands if command.name == "control")
admin = next(command for command in commands["ticket"].commands if command.name == "admin")
control_options = next(param for param in control.parameters if param.name == "command")
admin_options = next(param for param in admin.parameters if param.name == "command")
assert "close" not in {choice.value for choice in control_options.choices}
assert "close" in {choice.value for choice in admin_options.choices}
assert main.WATCHING_ACTIVITY_TEXT == "staff forget to claim tickets"
assert main.OWNER_UPDATE_USER_ID == 1263248306264608871

print("Reply privacy, staff attribution, colors, and custom status emojis are valid.")
