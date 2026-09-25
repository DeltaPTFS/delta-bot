"""Regression checks for customer privacy and private ticket attribution."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bot"))

import main  # noqa: E402


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


customer = main.anonymous_support_reply_embed("Hello.", 123)
staff = main.attributed_staff_reply_embed("Hello.", 123, _Agent())

customer_payload = str(customer.to_dict())
staff_payload = str(staff.to_dict())

assert "Delta Air Lines Support" in customer_payload
assert "Delta Support Reply" in customer_payload
assert "Example Agent" not in customer_payload
assert "private_support_username" not in customer_payload
assert "Customer Response" not in customer_payload

assert "Example Agent" in staff_payload
assert "private_support_username" in staff_payload
assert "Customer Response" not in staff_payload
assert staff.color == customer.color

assert main.delta_status_emoji(_Guild(), success=True) == main.CHECKMARK_EMOJI
assert main.delta_status_emoji(_Guild(), success=False) == str(_Emoji())

print("Reply privacy, staff attribution, colors, and custom status emojis are valid.")
