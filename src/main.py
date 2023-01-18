import asyncio
import os
from typing import Dict, Optional, Union

import discord
from discord.ext import commands
from dotenv import load_dotenv

import constants
import utils
from game import Game, GameState, Player, Suit

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

games: Dict[int, Game] = {}


@bot.event
async def on_ready():
    print(f"{bot.user.name} has connected to Discord!")


@bot.command(name="new", aliases=["newgame", "ng"], help="Starts a new game.")
async def new_game(
    ctx,
    round_minutes: int = constants.DEFAULT_ROUND_MINUTES,
    answer_minutes: int = constants.DEFAULT_ANSWER_MINUTES,
):
    if not ctx.guild:
        await ctx.send("This command can only be used in a server!")
        return

    if ctx.guild.id in games:
        await ctx.send(
            "Another game is already happening in this server. Please wait for "
            "the existing game to finish before starting a new one, or use the "
            "`stopgame` command to quit the current game."
        )
        return

    game = Game(bot, ctx.guild, ctx.author, round_minutes, answer_minutes)
    games[ctx.guild.id] = game
    players = ", ".join(
        [str(player.discord_user) for player in games[ctx.guild.id].players.values()]
    )
    await ctx.send(
        f"**SOLITARY CONFINEMENT**\n{ctx.author} started a new game!\n"
        f"Discussion stage: {round_minutes}m\n"
        f"Answer stage: {answer_minutes}m\n"
        "Please use the `join` command to join the game.\n\n"
        f"Current players: {len(games[ctx.guild.id].players)} ({players})"
    )


@bot.command(
    name="stop",
    help="Stops the current game. Can only be run by person who started the game.",
)
async def stop_game(ctx):
    if not ctx.guild:
        await ctx.send("This command can only be used in a server!")
        return

    if ctx.guild.id not in games:
        await ctx.send("No active game is happening in this server.")
        return

    if ctx.author.id != games[ctx.guild.id].host.id:
        await ctx.send(
            f"Only the host of the existing game ({games[ctx.guild.id].host}) can stop the game."
        )
        return

    del games[ctx.guild.id]
    await ctx.send(f"{ctx.author} stopped the existing game.")


@bot.command(
    name="join",
    aliases=["j"],
    help="Join the current game. Can only be run if there is an active game.",
)
async def join_game(ctx):
    if not ctx.guild:
        await ctx.send("This command can only be used in a server!")
        return

    if ctx.guild.id not in games:
        await ctx.send("No active game is happening in this server.")
        return

    if games[ctx.guild.id].state != GameState.NOT_STARTED:
        await ctx.send("Players can only be added before the game has started.")
        return

    if ctx.author.id in games[ctx.guild.id].players:
        await ctx.send(f"Player {ctx.author} is already in this game.")
        return

    games[ctx.guild.id].add_player(ctx.author)
    players = ", ".join(
        [str(player.discord_user) for player in games[ctx.guild.id].players.values()]
    )
    await ctx.send(
        f"{ctx.author} joined the game.\n"
        f"Current players: {len(games[ctx.guild.id].players)} ({players})"
    )


@bot.command(
    name="leave",
    aliases=["l"],
    help="Leave the current game. Can only be run if there is an active game.",
)
async def leave_game(ctx):
    if not ctx.guild:
        await ctx.send("This command can only be used in a server!")
        return

    if ctx.guild.id not in games:
        await ctx.send("No active game is happening in this server.")
        return

    if ctx.author.id not in games[ctx.guild.id].players:
        await ctx.send(f"Player {ctx.author} is not in this game.")
        return

    if games[ctx.guild.id].state == GameState.NOT_STARTED:
        games[ctx.guild.id].remove_player(ctx.author)
        if len(games[ctx.guild.id].players) > 0:
            if ctx.author == games[ctx.guild.id].host:
                games[ctx.guild.id].select_new_host()
                await ctx.send(
                    f"The previous game host {ctx.author} left the game, the "
                    f"new host is: {games[ctx.guild.id].host}"
                )

            players = ", ".join(
                [str(player.discord_user) for player in games[ctx.guild.id].players.values()]
            )
            await ctx.send(
                f"{ctx.author} left the game.\n"
                f"Current players: {len(games[ctx.guild.id].players)} ({players})"
            )
        else:
            await ctx.send("All players have left the game, quitting the game.")
            del games[ctx.guild.id]
    elif games[ctx.guild.id].state in {GameState.ANSWER_STAGE, GameState.DISCUSSION_STAGE}:
        games[ctx.guild.id].kill_player(ctx.author)
        await ctx.send(f"**{ctx.author} died!")
    else:
        await ctx.send("**ERROR**: Unable to leave game at this time.")


