import attr
import enum
import logging
from datetime import datetime
import typing as t
import itertools as it
from bs4 import BeautifulSoup
import requests

import hikari
from difflib import get_close_matches

import lightbulb.utils

from models import errors
from models.db import DatabaseModel
from models.context import SamuroSlashContext

from utils import hots as util

from utils.hots import EventWinner

from etc import constants as const

# TODO при переносе на сервер не забыть начать ивенты с 411
# SELECT setval('event_history_event_id_seq', 411, true)

logger = logging.getLogger(__name__)

bug_names = {"Deckard Cain": "Deckard", "Lúcio": "Lucio"}

all_heroes = const.all_heroes

leagues = {
    "Bronze": "Бронза",
    "Silver": "Серебро",
    "Gold": "Золото",
    "Platinum": "Платина",
    "Diamond": "Алмаз",
    "Master": "Мастер",
    "Grandmaster": "Грандмастер",
}

f_time = "%Y-%m-%d %H:%M:%S"


class HeroLeagues(str, enum.Enum):
    BRONZE = "Бронза"
    SILVER = "Серебро"
    GOLD = "Золото"
    PLATINUM = "Платина"
    DIAMOND = "Алмаз"
    MASTER = "Мастер"
    GRANDMASTER = "Грандмастер"


class EventTypes(str, enum.Enum):
    event5x5 = "5x5"
    event1x4 = "1x4"
    unranked = "unranked"
    manual5x5 = "5x5 manual"


class DatabaseUserFlag(enum.Flag):
    """Flags stored for a user in the database."""

    NONE = 0
    """An empty set of database user flags."""
    TIMEOUT_ON_JOIN = 1 << 0
    """The user should be timed out when next spotted joining the guild."""


def check_type(type, members):
    if type in [EventTypes.event5x5, EventTypes.unranked, EventTypes.manual5x5]:
        if len(members) != 10:
            raise errors.BadPlayersCount
    elif type == '1x4':
        if len(members) != 5:
            raise errors.BadPlayersCount
    else:
        if len(members) != 2:
            raise errors.BadPlayersCount


def sort_by_mmr(player):
    return player.mmr


async def matchmaking_5x5(ctx: SamuroSlashContext, type: str, players_str: str, manual:bool = False):
    players_id = util.players_parse(players_str)
    players = []
    unique_mmr = []
    members = []
    for p_id in players_id:
        member = ctx.get_guild().get_member(p_id)
        members.append(member)
    check_type(type, members)
    for member in members:
        player = await HotsPlayer.fetch(member, ctx.guild_id)
        if not player.blocked:
            players.append(player)
        else:
            raise errors.UserBlacklistedError(f"{player.battle_tag} заблокирован и не может принимать участие")
        while player.mmr in unique_mmr:
            player.mmr += 1
        unique_mmr.append(player.mmr)
    if not manual:
        players.sort(key=sort_by_mmr, reverse=True)
        team_one_mmr, team_two_mmr = util.min_diff_sets(
            [player.mmr for index, player in enumerate(players[:-2])])
        team_one_mmr += (players[-1].mmr,)
        team_two_mmr += (players[-2].mmr,)
        team_one = [player for player in players if player.mmr in team_one_mmr]
        team_two = [player for player in players if player.mmr in team_two_mmr]
    else:
        team_one = [player for player in players[:5]]
        team_two = [player for player in players[5:]]
    return team_one, team_two


async def _has_active_event(ctx: SamuroSlashContext):
    record = await ctx.app.db.fetchrow(
        """SELECT * FROM event_history WHERE guild_id = $1 AND room_id = $2 AND active = $3""",
        ctx.guild_id, ctx.channel_id, True
    )
    if record:
        return record

    return False


