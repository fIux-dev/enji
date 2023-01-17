from typing import Optional

from game import Suit


def suit_to_emoji(suit: Suit) -> str:
    if suit == Suit.CLUB:
        return "♣"
    elif suit == Suit.SPADE:
        return "♠"
    elif suit == Suit.HEART:
        return "♥"
    elif suit == Suit.DIAMOND:
        return "♦"


def emoji_to_suit(unicode_str: str) -> Optional[Suit]:
    if unicode_str == "♣":
        return Suit.CLUB
    elif unicode_str == "♠":
        return Suit.SPADE
    elif unicode_str == "♥":
        return Suit.HEART
    elif unicode_str == "♦":
        return Suit.DIAMOND

    return None
