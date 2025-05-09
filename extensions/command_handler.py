from __future__ import annotations

import asyncio
import datetime
import logging
import traceback
import typing as t

import hikari
import lightbulb

from etc import constants as const
from etc.perms_str import get_perm_str
from models import SamuroContext, errors
from models.bot import SamuroBot
from models.context import SamuroPrefixContext, SamuroSlashContext
from models.errors import BotRoleHierarchyError, MemberExpectedError, RoleHierarchyError, UserBlacklistedError
from models.plugin import SamuroPlugin
from utils import helpers

logger = logging.getLogger(__name__)

ch = SamuroPlugin("Command Handler")


async def log_exc_to_channel(
    error_str: str, ctx: t.Optional[lightbulb.Context] = None, event: t.Optional[hikari.ExceptionEvent] = None
) -> None:
    """Log an exception traceback to the specified logging channel.

    Parameters
    ----------
    error_str : str
        The exception message to print.
    ctx : t.Optional[lightbulb.Context], optional
        The context to use for additional information, by default None
    event : t.Optional[hikari.ExceptionEvent], optional
        The event to use for additional information, by default None
    """

    error_lines = error_str.split("\n")
    paginator = lightbulb.utils.StringPaginator(max_chars=2000, prefix="```py\n", suffix="```")
    if ctx:
        if guild := ctx.get_guild():
            assert ctx.command is not None
            paginator.add_line(
                f"Error in '{guild.name}' ({ctx.guild_id}) during command '{ctx.command.name}' executed by user '{ctx.author}' ({ctx.author.id})\n"
            )

    elif event:
        paginator.add_line(
            f"Ignoring exception in listener for {event.failed_event.__class__.__name__}, callback {event.failed_callback.__name__}:\n"
        )
    else:
        paginator.add_line("Uncaught exception:")

    for line in error_lines:
        paginator.add_line(line)

    assert isinstance(ch.app, SamuroBot)
    channel_id = ch.app.config.ERROR_LOGGING_CHANNEL

    if not channel_id:
        return

    for page in paginator.build_pages():
        try:
            await ch.app.rest.create_message(channel_id, page)
        except Exception as error:
            logging.error(f"Failed sending traceback to error-logging channel: {error}")


