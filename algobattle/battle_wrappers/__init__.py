from __future__ import annotations
from importlib import import_module
from pathlib import Path
from typing import Type
import logging

from algobattle.battle_wrapper import BattleWrapper

logger = logging.getLogger('algobattle.battle_wrapper')

for path in Path(__file__).resolve().parent.iterdir():
    if not path.name[:2] == ("__") and path.name[-3:] == ".py":
        import_module(f".{path.name[:-3]}", "algobattle.battle_wrappers")

battle_wrappers = BattleWrapper._battle_wrappers
def get_battle_wrapper(battle_type: str) -> Type[BattleWrapper]:
    """Get the battle wrapper for the given type of battle.

    Parameters
    ----------
    battle_type : str
        Name of the type of battle.

    Returns
    -------
    Type[BattleWrapper]
        BattleWrapper class.

    Raises
    ------
    ValueError
        If there is no battle wrapper with the specified name.
    """
    if battle_type.lower() in BattleWrapper._battle_wrappers.keys():
        return BattleWrapper._battle_wrappers[battle_type]
    else:
        logger.error(f'Unrecognized battle_type given: "{battle_type}"')
        raise ValueError