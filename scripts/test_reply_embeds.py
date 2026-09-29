"""Regression checks for customer privacy and private ticket attribution."""

from __future__ import annotations

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


class _Author:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _Message:
    def __init__(self, content: str, author_id: int) -> None:
        self.content = content
        self.author = _Author(author_id)


class _Role:
    def __init__(self, role_id: int) -> None:
        self.id = role_id


class _Member:
    def __init__(self, *role_ids: int) -> None:
        self.roles = [_Role(role_id) for role_id in role_ids]


customer = main.anonymous_support_reply_embed("Hello.", 123)
staff = main.attributed_staff_reply_embed("Hello.", 123, _Agent())

customer_payload = str(customer.to_dict())
staff_payload = str(staff.to_dict())

assert "Delta Support" in customer_payload
assert "Delta Support Reply" in customer_payload
assert "Example Agent" not in customer_payload
assert "private_support_username" not in customer_payload
assert "Customer Response" not in customer_payload
assert "123" not in customer_payload
assert "Customer ID" not in customer_payload

assert "Example Agent" in staff_payload
assert "private_support_username" in staff_payload
assert "Customer Response" not in staff_payload
assert staff.color == customer.color

assert main.delta_status_emoji(_Guild(), success=True) == main.CHECKMARK_EMOJI
assert main.delta_status_emoji(_Guild(), success=False) == str(_Emoji())
assert main.success_embed("Delivered").title.startswith(main.CHECKMARK_EMOJI)
main.XMARK_EMOJI = main.delta_status_emoji(_Guild(), success=False)
assert main.error_embed("Failed").title.startswith(str(_Emoji()))
assert main.BOT_VERSION == config.BOT_VERSION
assert main.format_uptime(90_061) == "1d 1h 1m 1s"
assert main.deployed_source() != "local/unknown"
assert main.find_blocked_term("this is sh1t") == "shit"
assert main.find_blocked_term("f.u.c.k") == "fuck"
assert main.find_blocked_term("class assignment") is None
partnership_accepted = main.SUPPORT_FORMATS["partnership_accepted"]
assert "External Affairs Office" in partnership_accepted
assert "## Delta Air Lines | SkyTeam" in partnership_accepted
assert "over [5,000]" in partnership_accepted
assert "https://discord.gg/u8GJF2br2M" in partnership_accepted
assert "Ad not done yet" not in partnership_accepted
assert len(partnership_accepted) <= 4096
assert main.is_release_update_message(
    _Message("# Delta Support Bot — Update 2.9.0", 123), 123
)
assert not main.is_release_update_message(
    _Message("# Delta Support Bot — Update 2.9.0", 456), 123
)
assert not main.is_release_update_message(_Message("ordinary log message", 123), 123)
assert config.TICKET_CONFIG["careers"]["role_id"] == config.ADMIN_ROLE_ID
assert main.ticket_access_role_ids("careers") == {config.ADMIN_ROLE_ID}
assert main.ticket_access_role_ids("general_inquiries") == {
    config.STAFF_ROLE_ID,
    config.ADMIN_ROLE_ID,
}
assert main.can_use_ticket_control(_Member(config.STAFF_ROLE_ID))
assert main.can_use_ticket_control(_Member(config.ADMIN_ROLE_ID))
assert main.can_use_ticket_control(
    _Member(config.STAFF_ROLE_ID, config.ADMIN_ROLE_ID)
)

topic = f"{main.DM_TICKET_OWNER_MARKER} 123"
topic = main.set_ticket_support_ids(topic, {456, 789})
assert main.get_ticket_support_ids(topic) == {456, 789}
topic = main.set_ticket_support_ids(topic, {789})
assert main.get_ticket_support_ids(topic) == {789}

bot = main.DeltaBot()
main.register_commands(bot.tree)
commands = {command.name: command for command in bot.tree.get_commands()}
assert set(commands) == {"panel", "version", "reply", "format", "ticket"}
assert {command.name for command in commands["ticket"].commands} == {"control", "admin"}
ticket_control = next(command for command in commands["ticket"].commands if command.name == "control")
ticket_admin = next(command for command in commands["ticket"].commands if command.name == "admin")
control_actions = {choice.value for choice in ticket_control._params["command"].choices}
admin_actions = {choice.value for choice in ticket_admin._params["command"].choices}
assert control_actions <= admin_actions

print("Reply privacy, staff attribution, colors, and custom status emojis are valid.")
