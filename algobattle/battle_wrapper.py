"""Base class for wrappers that execute a specific kind of battle.

The battle wrapper class is a base class for specific wrappers, which are
responsible for executing specific types of battle. They share the
characteristic that they are responsible for updating some match data during
their run, such that it contains the current state of the match.
"""
from __future__ import annotations
from dataclasses import dataclass, field
import logging
from abc import ABC, abstractmethod, abstractproperty
from typing import TYPE_CHECKING, Any, TypeVar
if TYPE_CHECKING:
    from algobattle.match import Match


logger = logging.getLogger('algobattle.battle_wrapper')


class BattleWrapper(ABC):
    """Base class for wrappers that execute a specific kind of battle.
    Its state contains information about the battle and its history."""

    #* using refs back to the parent match object is somewhat memory inefficient
    #* this could be changed by either heavily modifying __getattribute__ and __setattr__
    #* of the result classes or giving up the natural access syntax

    @dataclass
    class Result:
        _match: Match

        def __setattr__(self, name: str, value: Any) -> None:
            """Updates record in the RoundData object and notifies all obeservers
            subscribed to the associated Match object."""

            object.__setattr__(self, name, value)
            self._match.notify()
    
    def __init__(self, match: Match, problem: str, rounds: int = 5, **options: Any):
        """Builds a battle wrapper object with the given option values.
        Logs warnings if there were options provided that this wrapper doesn't use. 

        Parameters
        ----------
        match: Match
            The match object this wrapper will be used for.
        problem: str
            The problem this wrapper will be used for.
        rounds: int
            The number of rounds that will be executed.
        options: dict[str, Any]
            Dict containing option values.
        """
        self._match = match
        self.problem = problem
        self.rounds = rounds

        self.curr_round: int = 0
        self.pairs: dict[tuple[str, str], list[BattleWrapper.Result]] = {}
        self.error: str | None = None
        self.curr_pair: tuple[str, str] | None = None

        for pair in self._match.all_battle_pairs():
            self.pairs[pair] = []
            for _ in range(self.rounds):
                self.pairs[pair].append(type(self).Result(self._match))

        for arg, value in options.items():
            if arg not in vars(type(self)):
                logger.warning(f"Option '{arg}={value}' was provided, but is not used by {type(self)} type battles.")
    
    def __setattr__(self, name: str, value: Any) -> None:
        """Updates record in the MatchData object and notifies all obeservers
        subscribed to the associated Match object."""

        object.__setattr__(self, name, value)
        self._match.notify()

    @abstractmethod
    def wrapper(self, match: Match) -> None:
        """The main base method for a wrapper.

        A wrapper should update the match.match_data object during its run. The callback functionality
        around it is executed automatically.

        It is assumed that the match.generating_team and match.solving_team are
        set before calling a wrapper.

        Parameters
        ----------
        match: Match
            The Match object on which the battle wrapper is to be executed on.
        """
        raise NotImplementedError

    @abstractmethod
    def calculate_points(self, achievable_points: int) -> dict[str, float]:
        """Calculate the number of achieved points, given results.

        As awarding points completely depends on the type of battle that
        was fought, each wrapper should implement a method that determines
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

    def format_as_utf8(self) -> str:
        """Format the match_data for the battle wrapper as a UTF-8 string.

        The output should not exceed 80 characters, assuming the default
        of a battle of 5 rounds.

        Returns
        -------
        str
            A formatted string on the basis of the match_data.
        """
        formatted_output_string = ""

        formatted_output_string += f'Battles of type {type(self).__name__} are currently not compatible with the ui.'
        formatted_output_string += f'Here is a dump of the battle wrapper object anyway:\n{self}'

        return formatted_output_string
    