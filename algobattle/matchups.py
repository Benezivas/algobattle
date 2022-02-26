from __future__ import annotations
from dataclasses import dataclass
from typing import Iterator
from itertools import permutations

from algobattle.team import Team

@dataclass(frozen=True)
class Matchup:
    generator: Team
    solver: Team

    def __iter__(self) -> Iterator[Team]:
        yield self.generator
        yield self.solver


class BattleMatchups:
    
    def __init__(self, teams: list[Team]) -> None:
        self.teams = teams
        if len(self.teams) == 1:
            self._list = [Matchup(self.teams[0], self.teams[0])]
        else:
            self._list = [Matchup(*x) for x in permutations(self.teams, 2)]
    
    def __iter__(self) -> Iterator[Matchup]:
        return iter(self._list)
    
    def __getitem__(self, i: int) -> Matchup:
        return self._list[i]
