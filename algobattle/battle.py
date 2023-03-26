"""Module that handles the execution of each battle.

The battle class is a base class for specific type of battle that can be executed.
"""
from dataclasses import dataclass
from importlib.metadata import entry_points
import logging
from abc import abstractmethod, ABC
from typing import (
    Any,
    ClassVar,
    Literal,
    Mapping,
    TypeAlias,
    TypeVar,
    get_origin,
    get_type_hints,
)

from pydantic import BaseModel, Field, BaseConfig

from algobattle.docker_util import DockerError, Generator, Solver, GeneratorResult, SolverResult
from algobattle.ui import Observer, Subject
from algobattle.util import Encodable, Role, inherit_docs

logger = logging.getLogger("algobattle.battle")


_Config: TypeAlias = Any
T = TypeVar("T")


@dataclass
class CombinedResults:
    """The result of one execution of the generator and the solver with the generated instance."""

    score: float
    generator: GeneratorResult | DockerError
    solver: SolverResult | DockerError | None


class Battle(Subject, ABC):
    """Abstract Base class for classes that execute a specific kind of battle."""

    _battle_types: ClassVar[dict[str, type["Battle"]]] = {}

    scoring_team: ClassVar[Role] = "solver"

    class Config(BaseModel):
        """Object containing the config variables the battle types use."""

        @classmethod
        def as_argparse_args(cls) -> list[tuple[str, dict[str, Any]]]:
            """Constructs a list of argument names and `**kwargs` that can be passed to `ArgumentParser.add_argument()`."""
            arguments: list[tuple[str, dict[str, Any]]] = []
            resolved_annotations = get_type_hints(cls)
            for name, field in cls.__fields__.items():
                kwargs = field.field_info.extra
                kwargs["help"] = kwargs.get("help", "") + f" Default: {field.default}"
                if resolved_annotations[name] == bool and "action" not in kwargs and "const" not in kwargs:
                    kwargs["action"] = "store_const"
                    kwargs["const"] = not field.default
                elif get_origin(resolved_annotations[name]) == Literal and "choices" not in kwargs:
                    kwargs["choices"] = resolved_annotations[name].__args__

                arguments.append((field.name, kwargs))
            return arguments

        class Config(BaseConfig):
            """Pydandtic config."""

            validate_assignment = True

    @staticmethod
    def all() -> dict[str, type["Battle"]]:
        """Returns a list of all registered battle types."""
        for entrypoint in entry_points(group="algobattle.battle"):
            if entrypoint.name not in Battle._battle_types:
                battle: type[Battle] = entrypoint.load()
                Battle._battle_types[battle.name().lower()] = battle
        return Battle._battle_types

    def __init_subclass__(cls, notify_var_changes: bool = False) -> None:
        if cls.name() not in Battle._battle_types:
            Battle._battle_types[cls.name().lower()] = cls
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
        """Name of the type of this battle."""
        return cls.__name__

    @abstractmethod
    async def run_battle(self, generator: Generator, solver: Solver, config: _Config, min_size: int) -> None:
        """Calculates the next instance size that should be fought over."""
        raise NotImplementedError

    async def run_programs(
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
            gen_result = await generator.run(
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
            sol_result = await solver.run(
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

        score = gen_result.problem.calculate_score(
            solution=sol_result.solution, generator_solution=gen_result.solution, size=size
        )
        score = max(0, min(1, float(score)))
        logger.info(f"The solver achieved a score of {score}.")
        return CombinedResults(score, gen_result, sol_result)


class Iterated(Battle):
    """Class that executes an iterated battle."""

    def __init__(self, observer: Observer | None = None) -> None:
        self.running = False
        self.results = []
        super().__init__(observer)

    @inherit_docs
    class Config(Battle.Config):
        rounds: int = Field(default=5, help="Repeats the battle and averages the results.")
        iteration_cap: int = Field(default=50_000, help="Maximum instance size that will be tried.")
        exponent: int = Field(default=2, help="Determines how quickly the instance size grows.")
        approximation_ratio: float = Field(default=1, help="Approximation ratio that a solver needs to achieve to pass.")

    async def run_battle(self, generator: Generator, solver: Solver, config: Config, min_size: int) -> None:
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
        self.running = True
        for _ in range(config.rounds):
            base_increment = 0
            alive = True
            self.reached = 0
            self.cap = config.iteration_cap
            self.current = min_size
            while alive:
                result = await self.run_programs(generator, solver, self.current)
                score = result.score
                if score < config.approximation_ratio:
                    logger.info(f"Solver does not meet the required solution quality at instance size "
                                f"{self.current}. ({score}/{config.approximation_ratio})")
                    alive = False

                if not alive and base_increment > 1:
                    # The step size increase was too aggressive, take it back and reset the base_increment
                    logger.info(f"Setting the solution cap to {self.current}...")
                    self.cap = self.current
                    self.current -= base_increment ** config.exponent
                    base_increment = 0
                    alive = True
                elif self.current > self.reached and alive:
                    # We solved an instance of bigger size than before
                    self.reached = self.current

                if self.current + 1 > self.cap:
                    alive = False
                else:
                    base_increment += 1
                    self.current += base_increment ** config.exponent

                    if self.current >= self.cap:
                        # We have failed at this value of n already, reset the step size!
                        self.current -= base_increment ** config.exponent - 1
                        base_increment = 1
            self.results.append(self.reached)
        self.running = False

    @inherit_docs
    def score(self) -> float:
        results = self.results[::-1] if self.running else self.results
        return 0 if len(results) == 0 else sum(results) / len(results)

    @inherit_docs
    @staticmethod
    def format_score(score: float) -> str:
        return str(int(score))

    @inherit_docs
    def display(self) -> str:
        return f"current cap: {self.cap}\nsolved: {self.reached}\nattempting: {self.current}"


class Averaged(Battle):
    """Class that executes an averaged battle."""

    @inherit_docs
    class Config(Battle.Config):
        instance_size: int = Field(default=10, help="Instance size that will be fought at.")
        iterations: int = Field(default=10, help="Number of iterations in each round.")

    async def run_battle(self, generator: Generator, solver: Solver, config: Config, min_size: int) -> None:
        """Execute one averaged battle between a generating and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality.
        """
        if config.instance_size < min_size:
            raise ValueError(
                f"The problem specifies a minimum size of {min_size} but the chosen size is only {config.instance_size}!"
            )
        self.iterations = config.iterations
        self.scores: list[float] = []
        for i in range(config.iterations):
            self.curr_iter = i + 1
            result = await self.run_programs(generator, solver, config.instance_size)
            self.scores.append(result.score)

    @inherit_docs
    def score(self) -> float:
        if len(self.scores) == 0:
            return 0
        else:
            return sum(1 / x if x != 0 else 0 for x in self.scores) / len(self.scores)

    @inherit_docs
    @staticmethod
    def format_score(score: float) -> str:
        return format(score, ".0%")

    @inherit_docs
    def display(self) -> str:
        return (f"iteration: {self.curr_iter}/{self.iterations}\nscores: {self.scores}")
