"""A Battle is the portion of a match where a specific team generates instances and another one solves them.

This module contains the :cls:`Battle` class, which speciefies how each type of battle is fought and scored,
some basic battle types, and related classed.
"""
from dataclasses import dataclass
from importlib.metadata import entry_points
from abc import abstractmethod
from typing import (
    Any,
    ClassVar,
    Protocol,
    TypeAlias,
    TypeVar,
)

from pydantic import Field

from algobattle.docker_util import (
    Generator,
    ProgramRunInfo,
    ProgramUiProxy,
    Solver,
)
from algobattle.util import Encodable, Role, inherit_docs, BaseModel


_BattleConfig: TypeAlias = Any
"""Type alias used to generate correct typings when subclassing :cls:`Battle`.

Each battle type's :meth:`run` method is guaranteed to be passed an instance of its own :cls:`BattleConfig` object.
But due to limitations in the python type system we are currently not able to express this properly.
When creating your own battle type it is recommended to not use this alias and instead use the :cls:`BattleConfig` of
the new battle type directly.
"""
T = TypeVar("T")


class Fight(BaseModel):
    """The result of one fight between the participating teams.

    For a more detailed description of what each fight looks like, see :meth:`FightHandler.run`.
    """

    score: float
    """The solving Team's score.

    Always a number in [0, 1]. 0 indicates a total failure of the solver, 1 that it succeeded perfectly.
    """
    max_size: int
    """The maximum size of an instance the generator was allowed to create."""
    generator: ProgramRunInfo
    """Data about the generator's execution."""
    solver: ProgramRunInfo | None
    """Data about the solver's execution."""


class FightUiProxy(Protocol):
    """Provides an interface for :cls:`Fight` to update the ui."""

    generator: ProgramUiProxy
    solver: ProgramUiProxy

    @abstractmethod
    def start(self, max_size: int) -> None:
        """Informs the ui that a new fight has been started."""

    @abstractmethod
    def update(self, role: Role, data: ProgramRunInfo) -> None:
        """Updates the ui's current fight section with new data about a program."""

    @abstractmethod
    def end(self) -> None:
        """Informs the ui that the fight has finished running and has been added to the battle's `.fight_results`."""