@bot.command(
    name="start",
    aliases=["startgame", "sg"],
    help="Starts the current game. Can only be run if there is an active game.",
)
async def start_game(ctx):
    if not ctx.guild:
        await ctx.send("This command can only be used in a server!")
        return

    if ctx.guild.id not in games:
        await ctx.send("No active game is happening in this server.")
        return

    if ctx.author != games[ctx.guild.id].host:
        await ctx.send(
            f"Only the host of the existing game ({games[ctx.guild.id].host.id}) can start the game."
        )
        return

    if games[ctx.guild.id].state != GameState.NOT_STARTED:
        await ctx.send(
            f"The game is already started. To stop the existing game, the "
            f"host ({games[ctx.guild.id].host}) should use the `stopgame` command."
        )
        return

    if len(games[ctx.guild.id].players) < constants.MINIMUM_PLAYERS:
        raise Exception(
            f"Game cannot be started without at least {constants.MINIMUM_PLAYERS} players."
        )

    async def _wait_for_guess(player: Player):
        try:
            guess_message = await player.send_dm(
                f"**SOLITARY CONFINEMENT (server: {ctx.guild}, id: {ctx.guild.id})**\n"
                f"Round: {games[ctx.guild.id].round}\n"
                f"Time limit: {games[ctx.guild.id].answer_minutes}m\n"
                f"Please react to this message within the time limit with your guess for your suit!"
            )
            await asyncio.gather(
                *[guess_message.add_reaction(utils.suit_to_emoji(suit)) for suit in Suit]
            )

            def check(reaction: discord.Reaction, user: Union[discord.Member, discord.User]):
                return (
                    user.id == player.discord_user.id
                    and reaction.message.id == guess_message.id
                    and str(reaction.emoji) in {utils.suit_to_emoji(suit) for suit in Suit}
                )

            reaction, _ = await bot.wait_for(
                "reaction_add",
                check=check,
                timeout=games[ctx.guild.id].answer_minutes * constants.SECONDS_IN_MINUTE,
            )
        except asyncio.TimeoutError:
            games[ctx.guild.id].kill_player(player.discord_user)
            await player.send_dm(
                f"**GAME OVER**\n{player.discord_user} failed to guess in time and died."
            )
            return
        else:
            guess = utils.emoji_to_suit(str(reaction.emoji))
            if guess is None:
                # This shouldn't happen based on the check condition
                await player.send_dm("**ERROR:** Invalid guess.")
            games[ctx.guild.id].submit_guess(player.discord_user, guess)
            # Reload the player after submitting guess
            player = games[ctx.guild.id].get_player(player.discord_user)
            if not player.is_alive:
                await player.send_dm(
                    f"**GAME OVER**\n{player.discord_user} guessed "
                    f"{utils.suit_to_emoji(guess)} but your suit was "
                    f"{utils.suit_to_emoji(player.suit)}. You died!"
                )
                await ctx.send(f"**{player.discord_user} died!")
            else:
                await player.send_dm(
                    f"**CORRECT!**\n{player.discord_user} survived round "
                    f"{games[ctx.guild.id].round}!"
                )

    async def _run_game_loop():
        while (
            ctx.guild.id in games
            and games[ctx.guild.id].get_is_jack_alive()
            and len(games[ctx.guild.id].get_alive_players()) > 2
        ):
            games[ctx.guild.id].round += 1
            games[ctx.guild.id].assign_new_suits()
            alive_players = games[ctx.guild.id].get_alive_players()
            alive_players_list = ", ".join([str(player.discord_user) for player in alive_players])
            games[ctx.guild.id].state = GameState.DISCUSSION_STAGE
            await ctx.send(
                f"**ROUND {games[ctx.guild.id].round}**\n"
                f"Alive: {len(alive_players)} ({alive_players_list})\n"
                "You are now in the **DISCUSSION STAGE** for "
                f"{games[ctx.guild.id].round_minutes}m. Please discuss "
                "with your fellow players to find the **JACK OF HEARTS**."
            )
            await asyncio.sleep(games[ctx.guild.id].round_minutes * constants.SECONDS_IN_MINUTE)
            games[ctx.guild.id].state = GameState.ANSWER_STAGE
            await ctx.send(
                f"**SOLITARY CONFINEMENT**\nYou are now in the "
                f"**ANSWER STAGE**. Please check your DMs. You have {games[ctx.guild.id].answer_minutes}m "
                f"to react to my message with your guess!"
            )
            for player in alive_players:
                bot.loop.create_task(_wait_for_guess(player))
            await asyncio.sleep(games[ctx.guild.id].answer_minutes * constants.SECONDS_IN_MINUTE)

        if ctx.guild.id not in games:
            # Game was probably stopped
            return

        games[ctx.guild.id].state = GameState.GAME_OVER

        alive_players = games[ctx.guild.id].get_alive_players()
        alive_players_list = ", ".join([str(player.discord_user) for player in alive_players])
        if not games[ctx.guild.id].get_is_jack_alive() and len(alive_players) >= 2:
            games[ctx.guild.id].player_win = True
            await ctx.send(
                "**GAME OVER**\nThe Jack of Hearts "
                f"({games[ctx.guild.id].get_jack().discord_user}) is dead. "
                f"Players win!\nAlive: {len(alive_players)} ({alive_players_list})"
            )
        elif len(alive_players) == 0:
            games[ctx.guild.id].player_win = False
            await ctx.send(
                "**GAME OVER**\nEveryone is dead :(\n"
                f"The JACK OF HEARTS was: {games[ctx.guild.id].get_jack().discord_user}\n"
                "Alive: 0"
            )
        elif games[ctx.guild.id].get_is_jack_alive() and len(alive_players) <= 2:
            games[ctx.guild.id].player_win = False
            await ctx.send(
                "**GAME OVER**\nThe Jack of Hearts "
                f"({games[ctx.guild.id].get_jack().discord_user}) wins!\n"
                f"Alive: {len(alive_players)} ({alive_players_list})"
            )
        else:
            games[ctx.guild.id].player_win = False
            await ctx.send(
                "**GAME OVER**\nUnexpected game over condition.\n"
                f"Alive: {len(alive_players)} ({alive_players_list})"
            )

        del games[ctx.guild.id]

    await games[ctx.guild.id].intialize_game()
    await asyncio.gather(
        *[
            player.send_dm(
                f"**SOLITARY CONFINEMENT (server: {ctx.guild}, id: {ctx.guild.id})**\n"
                "Game start!"
            )
            for player in games[ctx.guild.id].players.values()
        ]
    )
    await games[ctx.guild.id].get_jack().send_dm(
        f"**SOLITARY CONFINEMENT (server: {ctx.guild}, id: {ctx.guild.id})**\n"
        "You are the Jack of Hearts!"
    )
    await ctx.send(
        f"**GAME START**\n{ctx.author} started the game in server {ctx.guild} "
        f"(id: {ctx.guild.id})!\nDM me with `!show {ctx.guild.id}` "
        "to get a list of other players' suits excluding your own."
    )
    bot.loop.create_task(_run_game_loop())