class HotsHero:
    def __init__(self, name: str):
        flag = False
        heroes_ru_list = const.ru_heroesdata
        name = name.title()
        name = get_close_matches(name, const.all_heroes, 2)[0]
        for hero, data in heroes_ru_list.items():
            if name in bug_names:
                name = bug_names[name]
            if name == data["name_en"] or name == data["name_ru"] or name == hero or name in data["nick"]:
                flag = True
                break  # вышли из цикла чтобы записать значение
        if not flag:
            raise errors.HeroNotFound
        self.id: str = data["name_id"]
        self.en: str = data["name_en"]
        self.ru: str = data["name_ru"]
        self.json: str = data["name_json"]
        self.role: str = data["role"]
        self.tier: str = data["tier"]
        self.nick: list = data["nick"]

        name_url = self.en.lower().replace(".", "").replace("'", "").replace(" ", "-")
        self.avatar: str = f"https://nexuscompendium.com/images/portraits/{name_url}.png"

        unit = const.gamestrings["gamestrings"]["unit"]
        heroesdata = const.heroesdata[self.id]
        self.description: str = unit["description"][self.id]
        self.expandedrole: str = unit["expandedrole"][self.id]

        self.complexity: int = int(heroesdata["ratings"]["complexity"])
        self.damage: int = heroesdata["ratings"]["damage"]
        self.survive: int = heroesdata["ratings"]["survivability"]
        self.utility: int = heroesdata["ratings"]["utility"]

        self.life: int = heroesdata["life"]["amount"]

        self.master_opinion = None
        self.master_opinion_link = None
        try:
            pancho_video = const.master_opinion.get(self.id)[0]
            if pancho_video is not None:
                youtube_url = "https://www.youtube.com/watch?v="
                self.master_opinion_link = f"{youtube_url}{pancho_video['url']}"
                self.master_opinion = f"[{pancho_video['date'][:10]}]({self.master_opinion_link})"
        except TypeError:  # нет мнений мастера
            self.master_opinion = "Отсутствует"

        name_url = self.en.lower().replace(".", "").replace("'", "")
        self.heroespatchnotes: str = f"https://heroespatchnotes.com/hero/{name_url.replace(' ', '')}.html"
        self.heroesprofile: str = (
            f"https://www.heroesprofile.com/Global/Talents/?hero={self.en.replace(' ', '+')}"
            f"&league_tier=master,diamond"
        )
        stlk_builds = const.stlk_builds[self.id]
        self.stlk: str = "💬 " + stlk_builds["comment1"] + "\n```" + stlk_builds["build1"] + "```"
        if len(stlk_builds["build2"]) > 0:
            self.stlk += "\n💬 " + stlk_builds["comment2"].capitalize() + "\n```" + stlk_builds["build2"] + "```"
        if len(stlk_builds["build3"]) > 0:
            self.stlk += "\n💬 " + stlk_builds["comment3"].capitalize() + "\n```" + stlk_builds["build3"] + "```"

        self.ability: dict = heroesdata["abilities"]
        self.talents: dict = heroesdata["talents"]

    def __repr__(self):
        return f"Hero({self.id})"

    def __str__(self):
        return self.id

    def __eq__(self, hero2):
        if self.id == hero2.id or self.en == hero2.en or self.ru == hero2.ru:
            return True
        else:
            return False

    def get_name_id(self):
        return self.id

    def get_role(self):
        return self.role

    def get_description_embed(self) -> hikari.Embed:
        embed = (
            hikari.Embed(
                title=f"{self.ru}",
                description=f"{self.description}",
                color=const.EMBED_BLUE,
            )
                .set_thumbnail(self.avatar)
                .add_field(
                name="Сложность",
                value=str(self.complexity),
                inline=True,
            )
                .add_field(name="Мнение мастера", value=self.master_opinion, inline=True)
                .add_field(
                name="Ссылки",
                value=f"[Патчноуты]({self.heroespatchnotes})\n[Винрейт по талантам]({self.heroesprofile})",
                inline=True,
            )
                .add_field(name="Билды", value=self.stlk, inline=False)
        )
        return embed

    def get_skills_embed(self, type: str) -> hikari.Embed:
        embed = hikari.Embed(title=f"{self.ru}", description="**Способности:**", color=const.EMBED_BLUE)
        embed.set_thumbnail(self.avatar)

        for elem in self.ability[type]:
            ability = HotsAbility(elem)
            description = (
                f"Время восстановления: {ability.cooldown}\n{ability.description}"
                if ability.cooldown
                else ability.description
            )
            embed.add_field(name=f"{ability.name} ({ability.type})", value=description, inline=False)
        return embed

    def get_talents_embed(self, level: int) -> hikari.Embed:
        embed = hikari.Embed(title=self.ru, description=f"**Таланты:** Уровень {level}", color=const.EMBED_BLUE)
        embed.set_thumbnail(self.avatar)
        for elem in self.talents["level" + str(level)]:
            talent = HotsTalent(elem)
            embed.add_field(name=f"{talent.name} ({talent.hotkey})", value=talent.description, inline=False)
        return embed

    def get_stlk_embed(self):
        embed = (
            hikari.Embed(
                title=f"{self.ru}",
                description=f"{self.description}",
                color=const.EMBED_BLUE,
            )
                .set_thumbnail(self.avatar)
                .add_field(name="Билды от Сталка", value=self.stlk, inline=False)
        )
        return embed


class HotsAbility:
    def __init__(self, ability: dict):
        self._nameId = ability["nameId"]
        self._buttonId = ability["buttonId"]
        self.type = ability["abilityType"]
        try:
            talent_name = f"{self._nameId}|{self._buttonId}|{self.type}|False"
            self.name = const.gamestrings["gamestrings"]["abiltalent"]["name"][talent_name]
        except:
            talent_name = f"{self._nameId}|{self._buttonId}|{self.type}|True"
            self.name = const.gamestrings["gamestrings"]["abiltalent"]["name"][talent_name]
        self.description = util.cleanhtml(const.gamestrings["gamestrings"]["abiltalent"]["full"][talent_name])
        try:
            ability_cooldown = util.cleanhtml(const.gamestrings["gamestrings"]["abiltalent"]["cooldown"][talent_name])
            cooldown_title, cooldown_time = ability_cooldown.split(":", 1)
            self.cooldown = cooldown_time
        except:
            self.cooldown = None


