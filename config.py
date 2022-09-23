import typing as t

import attr

"""
Configuration file example for the Discord bot Samuro.
The actual configuration is read from 'config.py', which must exist.
All secrets are stored and read from the .env file.
"""


@attr.frozen(weakref_slot=False)
class Config:
    DEV_MODE: bool = False  # Control debugging mode, commands will default to DEBUG_GUILDS if True

    ERROR_LOGGING_CHANNEL: int = 1011166844725497856  # Error tracebacks will be sent here if specified

    DB_BACKUP_CHANNEL: int = 880863858653286401  # DB backups will be sent here if specified

    DEBUG_GUILDS: t.Sequence[int] = (845658540341592096, )  # Commands will only be registered here if DEV_MODE is on

    OWNER: int = 196583204164075520

# by fenrir#5455
