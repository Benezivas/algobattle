"""Abstract base class for wrappers that execute a specific kind of battle.

The battle wrapper class is a base class for specific wrappers, which are
responsible for executing specific types of battle. They share the
characteristic that they are responsible for updating some match data during
their run, such that it contains the current state of the match.
"""
from dataclasses import dataclass
from importlib.metadata import entry_points
import logging
from abc import abstractmethod, ABC
from typing import Any, ClassVar, Mapping, TypeAlias
from algobattle.docker_util import DockerError, Generator, Solver, GeneratorResult, SolverResult
from algobattle.observer import Subject
from algobattle.util import CLIParsable, Encodable, Role

logger = logging.getLogger("algobattle.battle_wrapper")


_Config: TypeAlias = Any


@dataclass
class CombinedResults:
    """The result of one execution of the generator and the solver with the generated instance."""

    score: float
    generator: GeneratorResult | DockerError
    solver: SolverResult | DockerError | None


class BattleWrapper(Subject, ABC):
    """Abstract Base class for wrappers that execute a specific kind of battle."""

    _wrappers: ClassVar[dict[str, type["BattleWrapper"]]] = {}

    scoring_team: ClassVar[Role] = "solver"

    Config: ClassVar[type[CLIParsable]]
    """Object containing the config variables the wrapper will use."""

    @staticmethod
    def all() -> dict[str, type["BattleWrapper"]]:
        """Returns a list of all registered wrappers."""
        for entrypoint in entry_points(group="algobattle.wrappers"):
            if entrypoint.name not in BattleWrapper._wrappers:
                wrapper: type[BattleWrapper] = entrypoint.load()
                BattleWrapper._wrappers[wrapper.name().lower()] = wrapper
        return BattleWrapper._wrappers

    def __init_subclass__(cls, notify_var_changes: bool = False) -> None:
        if cls.name() not in BattleWrapper._wrappers:
            BattleWrapper._wrappers[cls.name().lower()] = cls
        return super().__init_subclass__(notify_var_changes)

    @abstractmethod
    def score(self) -> float:
        """The score achieved by the scored team during this battle."""
        raise NotImplementedError

    @staticmethod
    def format_score(score: float) -> str:
        """Formats a score nicely."""
        return f"{score:.2f}"

    @abstractmethod
    def display(self) -> str:
        """Nicely formats the object."""
        raise NotImplementedError

    @classmethod
    def name(cls) -> str:
        """Name of the type of this battle wrapper."""
        return cls.__name__

    @abstractmethod
    def run_battle(self, generator: Generator, solver: Solver, config: _Config, min_size: int) -> None:
        """Calculates the next instance size that should be fought over"""
        raise NotImplementedError

    def run_programs(
        self,
        generator: Generator,
        solver: Solver,
        size: int,
        *,
        timeout_generator: float | None = ...,
        space_generator: int | None = ...,
        cpus_generator: int = ...,
        timeout_solver: float | None = ...,
        space_solver: int | None = ...,
        cpus_solver: int = ...,
        generator_battle_input: Mapping[str, Encodable] = {},
        solver_battle_input: Mapping[str, Encodable] = {},
        generator_battle_output: Mapping[str, type[Encodable]] = {},
        solver_battle_output: Mapping[str, type[Encodable]] = {},
    ) -> CombinedResults:
        """Execute a single fight of a battle, running the generator and solver and handling any errors gracefully."""
        self.notify()
        try:
            gen_result = generator.run(
                size=size,
                timeout=timeout_generator,
                space=space_generator,
                cpus=cpus_generator,
                battle_input=generator_battle_input,
                battle_output=generator_battle_output,
            )
        except DockerError as e:
            return CombinedResults(score=1, generator=e, solver=None)

        try:
            sol_result = solver.run(
                gen_result.problem,
                size=size,
                timeout=timeout_solver,
                space=space_solver,
                cpus=cpus_solver,
                battle_input=solver_battle_input,
                battle_output=solver_battle_output,
            )
        except DockerError as e:
            return CombinedResults(score=0, generator=gen_result, solver=e)

        score = gen_result.problem.calculate_score(solution=sol_result.solution, generator_solution=gen_result.solution, size=size)
        score = max(0, min(1, float(score)))
        logger.info(f"Solver of group {solver.team_name} yields a valid solution with a score of {score}.")
        return CombinedResults(score, gen_result, sol_result)
