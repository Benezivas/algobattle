
# Battle

The `battle.py` module defines the `Battle` class and thus what each battle type can do to customize how it runs and
scores the programs. If you are implementing your own custom battle types, make sure they adhere to the api
specifications laid out here.


::: algobattle.battle.Battle
    options:
        members: [score, format_score, name, run_battle, BattleConfig, UiData, fight_results]

::: algobattle.battle.FightHandler
    options:
        members: [run]

::: algobattle.battle.Fight
