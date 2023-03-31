"""Module that handles the execution of each battle.

The battle class is a base class for specific type of battle that can be executed.
"""
from dataclasses import dataclass, field
from importlib.metadata import entry_points
import logging
from abc import abstractmethod, ABC
from typing import (
    Any,
    ClassVar,
    Literal,
    Mapping,
    Protocol,
    TypeAlias,
    TypeVar,
    get_origin,
    get_type_hints,
    overload,
)

from pydantic import BaseModel, Field, BaseConfig

from algobattle.docker_util import ProgramDisplayData, ProgramError, Generator, ProgramResult, ProgramUiProxy, Solver, GeneratorResult, SolverResult
from algobattle.util import Encodable, Role, inherit_docs

logger = logging.getLogger("algobattle.battle")


_Config: TypeAlias = Any
T = TypeVar("T")


@dataclass
class FightResult:
    """The result of one execution of the generator and the solver with the generated instance."""

    score: float
    generator: GeneratorResult
    solver: SolverResult | None


# We need this to be here to prevent an import cycle between match.py and battle.py
class BattleUiProxy(Protocol):
    """Provides an interface for :cls:`Battle`s to update the Ui."""

    generator: ProgramUiProxy
    solver: ProgramUiProxy

    @abstractmethod
    def update_fights(self) -> None:
        """Notifies the Ui to update the display of fight results for this battle."""

    @abstractmethod
    def update_data(self, data: "Battle.UiData") -> None:
        """Passes new custom display data to the Ui."""

    @overload
    @abstractmethod
    def update_curr_fight(self, role: Literal["generator"], data: ProgramDisplayData | GeneratorResult | None) -> None:
        ...

    @overload
    @abstractmethod
    def update_curr_fight(self, role: Literal["solver"], data: ProgramDisplayData | SolverResult | None) -> None:
        ...

    @overload
    @abstractmethod
    def update_curr_fight(self, role: None = None, data: None = None) -> None:
        ...

    @abstractmethod
    def update_curr_fight(
        self,
        role: Role | None = None,
        data: ProgramDisplayData | ProgramResult | None = None,
    ) -> None:
        """Updates the ui with info about the current fight.
        
        `data` is either the starting time of the 
        """


@dataclass
class FightUiData:
    """Holds display data about the currently executing fight."""

    generator:  ProgramDisplayData | GeneratorResult | None = None
    solver:  ProgramDisplayData | SolverResult | None = None


@dataclass
class Battle(ABC):
    """Abstract Base class for classes that execute a specific kind of battle."""

    ui: BattleUiProxy
    fight_results: list[FightResult] = field(default_factory=list)

    scoring_team: ClassVar[Role] = "solver"
    _battle_types: ClassVar[dict[str, type["Battle"]]] = {}

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

    class UiData(BaseModel):
        """Object containing custom diplay data."""

    @staticmethod
    def all() -> dict[str, type["Battle"]]:
        """Returns a list of all registered battle types."""
        for entrypoint in entry_points(group="algobattle.battle"):
            if entrypoint.name not in Battle._battle_types:
                battle: type[Battle] = entrypoint.load()
                Battle._battle_types[battle.name().lower()] = battle
        return Battle._battle_types

    def __init_subclass__(cls) -> None:
        if cls.name() not in Battle._battle_types:
            Battle._battle_types[cls.name().lower()] = cls
        return super().__init_subclass__()

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

    async def run_fight(
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
    ) -> FightResult:
        """Execute a single fight of a battle, running the generator and solver and handling any errors gracefully."""
        gen_result = await generator.run(
            size=size,
            timeout=timeout_generator,
            space=space_generator,
            cpus=cpus_generator,
            battle_input=generator_battle_input,
            battle_output=generator_battle_output,
            ui=self.ui.generator,
        )
        self.ui.update_curr_fight("generator", gen_result)
        if isinstance(gen_result.result, ProgramError):
            return FightResult(score=1, generator=gen_result, solver=None)

        sol_result = await solver.run(
            gen_result.result.problem,
            size=size,
            timeout=timeout_solver,
            space=space_solver,
            cpus=cpus_solver,
            battle_input=solver_battle_input,
            battle_output=solver_battle_output,
            ui=self.ui.solver,
        )
        self.ui.update_curr_fight("solver", sol_result)
        if isinstance(sol_result.result, ProgramError):
            return FightResult(score=0, generator=gen_result, solver=sol_result)

        score = gen_result.result.problem.calculate_score(
            solution=sol_result.result, generator_solution=gen_result.result.solution, size=size
        )
        score = max(0, min(1, float(score)))
        logger.info(f"The solver achieved a score of {score}.")
        res = FightResult(score, gen_result, sol_result)
        self.fight_results.append(res)
        self.ui.update_fights()
        return res


