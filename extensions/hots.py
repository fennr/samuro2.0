import enum
import logging
import re
import typing as t
from difflib import get_close_matches
from datetime import datetime

import hikari
import lightbulb
import miru
import psutil
import pytz

import asyncio

import models
import utils.helpers
from etc import constants as const
from models import SamuroBot
from models.checks import bot_has_permissions
from models.checks import has_permissions
from models.checks import is_lead, is_above_target
from models.context import SamuroMessageContext, SamuroUserContext
from models.components import *
from models.views import AuthorOnlyView
from models.context import SamuroSlashContext
from models.plugin import SamuroPlugin
from models.heroes import HotsHero, HotsPlayer, HotsEvent
from utils import helpers, hots as util
from utils.hots import EventWinner
from miru.abc import ViewItem
from utils.scheduler import ConversionMode

logger = logging.getLogger(__name__)

hots = SamuroPlugin("HeroesOfTheStorm Commands")

test_guild = 642852514865217578


class HeroCommands(str, enum.Enum):
    HERO = "hero"
    SKILL = "skill"
    TALENT = "talent"
    STLK = "stlk"


class HeroView(AuthorOnlyView):
    def __init__(self, *, lctx: lightbulb.Context, timeout: float = 180, command: str, hero: HotsHero) -> None:
        super(HeroView, self).__init__(lctx, timeout=timeout)
        self.command = command
        self.hero: HotsHero = hero
        self.update_select()

    async def on_timeout(self) -> None:
        try:
            assert self.children is not None
            self.clear_items()
            await self.lctx.edit_last_response(components=self.build())
            self.stop()
        except hikari.NotFoundError:
            pass

    def remove_selects(self):
        for item in self.children:
            if isinstance(item, SkillSelect) or isinstance(item, TalentSelect):
                self.remove_item(item)

    def update_select(self):
        self.remove_selects()
        if self.command == HeroCommands.SKILL:
            self.add_item(SkillSelect(hero=self.hero))
        if self.command == HeroCommands.TALENT:
            self.add_item(TalentSelect(hero=self.hero))

    @miru.button(label="Герой", style=hikari.ButtonStyle.PRIMARY, custom_id="hero")
    async def hero_button(self, button: miru.Button, ctx: miru.ViewContext) -> None:
        self.command = HeroCommands.HERO
        embed = self.hero.get_description_embed()
        self.update_select()
        await ctx.edit_response(embed=embed, components=self.build())

    @miru.button(label="Способности", style=hikari.ButtonStyle.PRIMARY, custom_id="skill")
    async def skill_button(self, button: miru.Button, ctx: miru.ViewContext) -> None:
        self.command = HeroCommands.SKILL
        embed = self.hero.get_skills_embed(type='basic')
        self.update_select()
        await ctx.edit_response(embed=embed, components=self.build())

    @miru.button(label="Таланты", style=hikari.ButtonStyle.PRIMARY, custom_id="talent")
    async def talent_button(self, button: miru.Button, ctx: miru.ViewContext) -> None:
        self.command = HeroCommands.TALENT
        embed = self.hero.get_talents_embed(level=1)
        self.update_select()
        await ctx.edit_response(embed=embed, components=self.build())


class EventView(miru.View):
    def __init__(self, *, ctx: SamuroSlashContext, event: HotsEvent) -> None:
        super(EventView, self).__init__(timeout=240)
        self.ctx = ctx
        self.event = event

    async def on_timeout(self) -> None:
        for item in self.children:
            assert isinstance(item, (miru.Button, miru.Select))
            item.disabled = True
        try:
            await self.ctx.edit_last_response(components=self.build())
        except hikari.NotFoundError:
            pass

    @miru.button(label="Проголосовать", style=hikari.ButtonStyle.PRIMARY, custom_id="blue")
    async def blue_vote(self, button: miru.Button, ctx: miru.ViewContext) -> None:
        await self.ctx.app.db.execute(
            """
            INSERT INTO votes (id, event_id, vote) VALUES ($1, $2, $3)
            ON CONFLICT (id, event_id) 
            DO UPDATE SET vote = $3""",
            self.ctx.author.id,
            self.event.id,
            util.EventWinner.BLUE
        )
        await ctx.respond("Засчитан голос за синих", flags=hikari.MessageFlag.EPHEMERAL)

    @miru.button(label="Проголосовать", style=hikari.ButtonStyle.DANGER, custom_id="red")
    async def red_vote(self, button: miru.Button, ctx: miru.ViewContext) -> None:
        await self.ctx.app.db.execute(
            """
            INSERT INTO votes (id, event_id, vote) VALUES ($1, $2, $3)
            ON CONFLICT (id, event_id) 
            DO UPDATE SET vote = $3""",
            self.ctx.author.id,
            self.event.id,
            util.EventWinner.RED
        )
        await ctx.respond("Засчитан голос за красных", flags=hikari.MessageFlag.EPHEMERAL)