@bot.command(
    name="show",
    help="Shows the active suits for other players in a game. DM only.",
)
async def show_suits(ctx, guild_id: Optional[int] = None):
    if isinstance(ctx.channel, discord.channel.DMChannel):
        if guild_id is None:
            await ctx.send("Usage: `show <guild_id>`")
            return

        guild = bot.get_guild(guild_id)
        member = guild.get_member(ctx.author.id)
        if not member:
            await ctx.send(f"{ctx.author} is not a member of server {guild}.")
            return

        if guild_id not in games:
            await ctx.send("No game is happening in this server.")
            return

        if member.id not in games[guild_id].players:
            await ctx.send(f"{ctx.author} is not part of the current game in server {guild}.")
            return

        if games[guild_id].state != GameState.DISCUSSION_STAGE:
            await ctx.send(
                "You can only view other players' suits during the "
                "**DISCUSSION STAGE** of the game."
            )
            return

        try:
            suits = "\n".join(
                [
                    f"{player.discord_user}: {utils.suit_to_emoji(player.suit)} ({player.suit.value})"
                    for player in games[guild_id].get_alive_players()
                    if player.discord_user.id != ctx.author.id
                ]
            )
            guild = bot.get_guild(guild_id)
            await ctx.send(
                f"**SOLITARY CONFINEMENT (server: {guild}, id: {guild_id})**\n"
                f"Round: {games[guild_id].round}\n"
                f"```\n{suits}\n```"
            )
        except Exception as e:
            await ctx.send("**ERROR:** Unspecified error occurred, please check bot logs.")
            raise e

    else:
        await ctx.send(
            "This command can only be used in DM! Please DM me with "
            f"`!show {ctx.guild.id}` to get a list of other players' suits "
            "excluding your own."
        )


bot.run(TOKEN)
