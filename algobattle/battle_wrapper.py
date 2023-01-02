"""Abstract base class for wrappers that execute a specific kind of battle.

The battle wrapper class is a base class for specific wrappers, which are
responsible for executing specific types of battle. They share the
characteristic that they are responsible for updating some match data during
their run, such that it contains the current state of the match.
"""
from importlib.metadata import entry_points
import logging
from abc import abstractmethod, ABC
from typing import Any, ClassVar
from algobattle.fight_handler import FightHandler
from algobattle.team import Role
from algobattle.observer import Subject
from algobattle.util import CLIParsable

logger = logging.getLogger('algobattle.battle_wrapper')


class BattleWrapper(Subject, ABC):
    """Abstract Base class for wrappers that execute a specific kind of battle."""

    _wrappers: ClassVar[dict[str, type["BattleWrapper"]]] = {}

    scoring_team: ClassVar[Role] = "solver"

    Config: ClassVar[type[CLIParsable]]
    """Object containing the config variables the wrapper will use."""

    @staticmethod
    def all() -> dict[str, type["BattleWrapper"]]:
        """Returns a list of all registered wrappers."""
        for entrypoint in entry_points(group="algobattle.wrappers"):
            if entrypoint.name not in BattleWrapper._wrappers:
                wrapper: type[BattleWrapper] = entrypoint.load()
                BattleWrapper._wrappers[wrapper.name()] = wrapper
        return BattleWrapper._wrappers

    def __init_subclass__(cls, notify_var_changes: bool = False) -> None:
        if cls.name() not in BattleWrapper._wrappers:
            BattleWrapper._wrappers[cls.name()] = cls
        return super().__init_subclass__(notify_var_changes)

    @abstractmethod
    def score(self) -> float:
        """The score achieved by the solver of this battle."""
        raise NotImplementedError

    @staticmethod
    def format_score(score: float) -> str:
        """Formats a score nicely."""
        return f"{score:.2f}"

    @abstractmethod
    def display(self) -> str:
        """Nicely formats the object."""
        raise NotImplementedError

    @classmethod
    def name(cls) -> str:
        """Name of the type of this battle wrapper."""
        return cls.__name__

    @abstractmethod
    def run_battle(self, config: Any, fight_handler: FightHandler, min_size: int) -> None:
        """Calculates the next instance size that should be fought over"""
        raise NotImplementedError