@dataclass
class Iterated(Battle):
    """Class that executes an iterated battle."""

    results: list[int] = field(default_factory=list)

    @inherit_docs
    class Config(Battle.Config):
        rounds: int = Field(default=5, help="Repeats the battle and averages the results.")
        iteration_cap: int = Field(default=50_000, help="Maximum instance size that will be tried.")
        exponent: int = Field(default=2, help="Determines how quickly the instance size grows.")
        approximation_ratio: float = Field(default=1, help="Approximation ratio that a solver needs to achieve to pass.")

    @inherit_docs
    class UiData(Battle.UiData):
        reached: list[int]
        cap: int

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
        results = []
        for _ in range(config.rounds):
            base_increment = 0
            alive = True
            reached = 0
            cap = config.iteration_cap
            current = min_size
            while alive:
                self.ui.update_data(self.UiData(reached=results + [reached], cap=cap))
                result = await self.run_fight(generator, solver, current)
                score = result.score
                if score < config.approximation_ratio:
                    logger.info(f"Solver does not meet the required solution quality at instance size "
                                f"{current}. ({score}/{config.approximation_ratio})")
                    alive = False

                if not alive and base_increment > 1:
                    # The step size increase was too aggressive, take it back and reset the base_increment
                    logger.info(f"Setting the solution cap to {current}...")
                    cap = current
                    current -= base_increment ** config.exponent
                    base_increment = 0
                    alive = True
                elif current > reached and alive:
                    # We solved an instance of bigger size than before
                    reached = current

                if current + 1 > cap:
                    alive = False
                else:
                    base_increment += 1
                    current += base_increment ** config.exponent

                    if current >= cap:
                        # We have failed at this value of n already, reset the step size!
                        current -= base_increment ** config.exponent - 1
                        base_increment = 1
            results.append(reached)

    @inherit_docs
    def score(self) -> float:
        return 0 if len(self.results) == 0 else sum(self.results) / len(self.results)

    @inherit_docs
    @staticmethod
    def format_score(score: float) -> str:
        return str(int(score))

    @inherit_docs
    def display(self) -> str:
        return ""


@dataclass
class Averaged(Battle):
    """Class that executes an averaged battle."""

    @inherit_docs
    class Config(Battle.Config):
        instance_size: int = Field(default=10, help="Instance size that will be fought at.")
        iterations: int = Field(default=10, help="Number of iterations in each round.")

    @inherit_docs
    class UiData(Battle.UiData):
        round: int

    async def run_battle(self, generator: Generator, solver: Solver, config: Config, min_size: int) -> None:
        """Execute one averaged battle between a generating and a solving team.

        Execute several fights between two teams on a fixed instance size
        and determine the average solution quality.
        """
        if config.instance_size < min_size:
            raise ValueError(
                f"The problem specifies a minimum size of {min_size} but the chosen size is only {config.instance_size}!"
            )
        for i in range(config.iterations):
            self.ui.update_data(self.UiData(round=i+1))
            await self.run_fight(generator, solver, config.instance_size)

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

    @inherit_docs
    def display(self) -> str:
        return ""