class SkillSelect(miru.Select):
    def __init__(self, *, hero: HotsHero) -> None:
        super(SkillSelect, self).__init__(
            options=[
                miru.SelectOption(label="Базовые", value="basic"),
                miru.SelectOption(label="Героические", value="heroic"),
                miru.SelectOption(label="Особая", value="trait"),
            ],
            placeholder="Посмотреть другие способности",
        )
        self.hero = hero

    async def callback(self, ctx: miru.ViewContext) -> None:
        embed = self.hero.get_skills_embed(type=self.values[0])
        await ctx.edit_response(embed=embed, components=self.view.build())


class TalentSelect(miru.Select):
    def __init__(self, *, hero: HotsHero) -> None:
        super(TalentSelect, self).__init__(
            options=[
                miru.SelectOption(label="1", value="1"),
                miru.SelectOption(label="4", value="4"),
                miru.SelectOption(label="7", value="7"),
                miru.SelectOption(label="10", value="10"),
                miru.SelectOption(label="13", value="13"),
                miru.SelectOption(label="16", value="16"),
                miru.SelectOption(label="20", value="20"),
            ],
            placeholder="Посмотреть другие таланты"
        )
        self.hero = hero

    async def callback(self, ctx: miru.ViewContext) -> None:
        embed = self.hero.get_talents_embed(level=int(self.values[0]))
        await ctx.edit_response(embed=embed, components=self.view.build())


@hots.command
@lightbulb.option(
    name="name",
    description="Имя героя",
    type=t.Optional[str],
    required=True,
    autocomplete=True
)
@lightbulb.command(
    name=HeroCommands.HERO,
    description="Информация о герое",
    pass_options=True
)
@lightbulb.implements(lightbulb.SlashCommand)
async def hero_command(ctx: SamuroSlashContext, name: str) -> None:
    hero = HotsHero(name.title())
    view = HeroView(lctx=ctx, command=ctx.command.name, hero=hero)

    embed = hero.get_description_embed()

    resp = await ctx.respond(
        embed=embed,
        components=view.build()
    )
    view.start(await resp.message())


@hots.command
@lightbulb.option(
    name="type",
    description="Тип способности",
    required=True,
    choices=["basic", "heroic", "trait"]
)
@lightbulb.option(
    name="name",
    description="Имя героя",
    type=t.Optional[str],
    required=True,
    autocomplete=True
)
@lightbulb.command(
    name=HeroCommands.SKILL,
    description="Информация о навыках героя",
    pass_options=True
)
@lightbulb.implements(lightbulb.SlashCommand)
async def skills_command(ctx: SamuroSlashContext, name: str, type: str) -> None:
    hero = HotsHero(name.title())
    view = HeroView(lctx=ctx, command=ctx.command.name, hero=hero)

    embed = hero.get_skills_embed(type)

    resp = await ctx.respond(
        embed=embed,
        components=view.build()
    )
    view.start(await resp.message())


@hots.command
@lightbulb.option(
    name="level",
    description="Уровень таланта",
    type=int,
    required=True,
    choices=[1, 4, 7, 10, 13, 16, 20]
)
@lightbulb.option(
    name="name",
    description="Имя героя",
    type=t.Optional[str],
    required=True,
    autocomplete=True
)
@lightbulb.command(
    name=HeroCommands.TALENT,
    description="Информация о талантах героя",
    pass_options=True
)
@lightbulb.implements(lightbulb.SlashCommand)
async def talent_command(ctx: SamuroSlashContext, name: str, level: int) -> None:
    hero = HotsHero(name)
    view = HeroView(lctx=ctx, command=ctx.command.name, hero=hero)

    embed = hero.get_talents_embed(level)

    resp = await ctx.respond(
        embed=embed,
        components=view.build()
    )
    view.start(await resp.message())


@hots.command
@lightbulb.option(
    name="name",
    description="Имя героя",
    type=t.Optional[str],
    required=True,
    autocomplete=True
)
@lightbulb.command(
    name=HeroCommands.STLK,
    description="Билды от Сталка",
    pass_options=True
)
@lightbulb.implements(lightbulb.SlashCommand)
async def stlk_command(ctx: SamuroSlashContext, name: str) -> None:
    hero = HotsHero(name)

    embed = hero.get_stlk_embed()

    await ctx.respond(
        embed=embed
    )


