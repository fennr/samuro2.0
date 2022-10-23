import json

ERROR_COLOR: int = 0xFF0000
WARN_COLOR: int = 0xFFCC4D
EMBED_BLUE: int = 0x009DFF
EMBED_GREEN: int = 0x77B255
EMBED_YELLOW: int = 0xFFD966
UNKNOWN_COLOR: int = 0xBE1931
MISC_COLOR: int = 0xC2C2C2

EMOJI_CHANNEL = "<:channel:585783907841212418>"
EMOJI_MENTION = "<:mention:658538492019867683>"
EMOJI_SLOWMODE = "<:slowmode:951913313577603133>"
EMOJI_MOD_SHIELD = "<:mod_shield:923752735768190976>"
# Badges
EMOJI_BUGHUNTER = "<:bughunter:927590809241530430>"
EMOJI_BUGHUNTER_GOLD = "<:bughunter_gold:927590820448710666>"
EMOJI_CERT_MOD = "<:cert_mod:927582595808657449>"
EMOJI_EARLY_SUPPORTER = "<:early_supporter:927582684123914301>"
EMOJI_HYPESQUAD_BALANCE = "<:hypesquad_balance:927582757587136582>"
EMOJI_HYPESQUAD_BRAVERY = "<:hypesquad_bravery:927582770329444434>"
EMOJI_HYPESQUAD_BRILLIANCE = "<:hypesquad_brilliance:927582740977684491>"
EMOJI_HYPESQUAD_EVENTS = "<:hypesquad_events:927582724523450368>"
EMOJI_PARTNER = "<:partner:927591117304778772>"
EMOJI_STAFF = "<:staff:927591104902201385>"
EMOJI_VERIFIED_DEVELOPER = "<:verified_developer:927582706974462002>"
EMOJI_FIRST = "<:first:956672908145602610>"
EMOJI_PREV = "<:prev:956672875111260160>"
EMOJI_NEXT = "<:next:956672907185123359>"
EMOJI_LAST = "<:last:956672908082708480>"

EMOJI_GREEN_UP = "<:s_sign_green_up:1014602357075624016>"
EMOJI_RED_DOWN = "<:s_sign_red_down:1014602358908530728>"

EMOJI_BLUE = "🔵"
EMOJI_RED = "🔴"
EMOJI_QUESTION = "❔"

patch = "2.55.3.88481"
spatch = patch[-5:]

hots_season = "2022.02"

hots_jsons = {
    "ru_heroesdata": "etc/hots/heroesdata_ru.json",
    "heroesdata": f"etc/hots/heroesdata_{spatch}.json",
    "gamestrings": f"etc/hots/gamestrings_{spatch}_ruru.json",
    "master_opinion": "etc/hots/pancho.json",
    "stlk_builds": "etc/hots/stlk.json"
}

try:
    with open(hots_jsons["ru_heroesdata"], encoding='utf-8') as file:
        ru_heroesdata = json.load(file)
    with open(hots_jsons["heroesdata"], encoding='utf-8') as file:
        heroesdata = json.load(file)
    with open(hots_jsons["gamestrings"], encoding='utf-8') as file:
        gamestrings = json.load(file)
    with open(hots_jsons["master_opinion"], encoding='utf-8') as file:
        master_opinion = json.load(file)
    with open(hots_jsons["stlk_builds"], encoding='utf-8') as file:
        stlk_builds = json.load(file)
except:
    print("Невозможно загрузить данные о героях")


