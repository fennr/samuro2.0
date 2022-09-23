from __future__ import annotations

import typing as t

import hikari
import lightbulb

import etc.constants as const
from models.context import SamuroSlashContext
from models.plugin import SamuroPlugin

if t.TYPE_CHECKING:
    from models import SamuroBot


help = SamuroPlugin("Help")


help_embeds = {
    # Default no topic help
    None: hikari.Embed(
        title="ℹ️ __Help__",
        description="""**Привет, это помощь по использованию бота Samuro!**
            
Чтобы начать использовать бота, набери `/` чтобы увидеть все доступные команды! Чтобы посмотреть справку по нескольким особенностям можно рабрать `/help topic_name`.

Если нужна помощь или вы обнаружили баг, можно написать на [Samuro_dev сервер](https://discord.gg/rt458hps)!

Thank you for using Samuro!""",
        color=const.EMBED_BLUE,
    ),
    # Default no topic help for people with manage guild perms
    "admin_home": hikari.Embed(
        title="ℹ️ __Help__",
        description="""**Это хелп по использованию команд бота Samuro**
            
Чтобы начать использовать бота набери `/` чтобы увидеть все доступные команды! Несколько дополнительных настроек можно изучить командами `/help topic_name`.

Для настройки бота на сервере необходимо набрать `/settings`.

Проверить, что бот корректно настроен можно командой `/troubleshoot`.

Если нужна помощь или вы обнаружили баг, можно написать на [Samuro_dev сервер](https://discord.gg/rt458hps)!

""",
        color=const.EMBED_BLUE,
    ),
    "time-formatting": hikari.Embed(
        title="ℹ️ __Help: Формат времени__",
        description="""Бот поддерживает ввод времени в различных форматах:

**Даты:**
`2022-03-04 23:43`
`04/03/2022 23:43`
`2022/04/03 11:43PM`
`...`

**Относительный ввод:**
`через 10 минут`
`через 2 дня`
`...`

**ℹ️ Заметка:**
Абсолютное время требует, чтобы бот знал ваш часовой пояс. Его можно установить командой `/timezone`.
""",
        color=const.EMBED_BLUE,
    ),
    "permissions": hikari.Embed(
        title="ℹ️ __Help: Разрешения__",
        description="""Разрешения редактируются через настройки сервера:
```Настройки сервера > Интеграция > Samuro```
Здесь можно настроить разрешения для каждой команды, как вы считаете нужным или оставить по-умолчанию""",
        color=const.EMBED_BLUE,
    ).set_image("https://cdn.discordapp.com/attachments/836300326172229672/949047433038544896/unknown.png"),
    "configuration": hikari.Embed(
        title="ℹ️ ___Help: Конфигурация__",
        description="""Для настройки бота используйте команду `/settings`. Это откроет интерактивное меню, в котором можно изменить различные настройки бота под ваш сервер.""",
        color=const.EMBED_BLUE,
    ),
}


@help.command
@lightbulb.option(
    "topic",
    "Особенности настройки бота",
    required=False,
    choices=["time-formatting", "configuration", "permissions"],
)
@lightbulb.command("help", "Получить помощь по различным функциям бота", pass_options=True)
@lightbulb.implements(lightbulb.SlashCommand)
async def help_cmd(ctx: SamuroSlashContext, topic: t.Optional[str] = None) -> None:
    if ctx.member:
        topic = (
            topic or "admin_home"
            if (lightbulb.utils.permissions_for(ctx.member) & hikari.Permissions.MANAGE_GUILD)
            else topic
        )
    await ctx.respond(embed=help_embeds[topic])


def load(bot: SamuroBot) -> None:
    bot.add_plugin(help)


def unload(bot: SamuroBot) -> None:
    bot.remove_plugin(help)


# by fenrir#5455
