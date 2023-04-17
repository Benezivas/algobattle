"""Module that handles the execution of each battle.

The battle class is a base class for specific type of battle that can be executed.
"""
from dataclasses import dataclass
from importlib.metadata import entry_points
from abc import abstractmethod
from typing import (
    Any,
    ClassVar,
    Literal,
    Protocol,
    TypeAlias,
    TypeVar,
    overload,
)

from pydantic import Field

from algobattle.docker_util import (
    Generator,
    ProgramRunInfo,
    ProgramUiProxy,
    Solver,
)
from algobattle.util import Encodable, Role, TimerInfo, inherit_docs, BaseModel


_Config: TypeAlias = Any
T = TypeVar("T")


class Fight(BaseModel):
    """The result of one execution of the generator and the solver with the generated instance."""

    score: float
    size: int
    generator: ProgramRunInfo
    solver: ProgramRunInfo | None


class FightUiProxy(Protocol):
    """Provides an interface for :cls:`Fight` to update the Ui."""

    generator: ProgramUiProxy
    solver: ProgramUiProxy

    def start(self, size: int) -> None:
        """Informs the Ui of a newly started fight."""

    @overload
    @abstractmethod
    def update(self, role: Literal["generator", "solver"], data: ProgramRunInfo) -> None:
        ...

    @overload
    @abstractmethod
    def update(self, role: None = None, data: None = None) -> None:
        ...

    @abstractmethod
    def update(
        self,
        role: Role | None = None,
        data: ProgramRunInfo | None = None,
    ) -> None:
        """Updates the ui with info about the current fight.

        `data` is either the starting time of the
        """


@dataclass
class FightHandler:
    """Helper class to run fights of a given matchup."""

    _generator: Generator
    _solver: Solver
    _battle: "Battle"
    _ui: "BattleUiProxy"

    def _saved(self, fight: Fight) -> Fight:
        self._battle.fight_results.append(fight)
        self._ui.update_fights()
        return fight

    async def run(
        self,
        size: int,
        *,
        timeout_generator: float | None = ...,
        space_generator: int | None = ...,
        cpus_generator: int = ...,
        timeout_solver: float | None = ...,
        space_solver: int | None = ...,
        cpus_solver: int = ...,
        generator_battle_input: Encodable | None = None,
        solver_battle_input: Encodable | None = None,
        generator_battle_output: type[Encodable] | None = None,
        solver_battle_output: type[Encodable] | None = None,
    ) -> Fight:
        """Execute a single fight of a battle between the given programs."""
        ui = self._ui.fight_ui
        ui.start(size)
        gen_result = await self._generator.run(
            size=size,
            timeout=timeout_generator,
            space=space_generator,
            cpus=cpus_generator,
            battle_input=generator_battle_input,
            battle_output=generator_battle_output,
            ui=ui.generator,
        )
        ui.update("generator", gen_result.info)
        if gen_result.instance is None:
            return self._saved(Fight(score=1, size=size, generator=gen_result.info, solver=None))

        sol_result = await self._solver.run(
            gen_result.instance,
            size=size,
            timeout=timeout_solver,
            space=space_solver,
            cpus=cpus_solver,
            battle_input=solver_battle_input,
            battle_output=solver_battle_output,
            ui=ui.solver,
        )
        ui.update("solver", sol_result.info)
        if sol_result.solution is None:
            return self._saved(Fight(score=0, size=size, generator=gen_result.info, solver=sol_result.info))

        score = gen_result.instance.calculate_score(
            solution=sol_result.solution, generator_solution=gen_result.solution, size=size
        )
        score = max(0, min(1, float(score)))
        return self._saved(Fight(score=score, size=size, generator=gen_result.info, solver=sol_result.info))


@dataclass
class FightUiData:
    """Holds display data about the currently executing fight."""

    size: int
    generator: TimerInfo | float | ProgramRunInfo | None = None
    solver: TimerInfo | float | ProgramRunInfo | None = None


# We need this to be here to prevent an import cycle between match.py and battle.py
class BattleUiProxy(Protocol):
    """Provides an interface for :cls:`Battle`s to update the Ui."""

    fight_ui: FightUiProxy

    @abstractmethod
    def update_data(self, data: "Battle.UiData") -> None:
        """Passes new custom display data to the Ui."""

    @abstractmethod
    def update_fights(self) -> None:
        """Notifies the Ui to update the display of fight results for this battle."""


