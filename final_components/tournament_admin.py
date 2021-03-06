import json
import sys
import random
import socket
import importlib
import math
import admin
from helpers import *
import remote_player_wrapper


'''
TOURNAMENT ADMINISTRATOR
expects configuration of tournament type, number of players

tournament types:
--league
--cup

number of players: int

----------------------------------------------------------
This component is a server that accepts connections from
remote players and fills up a tournament with default
players.

It then schedules games based on tournament type
and updates rankings based on each game's results

It finally prints out final rankings
'''


'''
DATA STRUCTURES
'''
curr_default_player_num = 0
# create data structures for player data
players = {}  # dictionary mapping player name to player objects
rankings = {}  # mapping player names to scores
beaten = {}  # mapping player names to names of players beaten
player_list = []  # list of active players


'''
GET_CONFIG
Returns python dictionary of config data
'''
def get_config():
    with open('go.config') as config_file:
        config_data = json.load(config_file)
    return config_data


'''
ADD_PLAYER_TO_TOURNAMENT
expects player, player name, Bool
'''
def add_player_to_tournament(player, name, replacement):
    # adds a player to the tournament data structures
    players[name] = player
    rankings[name] = 0
    beaten[name] = []
    if not replacement:
        player_list.append(name)


'''
SETUP_FROM_CONFIG
returns a socket and default player class
'''
def setup_from_config():
    config_data = get_config()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((config_data["IP"], config_data["port"]))

    module = importlib.import_module(config_data["default-player"])
    DefaultPlayer = getattr(module, 'DefaultPlayerWrapper')
    return sock, DefaultPlayer


'''
CONNECT_REMOTE_PLAYER
expects a number, socket, default player class
'''
def connect_remote_players(num_players, sock, DefaultPlayer):
    # accept connections for all expected remote players, registers each for tournament
    for i in range(num_players):
        sock.listen(10)
        accept_socket, address = sock.accept()
        new_player = remote_player_wrapper.RemotePlayerWrapper(accept_socket)
        try:
            new_player_name = new_player.register()
            print("registering new player:", new_player_name)
            if new_player_name == GONE_CRAZY:
                print("remote player gone crazy, replacing it")
                new_player, new_player_name = create_default_player(DefaultPlayer, cheater=False)
        except socket.error:
            print("remote player socket error, replacing it")
            new_player, new_player_name = create_default_player(DefaultPlayer, cheater=False)
        add_player_to_tournament(new_player, new_player_name, replacement=False)


'''
ADD_DEFAULT_PLAYERS
expects a number, default player class
'''
def add_default_players(num_players, DefaultPlayer):
    # add extra default players if needed
    while num_players == 0 or math.log2(num_players) % 1 != 0 or num_players == 1:
        new_player, new_name = create_default_player(DefaultPlayer, cheater=False)
        print("registering new default player")
        add_player_to_tournament(new_player, new_name, replacement=False)
        num_players += 1


'''
FLIP_COIN
expects player name, player name
returns player name
'''
def flip_coin(player1, player2):
    arr = [player1, player2]
    return [arr[random.randint(0, 1)]]


'''
GET_LOSER
expects player name, player name, player name
returns player name
'''
def get_loser(player1, player2, winner):
    if winner == player1:
        return player2
    elif winner == player2:
        return player1
    else:
        raise InvalidPlayer("Player not in game")


'''
CREATE_DEFAULT_PLAYER
expects default player class, bool
returns instance of default player, name
'''
def create_default_player(DefaultPlayer, cheater):
    global curr_default_player_num
    if cheater:
        name = "replacement-default-player-" + str(curr_default_player_num)
    else:
        name = "default-player-" + str(curr_default_player_num)
    default_player = DefaultPlayer(name)
    curr_default_player_num += 1
    default_player.register()
    return default_player, name


'''
PLAY_GAME
expects player, player, player name, player name
returns [player name], player name, bool
'''
def play_game(player, opponent, p_name, o_name):
    # give players to admin to play a game
    winner, illegal = admin.administrate(player, opponent, p_name, o_name)
    if len(winner) == 2:
        winner = flip_coin(p_name, o_name)
    loser = get_loser(p_name, o_name, winner[0])
    return winner, loser, illegal

'''
PLAY_LEAGUE
expects default player class
'''
def play_league(DefaultPlayer):
    print("starting a league tournament...")
    for i in range(len(player_list)):
        for opponent in player_list[i + 1:]:
            print(player_list)
            winner, loser, illegal = play_game(players[player_list[i]], players[opponent], player_list[i], opponent)
            update_league(winner, loser, illegal, DefaultPlayer)


'''
PLAY_CUP
'''
def play_cup():
    print("starting a cup tournament...")
    while len(player_list) > 1:
        player1 = player_list[0]
        player2 = player_list[1]
        winner, loser, illegal = play_game(players[player1], players[player2], player1, player2)
        update_cup(winner, loser, illegal)
        player_list.remove(loser)

'''
UPDATE_LEAGUE
expects player name, player name, bool, default player class
'''
def update_league(winner, loser, illegal, DefaultPlayer):
    # update data structures based on results
    if illegal:
        rankings[loser] = 0
        default_player, name = create_default_player(DefaultPlayer, cheater=True)
        # replace internal player name in player list
        player_list[player_list.index(loser)] = name
        # put the replacement player in all other data structures
        add_player_to_tournament(default_player, name, replacement=True)
        # distribute points of loser
        for player_name in beaten[loser]:
            rankings[player_name] += 1
        beaten[loser] = []
    else:
        # only add non cheaters so we don't give back points to any cheaters
        beaten[winner[0]].append(loser)
    rankings[winner[0]] += 1


'''
UPDATE_CUP
expects player name, player name, bool
'''
def update_cup(winner, loser, illegal):
    # update data structures based on results
    if illegal:
        rankings[loser] = 0
    rankings[winner[0]] += 1


'''
SCORES_TO_RANKINGS
returns dict
'''
def scores_to_rankings():
    sorted_by_value = sorted(rankings, key=lambda x: rankings[x], reverse=True)
    rank = 1
    last_value = rankings[sorted_by_value[0]]
    ranked_dict = dict()
    for name in sorted_by_value:
        this_value = rankings[name]
        if this_value != last_value:
            rank += 1
        if rank in ranked_dict:
            ranked_dict[rank].append(name)
        else:
            ranked_dict[rank] = [name]
        last_value = this_value
    return ranked_dict


def main(tourney_arg, num_arg):
    # get args from command line
    if tourney_arg == LEAGUE:
        tournament_type = LEAGUE
    elif tourney_arg == CUP:
        tournament_type = CUP
    else:
        raise InvalidTournamentType("Invalid tournament type.")

    num_players = int(num_arg)

    # make socket
    sock, DefaultPlayer = setup_from_config()

    # connect remote players
    connect_remote_players(num_players, sock, DefaultPlayer)

    # add extra default players if needed
    add_default_players(num_players, DefaultPlayer)

    # play pair players as determined by tournament type
    if tournament_type == LEAGUE:
        play_league(DefaultPlayer)

    elif tournament_type == CUP:
        play_cup()

    # stout the rankings dictionary
    print("closing socket")
    sock.close()
    rank_dict = scores_to_rankings()
    print("----------------")
    print("Final Rankings:")
    for key, val in rank_dict.items():
        print(key, ": ", val)
    print("\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