class HotsTalent:
    def __init__(self, talent: dict):
        self._nameId = talent["nameId"]
        self._buttonId = talent["buttonId"]
        self.hotkey = talent["abilityType"]
        talent_name = f"{self._nameId}|{self._buttonId}|{self.hotkey}|False"
        self.name = util.cleanhtml(const.gamestrings["gamestrings"]["abiltalent"]["name"][talent_name])
        self.description = util.cleanhtml(const.gamestrings["gamestrings"]["abiltalent"]["full"][talent_name])


@attr.define
class PlayerStats(DatabaseModel):
    id: hikari.Snowflake
    guild_id: hikari.Snowflake
    battle_tag: str
    points: int = 0
    win: int = 0
    lose: int = 0
    winstreak: int = 0
    max_ws: int = 0
    season: str = const.hots_season
    achievements: list = None

    async def update(self):
        await self._db.execute(
            """
            INSERT INTO players_stats (id, guild_id, season, points, win, lose, winstreak, max_ws)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (id, guild_id, season) DO
            UPDATE SET points = $4, win = $5, lose = $6, winstreak = $7, max_ws = $8""",
            self.id,
            self.guild_id,
            self.season,
            self.points,
            self.win,
            self.lose,
            self.winstreak,
            self.max_ws
        )

    @classmethod
    async def clear(cls, user: hikari.SnowflakeishOr[hikari.PartialUser], guild: hikari.SnowflakeishOr[hikari.PartialGuild]) -> None:
        return cls(
            hikari.Snowflake(user),
            hikari.Snowflake(guild),
            battle_tag=None,
            points=0,
            win=0,
            lose=0,
            winstreak=0,
            max_ws=0,
            season=const.hots_season
        )

    @classmethod
    async def fetch(
            cls, user: hikari.SnowflakeishOr[hikari.PartialUser], guild: hikari.SnowflakeishOr[hikari.PartialGuild]
    ) -> None:
        season = await cls._db.fetchval(
            """
            SELECT season FROM global_config where guild_id = $1
            """,
            hikari.Snowflake(guild)
        )
        record = await cls._db.fetchrow(
            """
            SELECT * FROM players_stats WHERE id = $1 AND guild_id = $2 AND season = $3
            """,
            hikari.Snowflake(user),
            hikari.Snowflake(guild),
            season
        )
        if not record:
            return cls(
                hikari.Snowflake(user),
                hikari.Snowflake(guild),
                battle_tag=None,
                points=0,
                win=0,
                lose=0,
                winstreak=0,
                max_ws=0,
                season=season,
                achievements=None
            )
        achievements = await cls._db.fetch(
            """
            SELECT ua.id, a.name, ua.timestamp FROM user_achievements as ua
                    INNER JOIN achievements as a
                    ON ua.achievement = a.id
                    WHERE ua.id = $1 AND ua.guild_id = $2 AND season = $3
            """,
            hikari.Snowflake(user),
            hikari.Snowflake(guild),
            season
        )
        return cls(
            id=hikari.Snowflake(record.get("id")),
            guild_id=hikari.Snowflake(record.get("guild_id")),
            battle_tag=record.get("btag"),
            points=record.get("points"),
            win=record.get("win"),
            lose=record.get("lose"),
            winstreak=record.get("winstreak"),
            max_ws=record.get("max_ws"),
            season=record.get("season"),
            achievements=achievements
        )