@dataclass
class FightHandler:
    """Helper class to run fights of a given battle."""

    _generator: Generator
    _solver: Solver
    _battle: "Battle"
    _ui: FightUiProxy
    _set_cpus: str | None = None

    def _saved(self, fight: Fight) -> Fight:
        self._battle.fight_results.append(fight)
        self._ui.end()
        return fight

    async def run(
        self,
        max_size: int,
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
        """Execute a single fight of a battle.

        First the generator will be run and its output parsed. Then the solver will be given the created instance
        and run. Its output gets parsed into a solution, which will then be scored.
        The timeout, space, and cpu arguments each override the corresponding match config options if set. Leaving them
        unset results in the config options being used.

        Args:
            max_size: The maximum instance size the generator is allowed to create.
            timeout_generator: Timeout in seconds for the generator to finish running. `None` means it is given an
                unlimited amount of time.
            space_generator: Memory space in MB the generator has access to. `None` means it is given an unlimited
                amount of space.
            cpus_generator: Number of physical cpu cores the generator can use.
            timeout_solver: Timeout in seconds for the solver to finish running. `None` means it is given an unlimited
                amount of time.
            space_solver: Memory space in MB the solver has access to. `None` means it is given
                an unlimited amount of space.
            cpus_solver: Number of physical cpu cores the solver can use.
            generator_battle_input: Additional data the generator will be provided with.
            solver_battle_input: Additional data the solver will be provided with.
            generator_battle_output: Class used to parse additional data the generator outputs into a python object.
            solver_battle_output: Class used to parse additional data the solver outputs into a python object.

        Returns:
            The resulting info about the executed fight.
        """
        min_size = self._generator.problem_class.min_size
        if max_size < min_size:
            raise ValueError(
                f"Cannot run battle at size {max_size} since it is smaller than the smallest "
                "size the problem allows ({min_size})."
            )
        ui = self._ui
        ui.start(max_size)
        gen_result = await self._generator.run(
            max_size=max_size,
            timeout=timeout_generator,
            space=space_generator,
            cpus=cpus_generator,
            battle_input=generator_battle_input,
            battle_output=generator_battle_output,
            set_cpus=self._set_cpus,
            ui=ui.generator,
        )
        ui.update(Role.generator, gen_result.info)
        if gen_result.instance is None:
            return self._saved(Fight(score=1, max_size=max_size, generator=gen_result.info, solver=None))

        sol_result = await self._solver.run(
            gen_result.instance,
            max_size=max_size,
            timeout=timeout_solver,
            space=space_solver,
            cpus=cpus_solver,
            battle_input=solver_battle_input,
            battle_output=solver_battle_output,
            set_cpus=self._set_cpus,
            ui=ui.solver,
        )
        ui.update(Role.solver, sol_result.info)
        if sol_result.solution is None:
            return self._saved(Fight(score=0, max_size=max_size, generator=gen_result.info, solver=sol_result.info))

        score = gen_result.instance.score(solver_solution=sol_result.solution, generator_solution=gen_result.solution)
        score = max(0, min(1, float(score)))
        return self._saved(Fight(score=score, max_size=max_size, generator=gen_result.info, solver=sol_result.info))


# We need this to be here to prevent an import cycle between match.py and battle.py
class BattleUiProxy(Protocol):
    """Provides an interface for :cls:`Battle`s to update the Ui."""

    fight_ui: FightUiProxy

    @abstractmethod
    def update_data(self, data: "Battle.UiData") -> None:
        """Passes new custom display data to the Ui.

        See :cls:`Battle.UiData` for further details.
        """


class Battle(BaseModel):
    """Base for classes that execute a specific kind of battle.

    Each battle type determines what parameters each fight will be fought with, how many fights are fought, and how
    they will ultimately be scored.
    """

    fight_results: list[Fight] = Field(default_factory=list)
    """The list of fights that have been fought in this battle."""
    run_exception: str | None = None
    """The description of an otherwise unhandeled exception that occured during the execution of :meth:`.run`."""

    _battle_types: ClassVar[dict[str, type["Battle"]]] = {}
    """Dictionary mapping the names of all registered battle types to their python classes."""

    class BattleConfig(BaseModel):
        """Config object for each specific battle type.

        A custom battle type can override this class to specify config options it uses. They will be parsed from a
        dictionary located at `battle.NAME` in the main config file, where NAME is the specific batle type's name.
        The created object will then be passed to the :meth:`.run` method with its fields set accordingly.
        """

    class UiData(BaseModel):
        """Object containing custom diplay data.

        The display data object will be displayed as key-value pairs generated from the :meth:`.field` method.
        You can use the normally available pydantic config options to customize what these will look like.
        """

    @staticmethod
    def all() -> dict[str, type["Battle"]]:
        """Returns a dictionary mapping the names of all registered battle types to their python classes.

        It includes all subclasses of :cls:`Battle` that have been initialized so far, including ones exposed to the
        algobattle module via the `algobattle.battle` entrypoint hook.
        """
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
        """Calculates the score the solver has achieved during this battle.

        Should always be a nonnegative float, with higher values indicating a better performance of the solver.
        """
        raise NotImplementedError

    @staticmethod
    def format_score(score: float) -> str:
        """Formats a given score nicely.

        Purely auxialiary method that can be used to customize how a score will be rendered.
        """
        return f"{score:.2f}"

    @classmethod
    def name(cls) -> str:
        """Name of this battle type.

        Defaults to the battle class's name. Can be used to customize this behaviour if e.g. a battle type should have a
        name that is not a valid python identifier.
        """
        return cls.__name__

    @abstractmethod
    async def run_battle(self, fight: FightHandler, config: _BattleConfig, min_size: int, ui: BattleUiProxy) -> None:
        """Executes one battle.

        Args:
            fight: The :cls:`FightHandler` used to run each fight of this battle. It already contains information about
                the participating teams, default config settings, etc. Each fight can be executed using its :meth:`.run`
                method.
            config: An instance of this battle type's :cls:`BattleConfig` class, parsed from the corresponding section
                of the config file.
            min_size: The minimum size valid for this problem.
            ui: An interface to interact with the ui.
        """
        raise NotImplementedError


class Iterated(Battle):
    """Class that executes an iterated battle."""

    results: list[int] = Field(default_factory=list)

    @inherit_docs
    class BattleConfig(Battle.BattleConfig):
        rounds: int = 5
        """Number of times the instance size will be increased until the solver fails to produce correct solutions."""
        maximum_size: int = 50_000
        """Maximum instance size that will be tried."""
        exponent: int = 2
        """Determines how quickly the instance size grows."""
        minimum_score: float = 1
        """Minimum score that a solver needs to achieve in order to pass."""

    @inherit_docs
    class UiData(Battle.UiData):
        reached: list[int]
        cap: int

    async def run_battle(self, fight: FightHandler, config: BattleConfig, min_size: int, ui: BattleUiProxy) -> None:
        """Execute an iterated battle.

        Incrementally tries to search for the highest n for which the solver is still able to solve instances.
        The base increment value is multiplied with the number of iterations since the last unsolvable instance to the
        given exponent. Only once the solver fails directly after the multiplier is reset, it counts as failed. Since
        this would heavily favour probabilistic algorithms (That may have only failed by chance and are able to solve a
        certain instance size on a second try), we cap the maximum solution size by the last value that an algorithm
        has failed on. If the solver never stops, the battle will run until the instance size reaches `iteration_cap`.

        This process is repeated `rounds` many times, with each round being completely independent of each other.
        """
        for _ in range(config.rounds):
            base_increment = 0
            alive = True
            reached = 0
            cap = config.maximum_size
            current = min_size
            while alive:
                ui.update_data(self.UiData(reached=self.results + [reached], cap=cap))
                result = await fight.run(current)
                score = result.score
                if score < config.minimum_score:
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
        """Averages the highest instance size reached in each round."""
        return 0 if len(self.results) == 0 else sum(self.results) / len(self.results)

    @inherit_docs
    @staticmethod
    def format_score(score: float) -> str:
        return str(int(score))


class Averaged(Battle):
    """Class that executes an averaged battle."""

    @inherit_docs
    class BattleConfig(Battle.BattleConfig):
        instance_size: int = 10
        """Instance size that will be fought at."""
        num_fights: int = 10
        """Number of iterations in each round."""

    @inherit_docs
    class UiData(Battle.UiData):
        round: int

    async def run_battle(self, fight: FightHandler, config: BattleConfig, min_size: int, ui: BattleUiProxy) -> None:
        """Execute an averaged battle.

        This simple battle type just executes `iterations` many fights after each other at size `instance_size`.
        """
        if config.instance_size < min_size:
            raise ValueError(f"size {config.instance_size} is smaller than the smallest valid size, {min_size}.")
        for i in range(config.num_fights):
            ui.update_data(self.UiData(round=i + 1))
            await fight.run(config.instance_size)

    @inherit_docs
    def score(self) -> float:
        """Averages the score of each fight."""
        if len(self.fight_results) == 0:
            return 0
        else:
            return sum(f.score for f in self.fight_results) / len(self.fight_results)

    @inherit_docs
    @staticmethod
    def format_score(score: float) -> str:
        return format(score, ".0%")
