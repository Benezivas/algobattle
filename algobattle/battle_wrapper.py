"""Abstract base class for wrappers that execute a specific kind of battle.

The battle wrapper class is a base class for specific wrappers, which are
responsible for executing specific types of battle. They share the
characteristic that they are responsible for updating some match data during
their run, such that it contains the current state of the match.
"""
from __future__ import annotations
from dataclasses import dataclass
from importlib.metadata import entry_points
import logging
from abc import abstractmethod, ABC
from typing import Any, Generic, TypeVar
from algobattle.fight_handler import FightHandler

from algobattle.observer import Subject
from algobattle.problem import Instance, Problem, Solution
from algobattle.util import CLIParsable

logger = logging.getLogger('algobattle.battle_wrapper')


_Instance, _Solution = TypeVar("_Instance", bound=Instance), TypeVar("_Solution", bound=Solution[Any])


class BattleWrapper(Generic[_Instance, _Solution], ABC):
    """Abstract Base class for wrappers that execute a specific kind of battle."""

    @dataclass
    class Config(CLIParsable):
        """Object containing the config variables the wrapper will use."""

        pass

    _wrappers: dict[str, type[BattleWrapper[Any, Any]]] = {}

    @staticmethod
    def all() -> dict[str, type[BattleWrapper[Any, Any]]]:
        """Returns a list of all registered wrappers."""
        for entrypoint in entry_points(group="algobattle.wrappers"):
            if entrypoint.name not in BattleWrapper._wrappers:
                wrapper: type[BattleWrapper[Any, Any]] = entrypoint.load()
                BattleWrapper._wrappers[wrapper.name()] = wrapper
        return BattleWrapper._wrappers

    def __init_subclass__(cls) -> None:
        if cls.name() not in BattleWrapper._wrappers:
            BattleWrapper._wrappers[cls.name()] = cls
        return super().__init_subclass__()

    def __init__(self, config: BattleWrapper.Config, problem: Problem[_Instance, _Solution]) -> None:
        super().__init__()
        self.config = config
        self.problem = problem

    @abstractmethod
    def run_battle(self, fight_handler: FightHandler[_Instance, _Solution]) -> BattleWrapper.Result:
        """Calculates the next instance size that should be fought over"""
        raise NotImplementedError

    @classmethod
    def name(cls) -> str:
        """Name of the type of this battle wrapper."""
        return cls.__name__

    class Result(Subject):
        """Result of a single battle."""

        @property
        @abstractmethod
        def score(self) -> float:
            """The score achieved by the solver of this battle."""
            raise NotImplementedError

        @staticmethod
        @abstractmethod
        def format_score(score: float) -> str:
            """Formats a score nicely."""
            raise NotImplementedError

        def __str__(self) -> str:
            return self.format_score(self.score)

        @abstractmethod
        def display(self) -> str:
            """Nicely formats the object."""
            raise NotImplementedError