@stlk_command.autocomplete("name")
@talent_command.autocomplete("name")
@skills_command.autocomplete("name")
@hero_command.autocomplete("name")
async def hero_name_ac(
    option: hikari.AutocompleteInteractionOption, interaction: hikari.AutocompleteInteraction
) -> t.List[str]:
    if option.value:
        assert isinstance(option.value, str)
        return get_close_matches(option.value.title(), util.all_heroes, 3)


@hots.command
@lightbulb.add_checks(
    has_permissions(hikari.Permissions.ADMINISTRATOR)
)
@lightbulb.option("name", "Имя текущего сезона")
@lightbulb.command("season", "Установить название текущего сезона", pass_options=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def set_season(ctx: SamuroSlashContext, name: str) -> None:
    await ctx.app.db.execute(
        """
        INSERT INTO global_config (guild_id, prefix, season)
        VALUES ($1, $2, $3)
        ON CONFLICT (guild_id) DO UPDATE
        SET season = $3 
        """,
        ctx.guild_id, None, name)
    await ctx.respond(
        embed=hikari.Embed(
            title="✅ Сезон обновлен",
            description=f"Имя нового сезона - {name}",
            color=const.MISC_COLOR
        )
    )


@hots.command
@lightbulb.command("profile", "Команды связанные с профилями")
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def hots_profile(ctx: SamuroSlashContext) -> None:
    pass


@hots_profile.child
@lightbulb.option(
    name="member",
    description="Профиль игрока",
    type=hikari.Member,
    required=True,
)
@lightbulb.command(
    name="show",
    description="Показать профиль",
    pass_options=True
)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def get_profile(ctx: SamuroSlashContext, member: hikari.Member) -> None:
    user = await HotsPlayer.fetch(member, guild_id=ctx.guild_id)
    await ctx.respond(
        embed=await user.profile()
    )


@hots.command
@lightbulb.command("HotS профиль", "Показать профиль игрока", pass_options=True)
@lightbulb.implements(lightbulb.UserCommand)
async def get_profile_user_command(ctx: SamuroUserContext, target: hikari.Member) -> None:
    user = await HotsPlayer.fetch(target, ctx.guild_id)
    await ctx.respond(embed=await user.profile())


@hots_profile.child
@lightbulb.option("battletag", "Батлтег игрока", type=str, required=True)
@lightbulb.option("member", "Пользователь", type=hikari.Member, required=True)
@lightbulb.command("add", "Добавить профиль в базу", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def get_profile(ctx: SamuroSlashContext, member: hikari.Member, battletag: str) -> None:
    await ctx.respond(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)
    user = await HotsPlayer.add(member=member, battletag=battletag)
    await ctx.respond(embed=await user.profile())


@hots_profile.child
@lightbulb.option(
    name="member",
    description="Профиль игрока",
    type=hikari.Member,
    required=True,
)
@lightbulb.command(
    name="history",
    description="История матчей",
    pass_options=True
)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def get_history(ctx: SamuroSlashContext, member: hikari.Member) -> None:
    user = await HotsPlayer.fetch(member, guild_id=ctx.guild_id)

    embeds = await user.log_page()

    navigator = models.AuthorOnlyNavigator(ctx, pages=embeds)

    await navigator.send(ctx.interaction)


@hots.command
@lightbulb.command("История матчей", "Показать историю матчей", pass_options=True)
@lightbulb.implements(lightbulb.UserCommand)
async def get_history_user_command(ctx: SamuroUserContext, target: hikari.Member) -> None:
    user = await HotsPlayer.fetch(target, guild_id=ctx.guild_id)

    embeds = await user.log_page()

    navigator = models.AuthorOnlyNavigator(ctx, pages=embeds)
    await navigator.send(ctx.interaction)


@hots.command
@lightbulb.command("event", "Команды связанные с ивентами")
@lightbulb.implements(lightbulb.SlashCommandGroup)
async def hots_events(ctx: SamuroSlashContext) -> None:
    pass


@hots_events.child
@lightbulb.option(name="event_id", description="ID матча", type=int, required=True)
@lightbulb.command(name="view", description="Показать матч", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def get_event(ctx: SamuroSlashContext, event_id: int) -> None:
    event = await HotsEvent.fetch(event_id, guild_id=ctx.guild_id)  # потом поменять на ctx.guild.id

    embed = event.fetch_embed()

    await ctx.respond(
        embed=embed
    )


@hots_events.child
@lightbulb.command(name="list", description="Список всех ивентов")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def event_list(ctx: SamuroSlashContext) -> None:
    events = await HotsEvent.fetch_all(guild_id=ctx.guild_id)

    if not events:
        ctx.respond(
            "Нет событий на сервере"
        )

    paginator = lightbulb.utils.StringPaginator(max_chars=300)
    for event in events:
        emoji = util.get_emoji_winner(event.winner)
        paginator.add_line(f"{emoji} ID: {event.id} - {event.ftime} - {event.map}")

    embeds = [
        hikari.Embed(
            title="Список всех матчей сервера\nПобедитель, ID, Время, Карта",
            description=page,
            color=const.EMBED_BLUE,
        )
        for page in paginator.build_pages()
    ]
    navigator = models.AuthorOnlyNavigator(ctx, pages=embeds)
    await navigator.send(ctx.interaction)


@hots_events.child
@lightbulb.add_checks(
    lightbulb.owner_only
)
@lightbulb.option(name="event_id", description="ID матча", type=int, required=True)
@lightbulb.command(name="log", description="Дозапись матча", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def event_add_log(ctx: SamuroSlashContext, event_id: int) -> None:
    event = await HotsEvent.fetch(event_id, guild_id=ctx.guild_id)
    await event.add_log()
    await ctx.respond(
        f"Запись матча #{event.id} добавлена"
    )


@hots_events.child
@lightbulb.add_checks(is_lead)
@lightbulb.option(name="lose_p", description="Баллы за поражение", type=int, min_value=1, max_value=4, default=1)
@lightbulb.option(name="win_p", description="Баллы за победу", type=int, min_value=4, max_value=8, default=4)
@lightbulb.option(name="mmr", description="Изменение ммр за матч", type=int, default=4, min_value=0, max_value=8)
@lightbulb.option(name="players", description="Игроки", type=t.List[hikari.Member], required=True)
@lightbulb.option(name="map", description="Карта", choices=util.maps, required=True)
@lightbulb.option(name="type", description="Тип ивента", choices=util.event_types, default=util.event_types[0])
@lightbulb.command(name="create", description="Создать ивент", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def event_create(ctx: SamuroSlashContext, type: str, map: str, players: str,
                       mmr: int, win_p: int, lose_p: int) -> None:
    event = await HotsEvent.init(datetime.now(), ctx, type=type, win_p=win_p, lose_p=lose_p, delta_mmr=mmr,
                                 map=map, players=players)
    view = EventView(ctx=ctx, event=event)
    embed = event.description()

    resp = await ctx.respond(embed=embed, components=view.build())
    view.start(await resp.message())


@hots_events.child
@lightbulb.add_checks(is_lead)
@lightbulb.command(name="remove", description="Удалить ивент")
@lightbulb.implements(lightbulb.SlashSubCommand)
async def event_remove(ctx: SamuroSlashContext) -> None:
    event = await HotsEvent.get_active_event(ctx)

    embed = await event.remove(ctx=ctx)

    await ctx.respond(embed=embed)


@hots_events.child
@lightbulb.add_checks(is_lead)
@lightbulb.option(name="winner", description="Победитель", choices=[EventWinner.BLUE.value, EventWinner.RED.value],
                  required=True)
@lightbulb.command(name="end", description="Завершить ивент", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def event_ending(ctx: SamuroSlashContext, winner: str) -> None:
    event = await HotsEvent.get_active_event(ctx)

    embed = await event.ending(ctx=ctx, winner=winner)

    await ctx.respond(embed=embed)


@hots_events.child
@lightbulb.add_checks(lightbulb.owner_only)
@lightbulb.option(name="winner", description="Победитель", choices=[EventWinner.BLUE.value, EventWinner.RED.value],
                  required=True)
@lightbulb.command(name="test", description="Тестирование голосований", pass_options=True)
@lightbulb.implements(lightbulb.SlashSubCommand)
async def event_test(ctx: SamuroSlashContext, winner: str) -> None:
    event = await HotsEvent.get_active_event(ctx)

    await event.vote_log(winner=winner)

    await ctx.respond("Голоса подсчитаны", flags=hikari.MessageFlag.EPHEMERAL)


'''@hots.command
@lightbulb.command(name="emojis", description="Показать все эмодзи")
@lightbulb.implements(lightbulb.SlashCommand)
async def get_emojis(ctx: SamuroSlashContext) -> None:
    emojis = await ctx.get_guild().fetch_emojis()

    for emoji in emojis:
        print(emoji)

    await ctx.respond("Команда отработала", flags=hikari.MessageFlag.EPHEMERAL)'''

'''@hots.listener(hikari.InteractionCreateEvent)
async def inter_event(event: hikari.InteractionCreateEvent):
    if not isinstance(event.interaction, hikari.ComponentInteraction):
        return'''


def load(bot: SamuroBot) -> None:
    bot.add_plugin(hots)


def unload(bot: SamuroBot) -> None:
    bot.remove_plugin(hots)

# by fenrir#5455
