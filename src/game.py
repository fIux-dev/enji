import random
from enum import Enum
from typing import Dict, Optional, Set, Union

from discord import Guild, Member, Message, User
from discord.ext import commands


class GameException(Exception):
    pass


class GameState(Enum):
    UNDEFINED = 0
    NOT_STARTED = 1
    DISCUSSION_STAGE = 2
    ANSWER_STAGE = 3
    GAME_OVER = 4


class Suit(Enum):
    CLUB = "club"
    SPADE = "spade"
    HEART = "heart"
    DIAMOND = "diamond"


class Player:
    discord_user: Union[Member, User]
    is_alive: bool
    suit: Suit
    guess: Optional[Suit]

    def __init__(self, discord_user: Union[Member, User]) -> None:
        self.discord_user = discord_user
        self.is_alive = True
        self.suit = random.choice(list(Suit))
        self.guess = None

    def get_new_suit(self) -> None:
        self.suit = random.choice(list(Suit))
        self.guess = None

    async def send_dm(self, content: str) -> Message:
        return await self.discord_user.send(content)

    def submit_guess(self, guess: Suit) -> None:
        self.guess = guess
        if guess != self.suit:
            self.is_alive = False


class Game:
    bot: commands.Bot
    guild: Guild
    host: Union[Member, User]

    round_minutes: int
    answer_minutes: int

    is_active: bool

    players: Dict[int, Player]
    round: int
    jack_id: Optional[int]
    state: GameState
    player_win: bool

    def __init__(
        self,
        bot: commands.Bot,
        guild: Guild,
        host: Union[Member, User],
        round_minutes: int,
        answer_minutes: int,
    ) -> None:
        self.bot = bot
        self.guild = guild
        self.host = host

        self.round_minutes = round_minutes
        self.answer_minutes = answer_minutes

        self.is_active = False

        self.players = {}
        self.round = 0
        self.jack_id = None
        self.state = GameState.NOT_STARTED
        self.player_win = False

        self.add_player(self.host)

    def get_alive_players(self) -> Set[Player]:
        return {player for player in self.players.values() if player.is_alive}

    def get_jack(self) -> Union[Member, User]:
        return self.players[self.jack_id]

    def get_is_jack_alive(self) -> bool:
        return self.players[self.jack_id].is_alive

    def add_player(self, discord_user: Union[Member, User]) -> None:
        self.players[discord_user.id] = Player(discord_user)

    def remove_player(self, discord_user: Union[Member, User]) -> None:
        del self.players[discord_user.id]

    async def intialize_game(self) -> None:
        self.jack_id = random.choice(list(self.players.keys()))
        self.players[self.jack_id].is_jack = True

    def assign_new_suits(self) -> None:
        for player_id in self.players.keys():
            if self.players[player_id].is_alive:
                self.players[player_id].get_new_suit()

    def submit_guess(self, discord_user: Union[Member, User], guess: Suit) -> None:
        self.players[discord_user.id].submit_guess(guess)

    def get_player(self, discord_user: Union[Member, User]) -> Optional[Player]:
        if discord_user.id not in self.players:
            return None
        return self.players[discord_user.id]

    def kill_player(self, discord_user: Union[Member, User]) -> None:
        self.players[discord_user.id].is_alive = False

    def kill_players_with_no_guesses(self) -> None:
        for player_id in self.players.keys():
            if not self.players[player_id].guess:
                self.players[player_id].is_alive = False
