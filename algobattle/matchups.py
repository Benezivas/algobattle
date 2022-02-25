from __future__ import annotations
from dataclasses import dataclass
from typing import Iterator
from itertools import permutations

from algobattle.team import Team

@dataclass(frozen=True)
class Matchup:
    generator: Team
    solver: Team

class BattleMatchups:
    
    def __init__(self, teams: list[Team]) -> None:
        self.teams = teams
    
    def __iter__(self) -> Iterator:
        if len(self.teams) == 1:
            return iter((self.teams[0], self.teams[0]))
        else:
            return permutations(self.teams, 2)