@attr.define()
class HotsPlayer(DatabaseModel):
    member: hikari.Member
    id: hikari.Snowflake
    guild_id: hikari.Snowflake
    mention: str = None
    battle_tag: str = None
    mmr: int = 2200
    league: HeroLeagues = HeroLeagues.BRONZE
    division: int = 0
    blocked: bool = False
    stats: PlayerStats = None

    async def log_page(self) -> list[hikari.Embed]:
        records = await self._db.fetch(
            """
            SELECT * FROM event_log WHERE id = $1
            ORDER BY event_id DESC 
            """,
            self.id,
        )
        paginator = lightbulb.utils.StringPaginator(max_chars=400)

        for record in records:
            mmr = str(record.get("delta_mmr"))
            if mmr != "0":
                mmr = '+' + mmr if record.get("winner") else '-' + mmr
            result = const.EMOJI_GREEN_UP if record.get("winner") else const.EMOJI_RED_DOWN
            paginator.add_line(f"{result} ID: {record.get('event_id')} {record.get('map')} ({mmr})")

        embeds = [
            hikari.Embed(title=f"Матчи {self.battle_tag}\nРезультат, ID, Карта, ММР", description=page, color=const.EMBED_BLUE)
                .set_thumbnail(self.member.avatar_url)
            for page in paginator.build_pages()
        ]
        return embeds

    async def profile(self) -> hikari.Embed:
        league = (
            self.league
            if self.league in [HeroLeagues.MASTER, HeroLeagues.GRANDMASTER]
            else f"{self.league} {self.division}"
        )
        if not self.blocked:
            embed = hikari.Embed(title=self.battle_tag, color=const.EMBED_BLUE)
            embed.set_thumbnail(self.member.avatar_url)
            embed.add_field(name="Лига", value=league, inline=True)
            embed.add_field(name="ММР", value=str(self.mmr), inline=True)

            if self.stats.battle_tag:
                await self.add_stats_info(embed=embed)

            if self.stats.achievements:
                await self.add_achievements_info(embed=embed)

        else:
            embed = hikari.Embed(title=self.battle_tag, description="Профиль заблокирован", color=const.ERROR_COLOR)
            embed.set_thumbnail(self.member.avatar_url)

        return embed

    async def change_log(self, admin: hikari.Member, type: str, message: str):
        now = datetime.now()
        await self._db.execute(
            """
            INSERT INTO profile_change_log (id, guild_id, admin_id, datetime, type, message) 
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            self.id,
            self.guild_id,
            admin.id,
            now,
            type,
            message
        )

    async def add_stats_info(self, embed: hikari.Embed) -> hikari.Embed:

        league_rating = ""
        # Позиция в рейтинге
        record = await self._db.fetchrow(
            """
            SELECT A.*
            FROM (SELECT *,
                         row_number() over (
                             ORDER BY mmr DESC
                             ) as league_rating
                  FROM players
                  WHERE league = $1) as A
                INNER JOIN players_stats as B
                    ON A.id = B.id
                    AND A.guild_id = B.guild_id
                INNER JOIN global_config gc
                    ON B.guild_id = gc.guild_id
                    AND B.season = gc.season
            WHERE A.id = $2
            """,
            HeroLeagues(self.league).name.capitalize(),
            self.id
        )
        if record:
            league_rating = f"• Позиция в лиге _{self.league}_: `{record.get('league_rating')}`"

        embed.add_field(
            name=f"Текущий сезон: {self.stats.season}",
            value=f"""{league_rating}
• Баллов: `{self.stats.points or "-"}`
• Побед: `{self.stats.win or "-"}`
• Поражений: `{self.stats.lose or "-"}`  
• Лучший винстрик: `{self.stats.max_ws or "-"}`      
            """
        )

        # Ставки
        records = await self._db.fetch(
            """
            SELECT * FROM vote_log WHERE id = $1
            """,
            self.id
        )
        correct = 0
        wrong = 0
        for record in records:
            if record.get("won"):
                correct += 1
            else:
                wrong += 1
        if correct > 0 and wrong > 0:
            rate = round(correct / (correct + wrong) * 100)
            embed.add_field(
                name="Ставки",
                value=f"""• Верных: `{correct or "-"}`  
• Ошибочных: `{wrong or "-"}`  """
            )

        return embed

    async def add_achievements_info(self, embed: hikari.Embed) -> hikari.Embed:
        text = "\n".join(f"• {a.get('name')}: <t:{int(a.get('timestamp').timestamp())}:D>" for a in self.stats.achievements)
        embed.add_field(
            name="Достижения",
            value=text
        )
        return embed

    async def update(self) -> None:
        self.league, self.division = self.get_league_division()
        await self._db.execute(
            """
            INSERT INTO players (id, guild_id, btag, mmr, league, division, blocked)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (id) DO
            UPDATE SET guild_id = $2, btag = $3, mmr = $4, league = $5, division = $6, blocked = $7""",
            self.id,
            self.guild_id,
            self.battle_tag,
            self.mmr,
            self.league,
            self.division,
            self.blocked
        )

    async def update_stats(self, winner: bool, points: int) -> None:
        if winner:
            self.stats.winstreak = self.stats.winstreak + 1 if self.stats.winstreak >= 0 else 1
            self.stats.win += 1
            if self.stats.winstreak > self.stats.max_ws:
                self.stats.max_ws = self.stats.winstreak
            self.stats.points += points
        else:
            self.stats.winstreak = self.stats.winstreak - 1 if self.stats.winstreak <= 0 else -1
            self.stats.lose += 1
            self.stats.points += points
        await self.stats.update()

    def fix_mmr(self, mmr: int) -> int:
        delta = 0
        if self.stats.winstreak > 5:
            delta = 4
        elif self.stats.winstreak > 2:
            delta = 2
        new_mmr = mmr + abs(self.stats.winstreak) + delta
        if self.mmr > 2900:
            new_mmr = new_mmr // 2
        return new_mmr

    def get_league_division(self) -> (str, int):
        league, division = next(
            x[1][0].split(sep='.') for x in enumerate(reversed(util.flatten_mmr.items())) if x[1][1] < self.mmr)
        return league, int(division)

    async def add_log(self, event_id: int, winner: bool, mmr: int, points: int, map: str):
        await self._db.execute(
            """INSERT INTO event_log (id, guild_id, event_id, winner, points, delta_mmr, map, season) 
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (id, guild_id, event_id, season) DO UPDATE 
            SET winner = $4, points = $5, delta_mmr = $6, season = $8 
            """,
            self.id,
            self.guild_id,
            event_id,
            winner,
            points,
            mmr,
            map,
            self.stats.season
        )

    async def ending_5x5(self, event_id: int, mmr: int, points: int, winner: bool, map: str) -> None:
        await self.update_stats(winner=winner, points=points)
        mmr = self.fix_mmr(mmr=mmr)
        if winner:
            self.mmr += mmr
        else:
            self.mmr -= mmr
        self.league, self.division = self.get_league_division()
        await self.update()

        await self.add_log(event_id=event_id, winner=winner, mmr=mmr, points=points, map=map)

    async def ending_unranked(self, event_id: int, mmr: int, points: int, winner: bool, map: str) -> None:
        await self.update_stats(winner=winner, points=points)
        await self.add_log(event_id=event_id, winner=winner, mmr=mmr, points=points, map=map)

    async def read_mmr(self, battletag: str) -> int:
        mmr_url = None
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) ' \
                     'Chrome/42.0.2311.135 Safari/537.36 Edge/12.246 '
        bname = battletag.replace('#', '%23')
        url = 'https://www.heroesprofile.com/Search/?searched_battletag=' + bname
        resp = requests.get(url, headers={"User-Agent": f"{user_agent}"})
        if 'Profile' in resp.url:
            mmr_url = resp.url.replace('Profile', 'MMR')
        else:
            soup = BeautifulSoup(resp.text, 'html.parser')
            multi_account = soup.find('div', attrs={'id': 'choose_battletag'})
            region = 'ion=2'
            if multi_account:
                links = multi_account.find_all('a')
                for link in links:
                    if region in link['href']:
                        mmr_url = 'https://www.heroesprofile.com' + link['href'].replace('®', '&reg').replace('Profile',
                                                                                                              'MMR')

        if mmr_url:
            resp = requests.get(mmr_url, headers={"User-Agent": f"{user_agent}"})
            soup = BeautifulSoup(resp.text, 'html.parser')
            mmr_table = soup.find('div', attrs={'class': 'gray-band-background table-section'})
            mmr_h3 = mmr_table.find('h3')
            try:
                text, mmr_str = mmr_h3.text.split(': ')
                mmr = int(mmr_str)
                return mmr if mmr > 2200 else 2200
            except ValueError:
                raise errors.DontHaveStormPlays
        raise errors.DontHaveStormPlays

    async def versus_stats(self, player2: hikari.Member) -> hikari.Embed:
        if self.id == player2.id:
            return hikari.Embed(
                title="❌ Ошибка сравнения",
                description="Выберите другого игрока для сравнения с собой",
                color=const.ERROR_COLOR
            )

        pl2 = await HotsPlayer.fetch(player2, self.guild_id)
        records = await self._db.fetch(
            """
            SELECT A.id, A.winner, A.event_id, B.id, B.winner FROM
                (SELECT * FROM event_log WHERE id=$1) AS A
            INNER JOIN
                (SELECT * FROM event_log WHERE id=$2) AS B
                    ON A.event_id = B.event_id
                ORDER BY A.event_id DESC
            """,
            self.id,
            pl2.id
        )

        if not records:
            return hikari.Embed(title=f"🔍 История матчей с {pl2.battle_tag}", description="Общих игр не найдено", color=const.EMBED_YELLOW)

        else:
            win_together = 0
            lose_together = 0
            win_versus = 0
            lose_versus = 0
            for record in records:
                values = list(record.values())
                a_id = values[0]
                a_winner = values[1]
                event_id = values[2]
                b_id = values[3]
                b_winner = values[4]
                if a_winner and b_winner:
                    win_together += 1
                elif a_winner and not b_winner:
                    win_versus += 1
                elif not a_winner and b_winner:
                    lose_versus += 1
                elif not a_winner and not b_winner:
                    lose_together += 1

            embed = hikari.Embed(
                title=f"🔍 История матчей с {pl2.battle_tag}",
                description=f"Общее количество матчей - `{len(records)}`",
                color=const.EMBED_BLUE
            )
            embed.add_field(
                name="Союзники",
                value=f"• Побед: `{win_together}`\n• Поражений: `{lose_together}`",
                inline=True
            )
            embed.add_field(
                name="Соперники",
                value=f"• Побед: `{win_versus}`\n• Поражений: `{lose_versus}`",
                inline=True
            )
            return embed




    @classmethod
    async def add(cls, member: hikari.Member, battletag: str):
        record = await cls._db.fetchrow(
            """SELECT * FROM players WHERE id = $1""",
            member.id,
        )
        if record:
            logger.warning(f"Профиль уже создан")
            raise errors.HasProfile

        profile = cls(
            member=member,
            id=member.id,
            guild_id=member.guild_id,
            mention=f"<@{member.id}>",
            battle_tag=battletag,
        )

        profile.mmr = await profile.read_mmr(battletag=battletag)
        profile.league, profile.division = profile.get_league_division()

        await cls._db.execute(
            """
            INSERT INTO players (btag, id, guild_id, mmr, league, division)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (id) DO NOTHING
            """,
            battletag,
            profile.id,
            profile.guild_id,
            profile.mmr,
            profile.league,
            profile.division
        )

        # дозаполнить данные
        profile.league = leagues.get(profile.league)
        profile.stats = await PlayerStats.clear(profile.id, profile.guild_id)

        return profile

    @classmethod
    async def fetch(cls, user: hikari.Member, guild_id: hikari.SnowflakeishOr[hikari.PartialGuild]):
        """Fetch a user from the database. If not present, returns a default DatabaseUser object.

        Parameters
        ----------
        user : hikari.SnowflakeishOr[hikari.PartialUser]
            The user to retrieve database information for.
        guild : hikari.SnowflakeishOr[hikari.PartialGuild]
            The guild the user belongs to.

        Returns
        -------
        DatabaseUser
            An object representing stored user data.
        """
        record = await cls._db.fetchrow(
            """SELECT * FROM players WHERE id = $1""",
            user.id,
        )

        # TODO: Получение профиля с heroesprofile

        if not record:
            logger.warning(f"Попытка посмотреть несуществующий профиль")
            raise errors.ProfileNotFound
            """return cls(
                hikari.Snowflake(user), hikari.Snowflake(guild), battle_tag=None, mmr=2200, league=HeroLeagues.BRONZE, division=5
            )"""

        return cls(
            member=user,
            id=hikari.Snowflake(record.get("id")),
            guild_id=hikari.Snowflake(record.get("guild_id")),
            mention=f"<@{record.get('id')}>",
            battle_tag=record.get("btag"),
            mmr=record.get("mmr"),
            league=leagues.get(record.get("league")),
            division=record.get("division"),
            stats=await PlayerStats.fetch(record.get("id"), guild_id),
            blocked=record.get("blocked")
        )

    @classmethod
    async def btag_fetch(cls, battle_tag: str, guild: hikari.SnowflakeishOr[hikari.PartialGuild]):
        """Fetch a user from the database. If not present, returns a default DatabaseUser object.

        Parameters
        ----------
        user : hikari.SnowflakeishOr[hikari.PartialUser]
            The user to retrieve database information for.
        guild : hikari.SnowflakeishOr[hikari.PartialGuild]
            The guild the user belongs to.

        Returns
        -------
        DatabaseUser
            An object representing stored user data.
        """
        record = await cls._db.fetchrow(
            """SELECT * FROM players WHERE btag = $1""",
            battle_tag,
        )

        if not record:
            raise errors.ProfileNotFound

        return cls(
            member=None,
            id=hikari.Snowflake(record.get("id")),
            guild_id=hikari.Snowflake(record.get("guild_id")),
            mention=f"<@{record.get('id')}>",
            battle_tag=record.get("btag"),
            mmr=record.get("mmr"),
            league=leagues.get(record.get("league")),
            division=record.get("division"),
            stats=await PlayerStats.fetch(record.get("id"), guild),
            blocked=record.get("blocked")
        )


@attr.define()
class HotsEvent(DatabaseModel):
    id: int
    time: datetime
    ftime: str
    guild_id: int
    room_id: int
    winner: str
    admin: str
    type: str
    active: bool
    win_points: int
    lose_points: int
    delta_mmr: int
    blue: list[HotsPlayer]
    red: list[HotsPlayer]
    season: str
    map: str = "??"

    async def update(self):
        await self._db.execute(
            """
            INSERT INTO event_history (event_id, guild_id, room_id, winner, active)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (event_id) DO
            UPDATE SET guild_id = $2, room_id = $3, winner = $4, active = $5""",
            self.id,
            self.guild_id,
            self.room_id,
            self.winner,
            self.active
        )

    @classmethod
    async def init(cls, time: datetime, ctx: SamuroSlashContext, type: str, win_p: int, lose_p: int, delta_mmr: int,
                   map: str, players: str):
        if await _has_active_event(ctx):
            raise errors.HasActiveEvent
        season = await cls._db.fetchval(
            """
            SELECT season FROM global_config where guild_id = $1
            """,
            hikari.Snowflake(ctx.guild_id)
        )
        event_id = None
        blue = red = []
        if type == EventTypes.event5x5:
            blue, red = await matchmaking_5x5(ctx, type, players_str=players)
        elif type in [EventTypes.unranked, EventTypes.manual5x5]:
            blue, red = await matchmaking_5x5(ctx, type, players_str=players, manual=True)
        if len(blue) > 0 and len(red) > 0:
            event_id = await cls._db.fetchval(
                """
                INSERT INTO event_history (time, guild_id, winner, active, 
                                            blue1, blue2, blue3, blue4, blue5, 
                                            red1, red2, red3, red4, red5, 
                                            room_id, delta_mmr, lose_points, admin, type, win_points, season, map)
                VALUES ($1, $2, $3, $4,
                        $5, $6, $7, $8, $9,
                        $10, $11, $12, $13, $14,
                        $15, $16, $17, $18, $19, $20, $21, $22
                        )
                RETURNING event_id
                """,
                time, ctx.guild_id, None, True,
                blue[0].battle_tag, blue[1].battle_tag, blue[2].battle_tag, blue[3].battle_tag, blue[4].battle_tag,
                red[0].battle_tag, red[1].battle_tag, red[2].battle_tag, red[3].battle_tag, red[4].battle_tag,
                ctx.channel_id, delta_mmr, lose_p, ctx.author.username, type, win_p, season, map

            )

        return cls(
            id=event_id,
            time=time,
            ftime=datetime.strftime(time, f_time),
            guild_id=ctx.guild_id,
            room_id=ctx.channel_id,
            winner=None,
            admin=ctx.author.id,
            type=type,
            active=True,
            win_points=win_p,
            lose_points=lose_p,
            delta_mmr=delta_mmr,
            blue=blue,
            red=red,
            season=season,
            map=map,
        )

    async def remove(self, ctx: SamuroSlashContext) -> hikari.Embed:
        record = await _has_active_event(ctx)

        if not record:
            raise errors.NoActiveEvent

        await self._db.execute("""DELETE FROM event_history WHERE event_id = $1""", record.get("event_id"))

        return hikari.Embed(
            title=f"Матч отменен",
            description=f"Можно пересоздать команды",
            color=const.EMBED_GREEN
        )

    @classmethod
    async def get_active_event(cls, ctx: SamuroSlashContext):
        record = await _has_active_event(ctx)

        if not record:
            raise errors.NoActiveEvent

        blue_btags = [
                record.get("blue1"),
                record.get("blue2"),
                record.get("blue3"),
                record.get("blue4"),
                record.get("blue5"),
            ]
        red_btags = [record.get("red1"), record.get("red2"), record.get("red3"), record.get("red4"), record.get("red5")]

        blue = [await HotsPlayer.btag_fetch(x, ctx.guild_id) for x in blue_btags]
        red = [await HotsPlayer.btag_fetch(x, ctx.guild_id) for x in red_btags]

        return cls(
            time=record.get("time"),
            ftime=datetime.strftime(record.get("time"), f_time),
            guild_id=record.get("guild_id"),
            room_id=record.get("room_id"),
            id=record.get("event_id"),
            winner=record.get("winner"),
            admin=record.get("admin"),
            type=record.get("type"),
            active=record.get("active"),
            win_points=record.get("win_points"),
            lose_points=record.get("lose_points"),
            delta_mmr=record.get("delta_mmr"),
            blue=blue,
            red=red,
            season=record.get("season"),
            map=record.get("map")
        )

    async def update_winner(self):
        await self._db.execute(
        """
            INSERT INTO event_history (event_id, winner)
            VALUES ($1, $2)
            ON CONFLICT (event_id) DO
            UPDATE SET winner = $2""",
        self.id,
        self.winner
        )

    async def ending_description(self, winner: EventWinner) -> hikari.Embed:
        color = const.EMBED_BLUE if winner == EventWinner.BLUE else const.ERROR_COLOR
        embed = hikari.Embed(
            title=f"Победила команда {winner.upper()}",
            description=f"ID матча: {self.id}\nКарта: {self.map}",
            color=color
        )
        embed.add_field(
            name="Blue",
            value='\n'.join([x.mention for x in self.blue]),
            inline=True
        )
        embed.add_field(
            name="Red",
            value='\n'.join([x.mention for x in self.red]),
            inline=True
        )
        return embed

    async def vote_log(self, winner):
        # TODO: Дописать голосования
        records = await self._db.fetch(
            """
            SELECT * FROM votes 
            WHERE event_id = $1""",
            self.id,
            )
        for record in records:
            flag = False
            if record.get("vote") == winner:
                flag = True
            await self._db.execute(
                """
                INSERT INTO vote_log (id, event_id, won)
                VALUES ($1, $2, $3)
                ON CONFLICT (id, event_id) DO UPDATE 
                SET won = $3
                """,
                record.get("id"),
                record.get("event_id"),
                flag
            )

    async def ending(self, ctx: SamuroSlashContext, winner: EventWinner) -> hikari.Embed:
        self.winner = winner

        winner_team = self.blue if self.winner == EventWinner.BLUE else self.red
        loser_team = self.blue if self.winner == EventWinner.RED else self.red
        if self.type in [EventTypes.event5x5, EventTypes.manual5x5]:
            for player in winner_team:
                await player.ending_5x5(event_id=self.id, mmr=self.delta_mmr, points=self.win_points, winner=True,
                                        map=self.map)
            for player in loser_team:
                await player.ending_5x5(event_id=self.id, mmr=self.delta_mmr, points=self.win_points, winner=False,
                                        map=self.map)
        elif self.type == EventTypes.unranked:
            self.delta_mmr = 0
            for player in winner_team:
                await player.ending_unranked(event_id=self.id, mmr=self.delta_mmr, points=self.win_points, winner=True,
                                             map=self.map)
            for player in loser_team:
                await player.ending_unranked(event_id=self.id, mmr=self.delta_mmr, points=self.win_points, winner=False,
                                             map=self.map)
        else:
            pass  # другие типы ивентов

        self.active = False
        await self.update()

        await self.vote_log(winner=winner)

        return await self.ending_description(winner=winner)

    def description(self):
        map_img = util.maps_url + self.map.replace(" ", "-").lower() + "/main.jpg"
        embed = hikari.Embed(
            title=f"Матч #{self.id} в режиме {self.type}",
            description=f"Карта: {self.map}",
            color=const.EMBED_GREEN
        )
        embed.set_thumbnail(map_img)
        embed.add_field(
            name="Blue",
            value='\n'.join([f"{x.mention} - {x.mmr}" for x in self.blue]),
            inline=True
        )
        embed.add_field(
            name="Red",
            value='\n'.join([f"{x.mention} - {x.mmr}" for x in self.red]),
            inline=True
        )
        return embed

    async def add_log(self):
        for player in self.blue:
            is_winner = self.winner == EventWinner.BLUE
            points = self.win_points if is_winner else self.lose_points
            await self._db.execute(
                """INSERT INTO event_log (id, guild_id, event_id, winner, points, delta_mmr, map) 
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT DO NOTHING 
                """,
                player.id,
                self.guild_id,
                self.id,
                is_winner,
                points,
                self.delta_mmr,
                self.map
            )

        for player in self.red:
            is_winner = self.winner == EventWinner.RED
            points = self.win_points if is_winner else self.lose_points
            await self._db.execute(
                """INSERT INTO event_log (id, guild_id, event_id, winner, points, delta_mmr) 
                VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT DO NOTHING 
                """,
                player.id,
                self.guild_id,
                self.id,
                is_winner,
                points,
                self.delta_mmr,
            )
        logger.info(f"Событие #{self.id} добавлено")

    @classmethod
    async def fetch(cls, event_id: int, guild_id: int):

        record = await cls._db.fetchrow(
            """SELECT * FROM event_history WHERE event_id = $1 AND guild_id = $2""",
            event_id, guild_id
        )

        if not record:
            raise errors.EventNotFound

        blue_btags = [
            record.get("blue1"),
            record.get("blue2"),
            record.get("blue3"),
            record.get("blue4"),
            record.get("blue5"),
        ]
        red_btags = [record.get("red1"), record.get("red2"), record.get("red3"), record.get("red4"), record.get("red5")]

        blue = [await HotsPlayer.btag_fetch(x, guild_id) for x in blue_btags]
        red = [await HotsPlayer.btag_fetch(x, guild_id) for x in red_btags]

        return cls(
            time=record.get("time"),
            ftime=datetime.strftime(record.get("time"), f_time),
            guild_id=record.get("guild_id"),
            room_id=record.get("room_id"),
            id=record.get("event_id"),
            winner=record.get("winner"),
            admin=record.get("admin"),
            type=record.get("type"),
            active=record.get("active"),
            win_points=record.get("win_points"),
            lose_points=record.get("lose_points"),
            delta_mmr=record.get("delta_mmr"),
            blue=blue,
            red=red,
            season=record.get("season"),
            map=record.get("map")
        )

    @classmethod
    async def fetch_all(cls, guild_id: int):
        records = await cls._db.fetch(
            """SELECT * FROM event_history WHERE guild_id = $1
            ORDER BY event_id DESC""",
            guild_id
        )
        if not records:
            return []

        return [
            cls(
                time=record.get("time"),
                ftime=datetime.strftime(record.get("time"), f_time),
                guild_id=record.get("guild_id"),
                room_id=record.get("room_id"),
                id=record.get("event_id"),
                winner=record.get("winner"),
                admin=record.get("admin"),
                type=record.get("type"),
                active=record.get("active"),
                lose_points=record.get("lose_points"),
                win_points=record.get("win_points"),
                delta_mmr=record.get("delta_mmr"),
                blue=[
                    record.get("blue1"),
                    record.get("blue2"),
                    record.get("blue3"),
                    record.get("blue4"),
                    record.get("blue5"),
                ],
                red=[
                    record.get("red1"),
                    record.get("red2"),
                    record.get("red3"),
                    record.get("red4"),
                    record.get("red5"),
                ],
                season=record.get("season"),
                map=record.get("map"),
            )
            for record in records
        ]

    def fetch_embed(self) -> hikari.Embed:
        map_img = util.maps_url + self.map.replace(" ", "-").lower() + "/main.jpg"
        winner = self.winner if self.winner else "Матч не завершен"
        embed = hikari.Embed(
            title=f"Матч #{self.id}",
            description=f"{self.ftime}\nВедущий: {self.admin}\nКарта: {self.map}\nПобедитель: **{winner}**",
            color=const.EMBED_BLUE
        )
        embed.set_thumbnail(map_img)
        embed.add_field(
            name="Blue",
            value='\n'.join([x.mention for x in self.blue]),
            inline=True
        )
        embed.add_field(
            name="Red",
            value='\n'.join([x.mention for x in self.red]),
            inline=True
        )
        return embed

    def result(self) -> hikari.Embed:
        embed = hikari.Embed(
            title=f"Матч #{self.id}",
            description=f"{self.ftime}\nВедущий: {self.admin}\nПобедитель: **{self.winner}**",
            color=const.EMBED_BLUE
        )
        embed.add_field(
            name="Blue",
            value='\n'.join([x.mention for x in self.blue]),
            inline=True
        )
        embed.add_field(
            name="Red",
            value='\n'.join([x.mention for x in self.red]),
            inline=True
        )
        return embed