all_heroes = [
    "Abathur",
    "Абатур",
    "Alarak",
    "Аларак",
    "Alexstrasza",
    "Алекстраза",
    "Ana",
    "Ана",
    "Anduin",
    "Андуин",
    "Anub'arak",
    "АнубАрак",
    "Ануб",
    "Artanis",
    "Артанис",
    "Arthas",
    "Артас",
    "Auriel",
    "Ауриэль",
    "Azmodan",
    "Азмодан",
    "Blaze",
    "Блэйз",
    "Пожарник",
    "Brightwing",
    "Светик",
    "Бв",
    "Cassia",
    "Кассия",
    "Амазонка",
    "Chen",
    "Чень",
    "Cho",
    "ЧоГалл",
    "Чо",
    "Chromie",
    "Хроми",
    "Deathwing",
    "Смертокрыл",
    "Deckard",
    "Декард Каин",
    "Декард",
    "Dehaka",
    "Дехака",
    "Diablo",
    "Диабло",
    "D.Va",
    "Дива",
    "Дива",
    "E.T.C.",
    "ETC",
    "Етц",
    "Falstad",
    "Фалстад",
    "Fenix",
    "Феникс",
    "Gall",
    "Галл",
    "Garrosh",
    "Гаррош",
    "Gazlowe",
    "Газлоу",
    "Газик",
    "Genji",
    "Гэндзи",
    "Greymane",
    "Седогрив",
    "Gul'dan",
    "Гулдан",
    "Hanzo",
    "Хандзо",
    "Hogger",
    "Дробитель",
    "Хогер",
    "Illidan",
    "Иллидан",
    "Imperius",
    "Империй",
    "Jaina",
    "Джайна",
    "Johanna",
    "Джоанна",
    "Junkrat",
    "Крысавчик",
    "Kael'thas",
    "КельТас",
    "Кель",
    "Инвокер",
    "Kel'Thuzad",
    "КелТузад",
    "Ктз",
    "Келтузед",
    "Ktz",
    "Kerrigan",
    "Керриган",
    "Kharazim",
    "Каразим",
    "Монк",
    "Leoric",
    "Леорик",
    "Li Li",
    "Лили",
    "Li-Ming",
    "Ли-Минг",
    "The Lost Vikings",
    "Потерявшиеся викинги",
    "Викинги",
    "Олаф",
    "Эрик",
    "Балеог",
    "Tlv",
    "Vikings",
    "Lt. Morales",
    "лейтенант Моралес",
    "Моралес",
    "Медик",
    "Morales",
    "Lucio",
    "Лусио",
    "Lunara",
    "Лунара",
    "Maiev",
    "Майев",
    "Malfurion",
    "Малфурион",
    "Mal'Ganis",
    "Малганис",
    "Malthael",
    "Малтаэль",
    "Medivh",
    "Медив",
    "Mei",
    "Мэй",
    "Mephisto",
    "Мефисто",
    "Muradin",
    "Мурадин",
    "Murky",
    "Мурчаль",
    "Nazeebo",
    "Назибо",
    "Nazibo",
    "Nova",
    "Нова",
    "Orphea",
    "Орфея",
    "Probius",
    "Пробиус",
    "Пробка",
    "Qhira",
    "Кахира",
    "Ragnaros",
    "Рагнарос",
    "Raynor",
    "Рейнор",
    "Rehgar",
    "Регар",
    "Rexxar",
    "Рексар",
    "Samuro",
    "Самуро",
    "Sgt. Hammer",
    "сержант Кувалда",
    "Хаммер",
    "Танк",
    "Сержант",
    "Кувалда",
    "Sonya",
    "Соня",
    "Stitches",
    "Стежок",
    "Стич",
    "Пудж",
    "Stukov",
    "Стуков",
    "Sylvanas",
    "Сильвана",
    "Tassadar",
    "Тассадар",
    "The Butcher",
    "Мясник",
    "Мясо",
    "Thrall",
    "Тралл",
    "Tracer",
    "Трейсер",
    "Tychus",
    "Тайкус",
    "Tyrael",
    "Тираэль",
    "Tyrande",
    "Тиранда",
    "Uther",
    "Утер",
    "Valeera",
    "Валира",
    "Valla",
    "Валла",
    "Varian",
    "Вариан",
    "Whitemane",
    "Вайтмейн",
    "Xul",
    "Зул",
    "Yrel",
    "Ирель",
    "Zagara",
    "Загара",
    "Zarya",
    "Заря",
    "Zeratul",
    "Зератул",
    "Zul'jin",
    "Зулджин",
]

# by fenrir#5455
