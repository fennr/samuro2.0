import enum
import json
import re
import itertools as it

import hikari

from models import errors
from models.context import SamuroSlashContext

from etc import constants as const

# Config


class EventWinner(str, enum.Enum):
    BLUE = "blue"
    RED = "red"
    UNKNOWN = None


flatten_mmr = {
    'Bronze.5': 0, 'Bronze.4': 2250, 'Bronze.3': 2300, 'Bronze.2': 2350, 'Bronze.1': 2400,
    'Silver.5': 2450, 'Silver.4': 2470, 'Silver.3': 2490, 'Silver.2': 2510, 'Silver.1': 2530,
    'Gold.5': 2550, 'Gold.4': 2575, 'Gold.3': 2600, 'Gold.2': 2625, 'Gold.1': 2650,
    'Platinum.5': 2675, 'Platinum.4': 2695, 'Platinum.3': 2715, 'Platinum.2': 2735, 'Platinum.1': 2755,
    'Diamond.5': 2775, 'Diamond.4': 2800, 'Diamond.3': 2825, 'Diamond.2': 2850, 'Diamond.1': 2875,
    'Master.0': 2900, 'Grandmaster.0': 3100,
}


event_types = ["5x5", "5x5 manual", "unranked", "tournament"]


maps = ["Alterac Pass", "Battlefield Of Eternity", "Blackheart's Bay", "Braxis Holdout", "Cursed Hollow",
        "Dragon Shire", "Garden of Terror", "Hanamura", "Haunted Mines", "Infernal Shrines", "Sky Temple",
        "Tomb of the Spider Queen", "Towers of Doom", "Volskaya Foundry", "Warhead Junction"]

maps_url = "https://nexuscompendium.com/images/battlegrounds/"  # + main.jpg


def players_parse(players):
    players_list = players.split(' ')
    return [int(''.join(filter(str.isdigit, x))) for x in players_list]


def get_emoji_winner(winner: str):
    if winner == EventWinner.BLUE:
        return const.EMOJI_BLUE
    elif winner == EventWinner.RED:
        return const.EMOJI_RED
    else:
        return const.EMOJI_QUESTION

def min_diff_sets(data):
    """
        Parameters:
        - `data`: input list.
        Return:
        - min diff between sum of numbers in two sets
    """
    #print(data)
    if len(data) == 1:
        return data[0]
    s = sum(data)
    # `a` is list of all possible combinations of all possible lengths (from 1
    # to len(data) )
    a = []
    for i in range(1, len(data)):
        a.extend(list(it.combinations(data, i)))
    # `b` is list of all possible pairs (combinations) of all elements from `a`
    b = it.combinations(a, 2)
    # `c` is going to be final correct list of combinations.
    # Let apply 2 filters:
    # 1. leave only pairs where: sum of all elements == sum(data)
    # 2. leave only pairs where: flat list from pairs == data
    c = filter(lambda x: sum(x[0]) + sum(x[1]) == s, b)
    c = filter(lambda x: sorted([i for sub in x for i in sub]) == sorted(data), c)
    # `res` = [min_diff_between_sum_of_numbers_in_two_sets,
    #           ((set_1), (set_2))
    #         ]
    #print(c)
    res = sorted([(abs(sum(i[0]) - sum(i[1])), i) for i in c],
                 key=lambda x: x[0])
    # print(res)
    # return min([i[0] for i in res])
    min_mmr = min([i[0] for i in res])
    for i in res:
        if i[0] == min_mmr:
            red_team = i[1][0]
            blue_team = i[1][1]
            return red_team, blue_team


def get_all_heroes():
    heroes = const.ru_heroesdata
    return_list = []
    for hero, data in heroes.items():
        return_list.append(data['name_en'])
        return_list.append(data['name_ru'])
        for nick in data['nick']:
            return_list.append(nick)

    return return_list


all_heroes = get_all_heroes()


def per_lvl(raw_text):
    """
    Заменяет ~~ на проценты в тексте

    :param raw_text: Строка с ~~*~~
    :return: Строка с % за уровень
    """
    match = re.search('~~.{3,5}~~', raw_text)
    if match:
        clean_r = re.compile('~~.{3,5}~~')
        left, dig, right = raw_text.split('~~', maxsplit=2)
        dig = float(dig) * 100
        clean_text = re.sub(clean_r, '(+{}% за лвл)'.format(dig), raw_text)
        return clean_text
    else:
        return raw_text


def cleanhtml(raw_html):
    """
    Удаляет html теги из текста

    :param raw_html: Строка
    :return: Строка без </.*?>
    """
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return per_lvl(cleantext)