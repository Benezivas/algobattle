"""Abstract base class for wrappers that execute a specific kind of battle.

The battle wrapper class is a base class for specific wrappers, which are
responsible for executing specific types of battle. They share the
characteristic that they are responsible for updating some match data during
their run, such that it contains the current state of the match.
"""
from __future__ import annotations
import logging
from abc import abstractmethod, ABC
from typing import Callable
from importlib import import_module
from configparser import ConfigParser

from algobattle.fight_handler import FightHandler
from algobattle.team import Matchup

logger = logging.getLogger('algobattle.battle_wrapper')


class BattleWrapper(ABC):
    """Abstract Base class for wrappers that execute a specific kind of battle."""

    @staticmethod
    def initialize(wrapper_name: str, config: ConfigParser) -> BattleWrapper:
        """Try to import and initialize a Battle Wrapper from a given name.

        For this to work, a BattleWrapper module with the same name as the argument
        needs to be present in the algobattle/battle_wrappers folder.

        Parameters
        ----------
        wrapper : str
            Name of a battle wrapper module in algobattle/battle_wrappers.

        config : ConfigParser
            A ConfigParser object containing possible additional arguments for the battle_wrapper.

        Returns
        -------
        BattleWrapper
            A BattleWrapper object of the given wrapper_name.

        Raises
        ------
        ValueError
            If the wrapper does not exist in the battle_wrappers folder.
        """
        try:
            wrapper_module = import_module("algobattle.battle_wrappers." + wrapper_name)
            return getattr(wrapper_module, wrapper_name.capitalize())(config)
        except ImportError as e:
            logger.critical(f"Importing a wrapper from the given path failed with the following exception: {e}")
            raise ValueError from e

    @abstractmethod
    def run_round(self, fight_handler: FightHandler, matchup: Matchup) -> BattleResult:
        """Execute a full round of fights between two teams configured in the fight_handler.

        During execution, the concrete BattleWrapper should update the round_data dict
        to which Observers can subscribe in order to react to new intermediate results.

        Parameters
        ----------
        fight_handler: FightHandler
            A FightHandler object that manages solving and generating teams as well
            single fights between them.
        """
        raise NotImplementedError


class BattleResult:
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
