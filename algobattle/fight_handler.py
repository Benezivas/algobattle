"""Class managing the execution of generators and solvers."""
from dataclasses import dataclass
import logging
from typing import Generic, Mapping, TypeVar

from algobattle.docker_util import DockerError, ExecutionError
from algobattle.observer import Observer, Subject
from algobattle.team import Matchup
from algobattle.problem import Problem
from algobattle.util import Encodable, TempDir, decode, encode

logger = logging.getLogger("algobattle.fight_handler")


# * in principle we could do a lot better typing in this module
# * but really it doesn't matter since there is no realistic case where different problems and solutions can sensibly be mixed
# * there also is the issue that TypeVars aren't subscriptable, which makes any attempt at this rather futile
# * since the most common errors (using a problem and solution type that don't match) won't be preventable


T = TypeVar("T", Problem, Problem.Solution)


@dataclass
class Result(Generic[T]):
    """Result of a single generator or solver execution."""

    time: float
    data: T
    battle_data: dict[str, Encodable]


class FightError(Exception):
    """Raised when a team's program doesn't generate valid output."""

    def __init__(self, runtime: float | None = None, *args: object) -> None:
        self.runtime = runtime
        super().__init__(*args)


class EncodingError(FightError):
    """Indicates that some data structured couldn't be encoded or decoded properly."""

    pass


@dataclass
class FightResult:
    """The result of a single fight."""

    score: float
    generator: Result[Problem] | FightError
    solver: Result[Problem.Solution] | FightError | None


@dataclass(kw_only=True)
class FightHandler(Subject):
    """Class managing the execution of generators and solvers."""

    problem: type[Problem]
    matchup: Matchup
    observer: Observer | None = None
    timeout_generator: float | None = None
    timeout_solver: float | None = None
    space_generator: int | None = None
    space_solver: int | None = None
    cpus: int = 1

    def fight(
        self,
        size: int,
        timeout_generator: float | None = ...,
        space_genrator: int | None = ...,
        timeout_solver: float | None = ...,
        space_solver: int | None = ...,
        cpus: int = ...,
        generator_battle_data: Mapping[str, Encodable] = {},
        solver_battle_data: Mapping[str, Encodable] = {},
        generator_battle_spec: Mapping[str, type[Encodable]] | None = None,
        solver_battle_spec: Mapping[str, type[Encodable]] | None = None,
    ) -> FightResult:
        """Execute a single fight of a battle, running the generator and solver and handling any errors gracefully."""
        self.notify()
        try:
            gen_result = self.generate(
                size=size, timeout=timeout_generator, space=space_genrator, cpus=cpus, battle_data=generator_battle_data, output_spec=generator_battle_spec
            )
        except FightError as e:
            return FightResult(score=1, generator=e, solver=None)

        try:
            sol_result = self.solve(
                gen_result.data, size=size, timeout=timeout_solver, space=space_solver, cpus=cpus, battle_data=solver_battle_data, output_spec=solver_battle_spec
            )
        except FightError as e:
            return FightResult(score=1, generator=gen_result, solver=e)

        score = self.problem.calculate_score(gen_result.data, sol_result.data, size)
        score = max(0, min(1, float(score)))
        logger.info(f"Solver of group {self.matchup.generator} yields a valid solution with an approx. ratio of {score}.")
        return FightResult(score, gen_result, sol_result)

    def generate(
        self,
        size: int,
        timeout: float | None = ...,
        space: int | None = ...,
        cpus: int = ...,
        battle_data: Mapping[str, Encodable] | None = None,
        output_spec: Mapping[str, type[Encodable]] | None = None,
    ) -> Result[Problem]:
        """Execute the generator and process its output."""
        logger.debug(f"Running generator of team {self.matchup.generator}.")
        if timeout is Ellipsis:
            timeout = self.timeout_generator
        if space is Ellipsis:
            space = self.space_generator
        if cpus is Ellipsis:
            cpus = self.cpus

        with TempDir() as input, TempDir() as output:
            with open(input / "size") as f:
                f.write(str(size))
            if battle_data:
                (input / "battle_data").mkdir()
                encode(battle_data, input / "battle_data", size, "generator")
            
            (output / "instance").mkdir()
            if output_spec:
                (output / "battle_data").mkdir()

            try:
                runtime = self.matchup.generator.generator.run(input, output, timeout=timeout, memory=space, cpus=cpus)
            except ExecutionError as e:
                logger.warning(f"Generator of team '{self.matchup.generator}' crashed!")
                raise FightError(e.time) from e
            except DockerError as e:
                logger.warning(f"Generator of team '{self.matchup.generator}' couldn't be executed successfully!")
                raise FightError from e

            try:
                instance = self.problem.decode(output / "instance", size)
            except Exception as e:
                logger.warning(f"Generator of team '{self.matchup.generator}' output a syntactically incorrect instance!")
                raise EncodingError(runtime) from e

            if output_spec:
                battle_output = decode(output_spec, output / "battle_data", size)
            else:
                battle_output = {}

        if not instance.check_semantics(size):
            logger.warning(f"Generator of team '{self.matchup.generator}' output a semantically incorrect instance!")
            raise EncodingError(runtime)

        logger.info(f"Generator of team '{self.matchup.generator}' output a valid instance.")
        return Result(runtime, instance, battle_output)

    def solve(
        self,
        instance: Problem,
        size: int,
        timeout: float | None = ...,
        space: int | None = ...,
        cpus: int = ...,
        battle_data: Mapping[str, Encodable] | None = None,
        output_spec: Mapping[str, type[Encodable]] | None = None,
    ) -> Result[Problem.Solution]:
        """Execute the solver and process its output."""
        logger.debug(f"Running generator of team {self.matchup.generator}.")
        if timeout is Ellipsis:
            timeout = self.timeout_generator
        if space is Ellipsis:
            space = self.space_generator
        if cpus is Ellipsis:
            cpus = self.cpus

        with TempDir() as input, TempDir() as output:
            (input / "instance").mkdir()
            try:
                instance.encode(input / "instance", size, "solver")
            except Exception as e:
                logger.warning(f"Problem instance couldn't be encoded into files!")
                raise EncodingError from e
            if battle_data:
                (input / "battle_data").mkdir()
                encode(battle_data, input / "battle_data", size, "generator")
            
            (output / "solution").mkdir()
            if output_spec:
                (output / "battle_data").mkdir()

            try:
                runtime = self.matchup.solver.solver.run(input, output, timeout=timeout, memory=space, cpus=cpus)
            except ExecutionError as e:
                logger.warning(f"Solver of team '{self.matchup.solver}' crashed!")
                raise FightError(e.time) from e
            except DockerError as e:
                logger.warning(f"Solver of team '{self.matchup.solver}' couldn't be executed successfully!")
                raise FightError from e

            try:
                solution = self.problem.Solution.decode(output / "solution", size)
            except Exception as e:
                logger.warning(f"Solver of team '{self.matchup.generator}' output a syntactically incorrect Solution!")
                raise EncodingError(runtime) from e

            if output_spec:
                battle_output = decode(output_spec, output / "battle_data", size)
            else:
                battle_output = {}

        if not solution.check_semantics(size, instance):
            logger.warning(f"Solver of team '{self.matchup.generator}' output a semantically incorrect instance!")
            raise EncodingError(runtime)

        logger.info(f"Solver of team '{self.matchup.generator}' output a valid solution.")
        return Result(runtime, solution, battle_output)