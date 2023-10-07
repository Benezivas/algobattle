"""Tests for the Battle types."""
from enum import Enum
from itertools import chain, cycle
from types import EllipsisType
from typing import Iterable, TypeVar
from unittest import IsolatedAsyncioTestCase, main

from algobattle.battle import Battle, Fight, FightHandler, Iterated
from algobattle.match import BattleObserver, EmptyUi
from algobattle.program import Matchup, ProgramRunInfo, Team
from algobattle.util import Encodable, ExceptionInfo


T = TypeVar("T")


def always(val: T) -> "cycle[T]":
    """Shorthand for an iterator always yielding a single value."""
    return cycle([val])


class TestTeam(Team):
    """Team that doesn't rely on actual docker images."""

    def __init__(self, team_name: str) -> None:
        object.__setattr__(self, "name", team_name)


class Result(Enum):
    """Fight result types."""

    success = 1
    fail = 0
    generator_err = "generator error"
    solver_err = "solver error"


succ = Result.success
fail = Result.fail
gen_err = Result.generator_err
sol_err = Result.solver_err


class TestHandler(FightHandler):
    """Test fight handler that just repeats a predefined sequence of results."""

    def __init__(self, battle: Battle, results: Iterable[Result]) -> None:
        self.results = iter(results)
        self.battle = battle

    async def run(
        self,
        max_size: int,
        *,
        timeout_generator: float | None | EllipsisType = ...,
        space_generator: int | None | EllipsisType = ...,
        cpus_generator: int | EllipsisType = ...,
        timeout_solver: float | None | EllipsisType = ...,
        space_solver: int | None | EllipsisType = ...,
        cpus_solver: int | EllipsisType = ...,
        generator_battle_input: Encodable | None = None,
        solver_battle_input: Encodable | None = None,
        generator_battle_output: type[Encodable] | None = None,
        solver_battle_output: type[Encodable] | None = None,
    ) -> Fight:
        f = None
        match next(self.results):
            case Result.generator_err:
                f = Fight(
                    score=1,
                    max_size=max_size,
                    generator=ProgramRunInfo(error=ExceptionInfo.from_exception(RuntimeError())),
                    solver=ProgramRunInfo(),
                )
            case Result.solver_err:
                f = Fight(
                    score=1,
                    max_size=max_size,
                    generator=ProgramRunInfo(),
                    solver=ProgramRunInfo(error=ExceptionInfo.from_exception(RuntimeError())),
                )
            case r:
                f = Fight(score=r.value, max_size=max_size, generator=ProgramRunInfo(), solver=ProgramRunInfo())
        self.battle.fights.append(f)
        return f


class ConstantHandler(FightHandler):
    """Test fight handler that always succeeds."""

    def __init__(self, battle: Battle, size: int) -> None:
        self.size = size
        self.battle = battle

    async def run(
        self,
        max_size: int,
        *,
        timeout_generator: float | None | EllipsisType = ...,
        space_generator: int | None | EllipsisType = ...,
        cpus_generator: int | EllipsisType = ...,
        timeout_solver: float | None | EllipsisType = ...,
        space_solver: int | None | EllipsisType = ...,
        cpus_solver: int | EllipsisType = ...,
        generator_battle_input: Encodable | None = None,
        solver_battle_input: Encodable | None = None,
        generator_battle_output: type[Encodable] | None = None,
        solver_battle_output: type[Encodable] | None = None,
    ) -> Fight:
        f = Fight(
            score=float(max_size <= self.size), max_size=max_size, generator=ProgramRunInfo(), solver=ProgramRunInfo()
        )
        self.battle.fights.append(f)
        return f


class IteratedTests(IsolatedAsyncioTestCase):
    """Tests the Iterated type."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.config = Iterated.Config(rounds=1)
        cls.ui = BattleObserver(EmptyUi(), Matchup(TestTeam("Test"), TestTeam("Test")))

    async def _expect_size(self, size: int) -> Iterated:
        battle = Iterated()
        handler = ConstantHandler(battle, size)
        await battle.run_battle(handler, self.config, 1, self.ui)
        self.assertEqual(size, battle.score())
        return battle

    async def test_sizes(self) -> None:
        await self._expect_size(1)
        await self._expect_size(17)
        await self._expect_size(128)
        await self._expect_size(17_000)

    async def _expect_fights(
        self, results: Iterable[Result], sizes: list[int], *, score: int | None = None, total: bool = False
    ) -> Iterated:
        battle = Iterated()
        if not total:
            results = chain(results, always(fail))
        handler = TestHandler(battle, results)
        await battle.run_battle(handler, Iterated.Config(rounds=1, maximum_size=1000), 1, self.ui)
        fought_sizes = list(f.max_size for f in battle.fights)
        if not total:
            fought_sizes = fought_sizes[: len(sizes)]
        self.assertEqual(sizes, fought_sizes)
        if score is not None:
            self.assertEqual(battle.score(), score)
        return battle

    async def test_full_battle(self) -> None:
        await self._expect_fights(always(fail), [1])
        await self._expect_fights(
            always(succ),
            [1, 2, 6, 15, 31, 56, 92, 141, 205, 286, 386, 507, 651, 820, 1000],
            score=1000,
            total=True,
        )

    async def test_reset_max_size(self) -> None:
        await self._expect_fights([succ, succ, succ, fail], [1, 2, 6, 15, 7])

    async def test_rest_step_size(self) -> None:
        await self._expect_fights([succ, succ, succ, fail, succ], [1, 2, 6, 15, 7, 8])

    async def test_exit_before_cap_success(self) -> None:
        await self._expect_fights([succ, succ, fail, succ, succ, succ], [1, 2, 6, 3, 4, 5], score=5, total=True)

    async def test_exit_before_cap_fail(self) -> None:
        await self._expect_fights([succ, succ, fail, succ, succ, fail], [1, 2, 6, 3, 4, 5], score=4, total=True)

    async def test_exit_solver_fail(self) -> None:
        await self._expect_fights([succ, succ, succ, fail, fail], [1, 2, 6, 15, 7], score=6, total=True)

    async def test_exit_fail_fast(self) -> None:
        await self._expect_fights([succ, fail], [1, 2], score=1, total=True)

    async def test_exit_fail_immedietly(self) -> None:
        await self._expect_fights([fail], [1], score=0, total=True)

    async def test_exit_repeated_gen_fails(self) -> None:
        e = gen_err
        await self._expect_fights(
            [succ, succ, succ, e, e, e, e, e], [1, 2, 6, 15, 31, 56, 92, 141], score=1000, total=True
        )

    async def test_noexit_disconnected_gen_fails(self) -> None:
        e = gen_err
        await self._expect_fights(
            [succ, succ, succ, e, e, succ, e, e, e], [1, 2, 6, 15, 31, 56, 92, 141, 205], score=205
        )


if __name__ == "__main__":
    main()
