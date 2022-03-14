from __future__ import annotations
from importlib import import_module
from pathlib import Path
from typing import Type
import logging

from algobattle.battle_style import BattleStyle

logger = logging.getLogger('algobattle.battle_styles')

for path in Path(__file__).resolve().parent.iterdir():
    if not path.name[:2] == ("__") and path.name[-3:] == ".py":
        import_module(f".{path.name[:-3]}", "algobattle.battle_styles")

battle_styles = BattleStyle._battle_styles


def get_battle_style(battle_type: str) -> Type[BattleStyle]:
    """Get the battle style for the given type of battle.

    Parameters
    ----------
    battle_type : str
        Name of the type of battle.

    Returns
    -------
    Type[BattleStyle]
        BattleStyle subclass.

    Raises
    ------
    ValueError
        If there is no battle style with the specified name.
    """
    if battle_type.lower() in BattleStyle._battle_styles.keys():
        return BattleStyle._battle_styles[battle_type]
    else:
        logger.error(f'Unrecognized battle_type given: "{battle_type}"')
        raise ValueError
