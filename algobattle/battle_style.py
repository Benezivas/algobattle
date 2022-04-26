"""Module for the abstract base class for battle styles."""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import Any, Generator, Generic, Type, TypeVar
from inspect import isabstract, signature, getdoc
from algobattle.fight import Fight

from algobattle.problem import Problem
from algobattle.team import Matchup
from algobattle.util import parse_doc_for_param

logger = logging.getLogger("algobattle.battle_type")

Instance = TypeVar("Instance")
Solution = TypeVar("Solution")


class BattleStyle(ABC, Generic[Instance, Solution]):
    """Base class for battle styles that define how a battle can be structured.

    All battle styles should inherit from this class explicitly so they are integrated into the match structure properly.
    A BattleStyle is responsible for deciding the sequence of fights that are executed and processing their results.
    It also handles further processing of match results through its associated types.
    """

    _battle_styles: dict[str, Type[BattleStyle]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if not isabstract(cls):
            BattleStyle._battle_styles[cls.name] = cls

    def __init__(self, problem: Problem[Instance, Solution], fight: Fight, **kwargs: dict[str, Any]):
        """Builds a battle style object with the given option values.

        Parameters
        ----------
        problem: Problem
            The problem this battle will be fought over.
        fight: Fight
            Fight that will be executed.
        kwargs: dict[str, Any]
            Further options that each specific battle style can use.
        """
        self.problem = problem
        self.fight = fight

    @classmethod
    @property
    def name(cls) -> str:
        """The normalized name of this battle style."""
        return cls.__name__.lower()

    @classmethod
    def get_arg_spec(cls) -> dict[str, dict[str, Any]]:
        """Gets the info needed to make a cli interface for a battle style.

        The argparse 'type' argument will only be set if the type is available in the builtin or global namespace.

        Returns
        -------
        dict[str, dict[str, Any]]
            A mapping of the names of a cli argument and the **kwargs for it.
        """
        base_params = [param for param in signature(BattleStyle).parameters]
        out = {}
        doc = getdoc(cls.__init__)
        for param in signature(cls).parameters.values():
            if param.kind != param.VAR_POSITIONAL and param.kind != param.VAR_KEYWORD and param.name not in base_params:
                kwargs = {}

                if param.annotation != param.empty:
                    if param.annotation in globals():
                        kwargs["type"] = globals()[param.annotation]
                    elif param.annotation in __builtins__:
                        kwargs["type"] = __builtins__[param.annotation]

                if param.default != param.empty:
                    kwargs["default"] = param.default
                    help_default = f" Default: {param.default}"
                else:
                    help_default = ""

                if doc is not None:
                    try:
                        kwargs["help"] = parse_doc_for_param(doc, param.name) + help_default
                    except ValueError:
                        pass

                out[param.name] = kwargs
        return out

    @abstractmethod
    def run(self, matchup: Matchup) -> Result:
        """Executes a battle between the given matchup.

        Parameters
        ----------
        matchup: Matchup
            The matchup of teams that participate in this battle.

        Returns
        -------
        Generator[Result, None, None]
            A generator of intermediate results, the last yielded is the final result.
        """
        raise NotImplementedError

    class Result(ABC):
        """The result of a battle."""

        @property
        @abstractmethod
        def score(self) -> float:
            """The score of this result."""
            raise NotImplementedError

        def __str__(self) -> str:
            return self.fmt_score(self.score)

        @staticmethod
        @abstractmethod
        def fmt_score(score: float) -> str:
            """Formats a given score nicely."""
            raise NotImplementedError
