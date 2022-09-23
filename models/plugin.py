from __future__ import annotations

import typing as t

import lightbulb

if t.TYPE_CHECKING:
    from models.bot import SamuroBot


class SamuroPlugin(lightbulb.Plugin):
    @property
    def app(self) -> SamuroBot:
        return super().app  # type: ignore

    @app.setter
    def app(self, val: SamuroBot) -> None:
        self._app = val
        self.create_commands()

    @property
    def bot(self) -> SamuroBot:
        return super().bot  # type: ignore


# by fenrir#5455