class Battle(BaseModel):
    """Abstract Base class for classes that execute a specific kind of battle."""

    fight_results: list[Fight] = Field(default_factory=list)
    run_exception: str | None = None

    _battle_types: ClassVar[dict[str, type["Battle"]]] = {}

    class BattleConfig(BaseModel):
        """Object containing the config variables the battle types use."""

    class UiData(BaseModel):
        """Object containing custom diplay data."""

    @staticmethod
    def all() -> dict[str, type["Battle"]]:
        """Returns a list of all registered battle types."""
        for entrypoint in entry_points(group="algobattle.battle"):
            if entrypoint.name not in Battle._battle_types:
                battle: type[Battle] = entrypoint.load()
                Battle._battle_types[battle.name()] = battle
        return Battle._battle_types

    def __init_subclass__(cls) -> None:
        if cls.name() not in Battle._battle_types:
            Battle._battle_types[cls.name()] = cls
        return super().__init_subclass__()

    @abstractmethod
    def score(self) -> float:
        """The score achieved by the scored team during this battle."""
        raise NotImplementedError

    @staticmethod
    def format_score(score: float) -> str:
        """Formats a score nicely."""
        return f"{score:.2f}"

    @classmethod
    def name(cls) -> str:
        """Name of the type of this battle."""
        return cls.__name__

    @abstractmethod
    async def run_battle(self, fight: FightHandler, config: BattleConfig, min_size: int, ui: BattleUiProxy) -> None:
        """Calculates the next instance size that should be fought over."""
        raise NotImplementedError


class Iterated(Battle):
    """Class that executes an iterated battle."""

    results: list[int] = Field(default_factory=list)

    @inherit_docs
    class BattleConfig(Battle.BattleConfig):
        rounds: int = Field(default=5, help="Repeats the battle and averages the results.")
        iteration_cap: int = Field(default=50_000, help="Maximum instance size that will be tried.")
        exponent: int = Field(default=2, help="Determines how quickly the instance size grows.")
        approximation_ratio: float = Field(
            default=1, help="Approximation ratio that a solver needs to achieve to pass."
        )

    @inherit_docs
    class UiData(Battle.UiData):
        reached: list[int]
        cap: int

    async def run_battle(self, fight: FightHandler, config: _Config, min_size: int, ui: BattleUiProxy) -> None:
        """Execute one iterative battle between a generating and a solving team.

        Incrementally try to search for the highest n for which the solver is
        still able to solve instances.  The base increment value is multiplied
        with the power of iterations since the last unsolvable instance to the
        given exponent.
        Only once the solver fails after the multiplier is reset, it counts as
        failed. Since this would heavily favour probabilistic algorithms (That
        may have only failed by chance and are able to solve a certain instance
        size on a second try), we cap the maximum solution size by the last
        value that an algorithm has failed on.

        The battle automatically ends once the iteration cap is reached with
        the solver being declared the winner.

        During execution, this function updates the self.round_data dict,
        which automatically notifies all observers subscribed to this object.s
        """
        for _ in range(config.rounds):
            base_increment = 0
            alive = True
            reached = 0
            cap = config.iteration_cap
            current = min_size
            while alive:
                ui.update_data(self.UiData(reached=self.results + [reached], cap=cap))
                result = await fight.run(current)
                score = result.score
                if score < config.approximation_ratio:
                    alive = False

                if not alive and base_increment > 1:
                    # The step size increase was too aggressive, take it back and reset the base_increment
                    cap = current
                    current -= base_increment**config.exponent
                    base_increment = 0
                    alive = True
                elif current > reached and alive:
                    # We solved an instance of bigger size than before
                    reached = current

                if current + 1 > cap:
                    alive = False
                else:
                    base_increment += 1
                    current += base_increment**config.exponent

                    if current >= cap:
                        # We have failed at this value of n already, reset the step size!
                        current -= base_increment**config.exponent - 1
                        base_increment = 1
            self.results.append(reached)

    @inherit_docs
    def score(self) -> float:
        return 0 if len(self.results) == 0 else sum(self.results) / len(self.results)

    @inherit_docs
    @staticmethod
    def format_score(score: float) -> str:
        return str(int(score))


class Averaged(Battle):
    """Class that executes an averaged battle."""

    @inherit_docs
    class BattleConfig(Battle.BattleConfig):
        instance_size: int = Field(default=10, help="Instance size that will be fought at.")
        iterations: int = Field(default=10, help="Number of iterations in each round.")

    @inherit_docs
    class UiData(Battle.UiData):
        round: int

    async def run_battle(self, fight: FightHandler, config: _Config, min_size: int, ui: BattleUiProxy) -> None:
        """Execute one averaged battle between a generating and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality.
        """
        if config.instance_size < min_size:
            raise ValueError(
                f"The problem specifies a minimum size of {min_size} "
                "but the chosen size is only {config.instance_size}!"
            )
        for i in range(config.iterations):
            ui.update_data(self.UiData(round=i + 1))
            await fight.run(config.instance_size)

    @inherit_docs
    def score(self) -> float:
        if len(self.fight_results) == 0:
            return 0
        else:
            return sum(f.score for f in self.fight_results) / len(self.fight_results)

    @inherit_docs
    @staticmethod
    def format_score(score: float) -> str:
        return format(score, ".0%")
