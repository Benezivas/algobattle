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
from pathlib import Path
from typing import Generator, Literal, Type

from algobattle.problem import Instance, Solution
from algobattle.observer import Subject
from algobattle.util import CLIParsable

logger = logging.getLogger('algobattle.battle_wrapper')


@dataclass
class _RunData:
    time: float
    status: Literal["success", "failure", "timeout"]


@dataclass
class GeneratorData(_RunData):
    """Detailed info about the generator's execution."""
    instance: Instance


@dataclass
class SolverData(_RunData):
    """Detailed info about the solver's execution."""
    solution: Solution[Instance]


@dataclass
class FightResult:
    """The result of a single fight."""
    score: float
    generator: GeneratorData
    solver: SolverData


class FightSpec:
    """Data defining the execution of a single fight."""

    def __init__(self, size: int = ..., *, gen_timeout: float | None = ..., gen_space: int | None = ..., gen_cpus: int | None = ..., 
        sol_timeout: float | None = ..., sol_space: int | None = ..., sol_cpus: int | None = ...) -> None:
        self.size = size
        self.gen_timeout = gen_timeout
        self.gen_space = gen_space
        self.gen_cpus = gen_cpus
        self.sol_timeout = sol_timeout
        self.sol_space = sol_space
        self.sol_cpus = sol_cpus
        super().__init__()


class BattleWrapper(ABC):
    """Abstract Base class for wrappers that execute a specific kind of battle."""

    @dataclass
    class Config(CLIParsable):
        """Object containing the config variables the wrapper will use."""

        pass

    _wrappers: dict[str, Type[BattleWrapper]] = {}

    @staticmethod
    def all() -> dict[str, Type[BattleWrapper]]:
        """Returns a list of all registered wrappers."""
        for entrypoint in entry_points(group="algobattle.wrappers"):
            if entrypoint.name not in BattleWrapper._wrappers:
                wrapper: Type[BattleWrapper] = entrypoint.load()
                BattleWrapper._wrappers[wrapper.name()] = wrapper
        return BattleWrapper._wrappers

    def __init_subclass__(cls) -> None:
        if cls.name() not in BattleWrapper._wrappers:
            BattleWrapper._wrappers[cls.name()] = cls
        return super().__init_subclass__()

    def __init__(self, config: BattleWrapper.Config) -> None:
        super().__init__()
        self.config = config

    @abstractmethod
    def generate_instance_sizes(self, minimum_size: int) -> Generator[FightSpec, FightResult, BattleWrapper.Result]:
        """Calculates the next instance size that should be fought over"""
        raise NotImplementedError

    def generator_input(self, path: Path):
        """Create additional input that will be available to the generator."""
        return

    def solver_input(self, path: Path):
        """Create additional input that will be given to the solver."""
        return

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