async def application_error_handler(ctx: SamuroContext, error: BaseException) -> None:
    if isinstance(error, lightbulb.CheckFailure):
        error = error.causes[0] if error.causes else error.__cause__ if error.__cause__ else error

    if isinstance(error, UserBlacklistedError):
        await ctx.respond(
            embed=hikari.Embed(
                title="❌ Доступ к приложению прекращен",
                color=const.ERROR_COLOR,
            ),
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    # These may be raised outside of a check too
    if isinstance(error, lightbulb.MissingRequiredRole):
        await ctx.respond(
            embed=hikari.Embed(
                title="❌ Недостаточно прав",
                description="Необходимо иметь определенную роль для доступа к данной команде",
                color=const.ERROR_COLOR,
            ),
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    if isinstance(error, lightbulb.MissingRequiredPermission):
        await ctx.respond(
            embed=hikari.Embed(
                title="❌ Недостаточно прав",
                description=f"Требуется доступ к `{get_perm_str(error.missing_perms).replace('|', ', ')}` для использование этой команды",
                color=const.ERROR_COLOR,
            ),
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    if isinstance(error, lightbulb.BotMissingRequiredPermission):
        await ctx.respond(
            embed=hikari.Embed(
                title="❌ Боту недостаточно прав",
                description=f"Бот требует права на `{get_perm_str(error.missing_perms).replace('|', ', ')}` для использования этой команды",
                color=const.ERROR_COLOR,
            ),
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    if isinstance(error, lightbulb.CommandIsOnCooldown):
        await ctx.respond(
            embed=hikari.Embed(
                title="🕘 Cooldown",
                description=f"Пожалуйста, повторите через: `{datetime.timedelta(seconds=round(error.retry_after))}`",
                color=const.ERROR_COLOR,
            ),
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    if isinstance(error, lightbulb.MaxConcurrencyLimitReached):
        await ctx.respond(
            embed=hikari.Embed(
                title="❌ Максимальное количество инстанций",
                description="Вы достигли максимального количества запущенных экземпляров для этой команды. Пожалуйста, попробуйте позже",
                color=const.ERROR_COLOR,
            ),
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    if isinstance(error, BotRoleHierarchyError):
        await ctx.respond(
            embed=hikari.Embed(
                title="❌ Ошибка иерархии ролей",
                description="Самая высокая роль целевого пользователя выше роли бота",
                color=const.ERROR_COLOR,
            ),
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    if isinstance(error, RoleHierarchyError):
        await ctx.respond(
            embed=hikari.Embed(
                title="❌ Ошибка иерархии ролей",
                description="Самая высокая роль целевого пользователя выше вашей максимальной роли",
                color=const.ERROR_COLOR,
            ),
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    if isinstance(error, lightbulb.CheckFailure):
        await ctx.respond(
            embed=hikari.Embed(
                title="❌ Недостаточно прав",
                description="Убедитесь что у вас есть необходимая роль для использования команды",
                color=const.ERROR_COLOR,
            ),
            flags=hikari.MessageFlag.EPHEMERAL,
        )
        return

    if isinstance(error, lightbulb.CommandInvocationError):
        if isinstance(error.original, errors.UserBlacklistedError):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ Пользователь заблокирован",
                    description=error.original,
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        if isinstance(error.original, errors.HeroNotFound):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ Герой не найден",
                    description="Убедитесь что в поле `name` герой выбран из автодополнения",
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        if isinstance(error.original, errors.ProfileNotFound):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ Профиль не найден",
                    description=f"{error.original}\nИспользуйте команду `/profile add`",
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        if isinstance(error.original, errors.HasProfile):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ В базе уже есть этот профиль",
                    description="Используйте команду `/profile show`",
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        if isinstance(error.original, errors.EventNotFound):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ Не найдено события",
                    description="На данном сервере нет события с таким id\n Посмотреть ивенты можно командой `/event list`",
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        if isinstance(error.original, errors.DontHaveStormPlays):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ Нет игр в штормовой лиге",
                    description="На сайте `heroesprofile.com` не найдены игры в лиге.\n"
                    "Пожалуйста загрузите реплеи на сайт и повторите попытку",
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        if isinstance(error.original, errors.DontHaveLogs):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ История матчей пуста",
                    description="Пока не сыграно ни одного матча на сервере.",
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        if isinstance(error.original, errors.BadPlayersCount):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ Неверное число игроков",
                    description="Для данного режима нужно другое количество игроков",
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        if isinstance(error.original, errors.HasActiveEvent):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ Есть активное событие",
                    description="Завершите запущенное событие в данной комнате командой `/event end`",
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        if isinstance(error.original, errors.NoActiveEvent):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ Нет активных событий",
                    description="Запустите новое событие в данной комнате командой `/event create`",
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        if isinstance(error.original, asyncio.TimeoutError):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ Время действия истекло",
                    description="Время ожидания команды истекло",
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        elif isinstance(error.original, hikari.InternalServerError):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ Ошибка дискорд сервера",
                    description="Это действие не удалось выполнить из-за проблемы с серверами Discord. Пожалуйста, попробуйте снова через пару минут",
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        elif isinstance(error.original, hikari.ForbiddenError):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ Запрещено",
                    description=f"Действие не выполнено из-за отсутствия разрешений.\n**Ошибка:** ```{error.original}```",
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        elif isinstance(error.original, RoleHierarchyError):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ Ошибка иерархии ролей",
                    description="Не удалось выполнить это действие из-за попытки изменить пользователя с ролью выше или равной вашей самой высокой роли",
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        elif isinstance(error.original, BotRoleHierarchyError):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ Ошибка иерархии ролей",
                    description="Не удалось выполнить это действие из-за попытки изменить роль пользователя с ролью выше роли бота",
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

        if isinstance(error.original, MemberExpectedError):
            await ctx.respond(
                embed=hikari.Embed(
                    title="❌ Ожидается Member",
                    description="Ожидается пользователь, который является членом этого сервера",
                    color=const.ERROR_COLOR,
                ),
                flags=hikari.MessageFlag.EPHEMERAL,
            )
            return

    assert ctx.command is not None

    logging.error("Ignoring exception in command {}:".format(ctx.command.name))
    exception_msg = "\n".join(traceback.format_exception(type(error), error, error.__traceback__))
    logging.error(exception_msg)
    error = error.original if hasattr(error, "original") else error  # type: ignore

    await ctx.respond(
        embed=hikari.Embed(
            title="❌ Unhandled exception",
            description=f"Произошла ошибка, которой не должно было произойти. Пожалуйста [свяжитесь со мной](https://discord.gg/rt458hps) со скриншотом этого сообщения!\n**Ошибка:** ```{error.__class__.__name__}: {str(error).replace(ctx.app._token, '')}```",
            color=const.ERROR_COLOR,
        ).set_footer(text=f"Guild: {ctx.guild_id}"),
        flags=hikari.MessageFlag.EPHEMERAL,
    )

    await log_exc_to_channel(exception_msg, ctx)


@ch.listener(lightbulb.UserCommandErrorEvent)
@ch.listener(lightbulb.MessageCommandErrorEvent)
@ch.listener(lightbulb.SlashCommandErrorEvent)
async def application_command_error_handler(event: lightbulb.CommandErrorEvent) -> None:
    assert isinstance(event.context, SamuroSlashContext)
    await application_error_handler(event.context, event.exception)


@ch.listener(lightbulb.UserCommandCompletionEvent)
@ch.listener(lightbulb.SlashCommandCompletionEvent)
@ch.listener(lightbulb.MessageCommandCompletionEvent)
async def application_command_completion_handler(event: lightbulb.events.CommandCompletionEvent):
    if event.context.author.id in event.context.app.owner_ids:  # Ignore cooldowns for owner c:
        if cm := event.command.cooldown_manager:
            await cm.reset_cooldown(event.context)


@ch.listener(lightbulb.PrefixCommandErrorEvent)
async def prefix_error_handler(event: lightbulb.PrefixCommandErrorEvent) -> None:
    if event.context.author.id not in event.app.owner_ids:
        return
    if isinstance(event.exception, lightbulb.CheckFailure):
        return
    if isinstance(event.exception, lightbulb.CommandNotFound):
        return

    error = event.exception.original if hasattr(event.exception, "original") else event.exception  # type: ignore

    await event.context.respond(
        embed=hikari.Embed(
            title="❌ Exception encountered",
            description=f"```{error}```",
            color=const.ERROR_COLOR,
        )
    )
    raise event.exception


@ch.listener(lightbulb.events.CommandInvocationEvent)
async def command_invoke_listener(event: lightbulb.events.CommandInvocationEvent) -> None:
    logger.info(
        f"Command {event.command.name} was invoked by {event.context.author} in guild {event.context.guild_id}."
    )


@ch.listener(lightbulb.PrefixCommandInvocationEvent)
async def prefix_command_invoke_listener(event: lightbulb.PrefixCommandInvocationEvent) -> None:
    if event.context.author.id not in event.app.owner_ids:
        return

    if event.context.guild_id:
        assert isinstance(event.app, SamuroBot)
        me = event.app.cache.get_member(event.context.guild_id, event.app.user_id)
        assert me is not None

        if not helpers.includes_permissions(lightbulb.utils.permissions_for(me), hikari.Permissions.ADD_REACTIONS):
            return

    assert isinstance(event.context, SamuroPrefixContext)
    await event.context.event.message.add_reaction("▶️")


@ch.listener(hikari.ExceptionEvent)
async def event_error_handler(event: hikari.ExceptionEvent) -> None:
    logging.error("Ignoring exception in listener {}:".format(event.failed_event.__class__.__name__))
    exception_msg = "\n".join(traceback.format_exception(*event.exc_info))
    logging.error(exception_msg)
    await log_exc_to_channel(exception_msg, event=event)


def load(bot: SamuroBot) -> None:
    bot.add_plugin(ch)


def unload(bot: SamuroBot) -> None:
    bot.remove_plugin(ch)


# by fenrir#5455
