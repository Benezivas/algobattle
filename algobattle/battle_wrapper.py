"""Base class for wrappers that execute a specific kind of battle.

The battle wrapper class is a base class for specific wrappers, which are
responsible for executing specific types of battle. They share the
characteristic that they are responsible for updating some match data during
their run, such that it contains the current state of the match.
"""
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger('algobattle.battle_wrapper')


class BattleWrapper(ABC):
    """Base class for wrappers that execute a specific kind of battle."""

    @abstractmethod
    def wrapper(self, match, options: dict) -> None:
        """The main base method for a wrapper.

        In order to manage the execution of a match, the wrapper needs the match object and possibly
        some options that are specific to the individual battle wrapper.

        A wrapper should update the match.match_data dict during its run by calling
        the match.update_match_data method. This ensures that the callback
        functionality around the match_data dict is properly executed.

        It is assumed that the match.generating_team and match.solving_team are
        set before calling a wrapper.

        Parameters
        ----------
        match: Match
            The Match object on which the battle wrapper is to be executed on.
        options: dict
            Additional options for the wrapper.
        """
        raise NotImplementedError
