"""Module for the abstract base class for battle styles."""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import Any, Generator, Generic, Type, TypeVar
from inspect import isabstract, signature, getdoc
from algobattle.fight import Fight

from algobattle.problem import Problem
from algobattle.team import Team, BattleMatchups, Matchup
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
            BattleStyle._battle_styles[cls.__name__.lower()] = cls

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
    def get_arg_spec(cls) -> dict[str, dict[str, Any]]:
        """Gets the info needed to make a cli interface for a battle style.

        The argparse type argument will only be set if the type is available in the builtin or global namespace.

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
    def run(self, matchup: Matchup) -> Generator[Result, None, None]:
        """The main base method for a battle style.

        A battle style should update the match.match_data object during its run. The callback functionality
        around it is executed automatically.

        It is assumed that the match.generating_team and match.solving_team are
        set before calling a battle style.

        Parameters
        ----------
        match: Match
            The Match object on which the battle battle style is to be executed on.
        """
        raise NotImplementedError

    class Result:
        """The result of a battle."""

        pass

    Res = TypeVar("Res", covariant=True, bound=Result)

    class MatchResult(dict[Matchup, list[Res]], ABC):
        """The result of a whole match.

        Generally a mapping of matchups to a list of Results, one per round.
        """

        def __init__(self, matchups: BattleMatchups, rounds: int) -> None:
            self.rounds = rounds
            for matchup in matchups:
                self[matchup] = []

        def format(self) -> str:
            """Format the match_data for the battle battle style as a UTF-8 string.

            The output should not exceed 80 characters, assuming the default
            of a battle of 5 rounds.

            Returns
            -------
            str
                A formatted string on the basis of the match_data.
            """
            formatted_output_string = "Battles of this type are currently not compatible with the ui.\n"
            formatted_output_string += "Here is a dump of the result objects anyway:\n"
            formatted_output_string += "\n".join(f"{matchup}: {res}" for (matchup, res) in self.items())

            return formatted_output_string

        def __str__(self) -> str:
            return self.format()

        @abstractmethod
        def calculate_points(self, achievable_points: int) -> dict[Team, float]:
            """Calculate the number of achieved points, given results.

            As awarding points completely depends on the type of battle that
            was fought, each battle style should implement a method that determines
            how to split up the achievable points among all teams.

            Parameters
            ----------
            achievable_points : int
                Number of achievable points.

            Returns
            -------
            dict
                A mapping between team names and their achieved points.
                The format is {team_name: points [...]} for each
                team for which there is an entry in match_data and points is a
                float value. Returns an empty dict if no battle was fought.
            """
            raise NotImplementedError
