"""Module providing an interface to interact with the teams' programs."""
from abc import ABC, abstractmethod
from contextlib import contextmanager
from os import environ
from pathlib import Path
from tarfile import TarFile, is_tarfile
from tempfile import TemporaryDirectory
from timeit import default_timer
from types import EllipsisType
from typing import Any, ClassVar, Iterator, Protocol, Self, TypeVar, cast, Generator as PyGenerator
from typing_extensions import TypedDict
from uuid import uuid4
import json
from dataclasses import dataclass
from zipfile import ZipFile, is_zipfile

from docker import DockerClient
from docker.errors import APIError, BuildError as DockerBuildError, DockerException, ImageNotFound
from docker.models.images import Image as DockerImage
from docker.models.containers import Container as DockerContainer
from docker.types import Mount
from requests import Timeout, ConnectionError
from pydantic import Field
from anyio.to_thread import run_sync
from urllib3.exceptions import ReadTimeoutError

from algobattle.util import (
    BuildError,
    DockerError,
    Encodable,
    EncodingError,
    ExceptionInfo,
    ExecutionError,
    ExecutionTimeout,
    ValidationError,
    Role,
    BaseModel,
)
from algobattle.problem import AnyProblem, Instance, Solution


AnySolution = Solution[Instance]


_client_var: DockerClient | None = None


T = TypeVar("T")


def client() -> DockerClient:
    """Returns the docker api client, checking that it's still responsive."""
    global _client_var
    try:
        if _client_var is None:
            _client_var = DockerClient.from_env()
        else:
            _client_var.ping()
    except (DockerException, APIError):
        raise SystemExit("Could not connect to the docker daemon. Is docker running?")
    return _client_var


class RunConfigOverride(TypedDict, total=False):
    """Run parameters that were overriden by the battle type."""

    timeout: float | None
    space: int | None
    cpus: int


@dataclass(frozen=True, slots=True)
class RunSpecs:
    """Actual specification of a program run."""

    timeout: float | None
    space: int | None
    cpus: int
    overriden: RunConfigOverride


@dataclass(frozen=True, slots=True)
class RunConfigView:
    """Config view for single runs."""

    timeout: float | None
    space: int | None
    cpus: int

    def reify(
        self,
        timeout: float | None | EllipsisType,
        space: int | None | EllipsisType,
        cpus: int | EllipsisType,
    ) -> RunSpecs:
        """Merges the overriden config options with the parsed ones."""
        overriden = RunConfigOverride()
        if timeout is ...:
            timeout = self.timeout
        else:
            overriden["timeout"] = timeout
        if space is ...:
            space = self.space
        else:
            overriden["space"] = space
        if cpus is ...:
            cpus = self.cpus
        else:
            overriden["cpus"] = cpus
        return RunSpecs(timeout=timeout, space=space, cpus=cpus, overriden=overriden)


@dataclass(frozen=True, slots=True)
class ProgramConfigView:
    """Config settings relevant to the program module."""

    build_timeout: float | None
    max_image_size: int | None
    strict_timeouts: bool
    build_kwargs: dict[str, Any]
    run_kwargs: dict[str, Any]
    generator: RunConfigView
    solver: RunConfigView


class ProgramUi(Protocol):
    """Provides an interface for :class:`Program` to update the Ui."""

    @abstractmethod
    def start_program(self, role: Role, timeout: float | None) -> None:
        """Signals that the program execution has been started."""

    @abstractmethod
    def stop_program(self, role: Role, runtime: float) -> None:
        """Signals that the program execution has been finished."""


class ProgramIO:
    """Manages the directories used to pass IO to programs.

    Normally we can just create temporary directories using the python stdlib, but when running inside a container we
    need to use a directory thats bound to one on the host machine.
    """

    host_dir: ClassVar[Path | None] = Path(environ["ALGOBATTLE_IO_DIR"]) if "ALGOBATTLE_IO_DIR" in environ else None
    parent_dir: ClassVar[Path | None] = Path("/algobattle/io") if "ALGOBATTLE_IO_DIR" in environ else None

    def __init__(self) -> None:
        """Creates the needed temporary directories."""
        super().__init__()
        self._input = TemporaryDirectory(dir=self.parent_dir)
        self._output = TemporaryDirectory(dir=self.parent_dir)

    @property
    def input(self) -> Path:
        """Path to the input directory."""
        return Path(self._input.name)

    @property
    def output(self) -> Path:
        """Path to the output directoy."""
        return Path(self._output.name)

    @property
    def mounts(self) -> list[Mount]:
        """A list of Mounts corresponding to these IO directories that can be passed to the docker api."""
        if self.host_dir:
            host_input = self.host_dir / self.input.name
            host_output = self.host_dir / self.output.name
        else:
            host_input = self.input
            host_output = self.output
        return [
            Mount(target="/input", source=str(host_input), type="bind", read_only=True),
            Mount(target="/output", source=str(host_output), type="bind"),
        ]

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc: Any, val: Any, tb: Any):
        self._input.__exit__(exc, val, tb)
        self._output.__exit__(exc, val, tb)


class ProgramRunInfo(BaseModel):
    """Data about a program's execution."""

    runtime: float = 0
    overriden: RunConfigOverride = Field(default_factory=dict)
    error: ExceptionInfo | None = None


@dataclass
class ProgramResult:
    """The result of a program execution."""

    info: ProgramRunInfo
    battle_data: Encodable | None = None


@dataclass
class GeneratorResult(ProgramResult):
    """Result of a single generator execution."""

    instance: Instance | None = None
    solution: AnySolution | None = None


@dataclass
class SolverResult(ProgramResult):
    """Result of a single solver execution."""

    solution: AnySolution | None = None


@dataclass
class _WrappedException(Exception):
    """Wraps an inner exception such that we can recover the runtime from outer methods easily."""

    inner: Exception
    runtime: float


@dataclass(frozen=True)
class Program(ABC):
    """A higher level interface for a team's programs."""

    id: str
    """The id of the Docker image."""
    problem: AnyProblem
    """The problem this program generates/solves."""
    config: ProgramConfigView
    """Config settings used for this program."""

    role: ClassVar[Role]
    """Role of this program."""

    @classmethod
    @contextmanager
    def _setup_docker_env(cls, source: Path) -> PyGenerator[tuple[Path, str | None], None, None]:
        """Creates a folder containing the actual docker environment used to build a program."""
        if not source.exists():
            raise ValueError
        if source.is_dir():
            yield source, None
            return
        if source.name == "Dockerfile" or source.suffix == ".dockerfile":
            yield source.parent, source.name
            return

        with TemporaryDirectory() as build_folder:
            build_folder = Path(build_folder)
            if is_zipfile(source):
                with ZipFile(source, "r") as f:
                    f.extractall(build_folder)
            elif is_tarfile(source):
                with TarFile(source, "r") as f:
                    f.extractall(build_folder)
            else:
                raise ValueError(f"The file {source} is not recognisable as a dockerfile.")

            yield build_folder, None

    @classmethod
    async def build(
        cls,
        path: Path,
        *,
        problem: AnyProblem,
        config: ProgramConfigView,
        team_name: str | None = None,
    ) -> Self:
        """Creates a program by building the specified docker image.

        Args:
            path: Path to a Dockerfile (or folder containing one) from which to build the image.
            problem: The problem this program generates/solves.
            config: Settings for this program.
            team_name: If set the image will be given a descriptive name.

        Returns:
            The built Program.

        Raises:
            BuildError: If the build fails for any reason.
        """
        if team_name is not None:
            name = f"algobattle_{team_name}_{cls.role.name}"
            try:
                old_image = cast(DockerImage, client().images.get(name))
            except ImageNotFound:
                old_image = None
        else:
            name = None
            old_image = None

        with cls._setup_docker_env(path) as (path, dockerfile):
            try:
                image = await run_sync(
                    cls._build_daemon_call,
                    str(path),
                    name,
                    config.build_timeout,
                    dockerfile,
                    config.build_kwargs,
                )
                if old_image is not None:
                    old_image.reload()
                    if len(old_image.tags) == 0:
                        old_image.remove(force=True)

            except Timeout as e:
                raise BuildError("Build ran into a timeout.") from e
            except DockerBuildError as e:
                raise BuildError("Build did not complete successfully.", detail=e.msg) from e
            except APIError as e:
                raise BuildError("Docker APIError thrown while building.", detail=str(e)) from e

        self = cls(
            cast(str, image.id),
            problem=problem,
            config=config,
        )
        used_size = cast(dict[str, Any], image.attrs).get("Size", 0)
        if config.max_image_size is not None and used_size > config.max_image_size:
            try:
                self.remove()
            finally:
                raise BuildError(
                    "Built image is too large.", detail=f"Size: {used_size}B, limit: {config.max_image_size}B."
                )
        return self

    @classmethod
    def _build_daemon_call(
        cls, path: str, tag: str | None, timeout: float | None, dockerfile: str | None, build_kwargs: dict[str, Any]
    ) -> DockerImage:
        image, _logs = cast(
            tuple[DockerImage, Iterator[Any]],
            client().images.build(
                path=str(path),
                tag=tag,
                timeout=timeout,
                dockerfile=dockerfile,
                **build_kwargs,
            ),
        )
        return image

    def run_specs(
        self,
        timeout: float | None | EllipsisType,
        space: int | None | EllipsisType,
        cpus: int | EllipsisType,
    ) -> RunSpecs:
        """Merges the overriden config options with the parsed ones."""
        overriden = RunConfigOverride()
        match self.role:
            case Role.generator:
                config = self.config.generator
            case Role.solver:
                config = self.config.solver
        if timeout is ...:
            timeout = config.timeout
        else:
            overriden["timeout"] = timeout
        if space is ...:
            space = config.space
        else:
            overriden["space"] = space
        if cpus is ...:
            cpus = config.cpus
        else:
            overriden["cpus"] = cpus
        return RunSpecs(timeout=timeout, space=space, cpus=cpus, overriden=overriden)

    async def _run_inner(
        self,
        *,
        io: ProgramIO,
        max_size: int,
        specs: RunSpecs,
        battle_input: Encodable | None,
        battle_output: type[Encodable] | None,
        set_cpus: str | None,
        ui: ProgramUi | None,
    ) -> tuple[float, Encodable | None]:
        """Encodes the metadata, runs the docker container, and decodes battle metadata."""
        with open(io.input / "info.json", "w+") as f:
            json.dump(
                {
                    "max_size": max_size,
                    "timeout": specs.timeout,
                    "space": specs.space,
                    "cpus": specs.cpus,
                },
                f,
            )
        if battle_input is not None:
            try:
                battle_input.encode(io.input / "battle_data", self.role)
            except Exception as e:
                raise EncodingError("Battle data couldn't be encoded.", detail=str(e))

        runtime = 0
        try:
            container = cast(
                DockerContainer,
                client().containers.create(
                    image=self.id,
                    name=f"algobattle_{uuid4().hex[:8]}",
                    mem_limit=specs.space,
                    nano_cpus=specs.cpus * 1_000_000_000,
                    detach=True,
                    mounts=io.mounts if io else None,
                    cpuset_cpus=set_cpus,
                    **self.config.run_kwargs,
                ),
            )

            if ui is not None:
                ui.start_program(self.role, specs.timeout)
            try:
                runtime = await run_sync(self._run_daemon_call, container, specs.timeout)
            except ExecutionError as e:
                raise _WrappedException(e, e.runtime)
            finally:
                container.remove(force=True)
                if ui is not None:
                    ui.stop_program(self.role, runtime)
        except APIError as e:
            raise _WrappedException(
                DockerError("Docker APIError thrown while running container.", detail=str(e)), runtime
            )

        if battle_output:
            try:
                decoded_battle_output = battle_output.decode(io.output / "battle_data", max_size, self.role)
            except Exception as e:
                raise _WrappedException(e, runtime)
        else:
            decoded_battle_output = None
        return runtime, decoded_battle_output

    def _run_daemon_call(self, container: DockerContainer, timeout: float | None = None) -> float:
        """Runs the container.

        Returns:
            The container runtime
        Raises:
            ExecutionTimeout: When the container runs into the timeout.
            ExecutionError: When the process inside the container crashes.
            DockerException: When the daeomon raises some other error.
        """
        # this method has to be a thicker wrapper since we have to kill the container asap, not just when the
        # async manager gives us back control.
        container.start()
        start_time = default_timer()
        elapsed_time = 0
        try:
            response = cast(dict[str, Any], container.wait(timeout=timeout))
            elapsed_time = round(default_timer() - start_time, 2)
            if response["StatusCode"] == 0:
                return elapsed_time
            else:
                raise ExecutionError(
                    "The program executed in the container crashed.",
                    detail=f"exit code: {response['StatusCode']}, error message:\n{container.logs().decode()}",
                    runtime=elapsed_time,
                )
        except (Timeout, ConnectionError) as e:
            container.kill()
            elapsed_time = round(default_timer() - start_time, 2)
            if len(e.args) != 1 or not isinstance(e.args[0], ReadTimeoutError):
                raise
            if self.config.strict_timeouts:
                raise ExecutionTimeout("The docker container exceeded the time limit.", runtime=elapsed_time)
            return elapsed_time

    def remove(self) -> None:
        """Removes the image from the docker daemon.

        **This will not cause the python object to be deleted.**
        Attempting to run the image after it has been removed will cause runtime errors.
        Will not throw an error if the image has been removed already.

        Raises:
            DockerError: When removing the image fails.
        """
        try:
            client().images.remove(image=self.id, force=True)
        except ImageNotFound:
            pass
        except APIError as e:
            raise DockerError("Docker APIError thrown while removing image.", detail=str(e)) from e

    def __enter__(self):
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any):
        self.remove()


class Generator(Program):
    """A higher level interface for a team's generator."""

    role: ClassVar[Role] = Role.generator

    async def run(
        self,
        max_size: int,
        *,
        timeout: float | None | EllipsisType = ...,
        space: int | None | EllipsisType = ...,
        cpus: int | EllipsisType = ...,
        battle_input: Encodable | None = None,
        battle_output: type[Encodable] | None = None,
        ui: ProgramUi | None = None,
        set_cpus: str | None = None,
    ) -> GeneratorResult:
        """Executes the generator and parses its output into a problem instance.

        Args:
            max_size: Maximum size of the instance that the generator is allowed to generate.
            timeout: Timeout for the program in seconds.
            space: Maximum amount of memory space this program can use in bytes.
            cpus: Number of cpu cores this program can use.
            battle_input: Additional data that will be given to the generator.
            battle_output: Class that will be used to parse additional data the generator outputs.
            ui: Interface the program execution uses to update the ui.
            set_cpus: A docker format string specifying what cpu cores the program should use, or None for any cores.

        Returns:
            Datastructure containing all info about the generator execution and the created problem instance.
        """
        specs = self.run_specs(timeout, space, cpus)
        runtime = 0
        battle_data = None
        instance = None
        solution = None
        exception_info = None
        with ProgramIO() as io:
            try:
                with open(io.input / "max_size.txt", "w+") as f:
                    f.write(str(max_size))

                runtime, battle_data = await self._run_inner(
                    io=io,
                    max_size=max_size,
                    specs=specs,
                    battle_input=battle_input,
                    battle_output=battle_output,
                    ui=ui,
                    set_cpus=set_cpus,
                )

                try:
                    instance = self.problem.instance_cls.decode(io.output / "instance", max_size, self.role)
                except EncodingError:
                    raise
                except Exception as e:
                    raise EncodingError("Unknown error thrown while decoding the problem instance.", detail=str(e))
                try:
                    instance.validate_instance()
                except ValidationError:
                    raise
                except Exception as e:
                    raise ValidationError("Unknown error thrown during instance validation.", detail=str(e))
                if instance.size > max_size:
                    raise ValidationError(
                        "Instance is too large.", detail=f"Generated: {instance.size}, maximum: {max_size}"
                    )
                if self.problem.with_solution:
                    try:
                        solution = self.problem.solution_cls.decode(io.output / "solution", max_size, self.role)
                    except EncodingError:
                        raise
                    except Exception as e:
                        raise EncodingError("Unknown error thrown while decoding the solution.", detail=str(e))
                    try:
                        solution.validate_solution(instance, Role.generator)
                    except ValidationError:
                        raise
                    except Exception as e:
                        raise ValidationError("Unknown error thrown during solution validation.", detail=str(e))

            except _WrappedException as e:
                runtime = e.runtime
                exception_info = ExceptionInfo.from_exception(e.inner)
            except Exception as e:
                exception_info = ExceptionInfo.from_exception(e)
            return GeneratorResult(
                info=ProgramRunInfo(runtime=runtime, overriden=specs.overriden, error=exception_info),
                battle_data=battle_data,
                instance=instance,
                solution=solution,
            )


class Solver(Program):
    """A higher level interface for a team's solver."""

    role: ClassVar[Role] = Role.solver

    def _encode_input(self, input: Path, max_size: int, instance: Instance | None) -> None:
        assert instance is not None
        instance.encode(input / "instance", self.role)

    def _parse_output(self, output: Path, max_size: int, instance: Instance | None) -> AnySolution:
        assert instance is not None
        try:
            solution = self.problem.solution_cls.decode(output / "solution", max_size, self.role, instance)
        except EncodingError:
            raise
        except Exception as e:
            raise EncodingError("Error thrown while decoding the solution.", detail=str(e)) from e
        try:
            solution.validate_solution(instance, Role.solver)
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError("Unknown error during solution validation.", detail=str(e)) from e
        return solution

    async def run(
        self,
        instance: Instance,
        max_size: int,
        *,
        timeout: float | None | EllipsisType = ...,
        space: int | None | EllipsisType = ...,
        cpus: int | EllipsisType = ...,
        battle_input: Encodable | None = None,
        battle_output: type[Encodable] | None = None,
        ui: ProgramUi | None = None,
        set_cpus: str | None = None,
    ) -> SolverResult:
        """Executes the solver on the given problem instance and parses its output into a problem solution.

        Args:
            max_size: Maximum size of the instance that the generator is allowed to generate.
            timeout: Timeout for the program in seconds.
            space: Maximum amount of memory space this program can use in bytes.
            cpus: Number of cpu cores this program can use.
            battle_input: Additional data that will be given to the solver.
            battle_output: Class that will be used to parse additional data the solver outputs.
            ui: Interface the program execution uses to update the ui.
            set_cpus: A docker format string specifying what cpu cores the program should use, or None for any cores.

        Returns:
            Datastructure containing all info about the solver execution and the solution it computed.
        """
        specs = self.run_specs(timeout, space, cpus)
        runtime = 0
        battle_data = None
        solution = None
        exception_info = None
        with ProgramIO() as io:
            try:
                instance.encode(io.input / "instance", self.role)
                runtime, battle_data = await self._run_inner(
                    io=io,
                    max_size=max_size,
                    specs=specs,
                    battle_input=battle_input,
                    battle_output=battle_output,
                    ui=ui,
                    set_cpus=set_cpus,
                )
                try:
                    solution = self.problem.solution_cls.decode(io.output / "solution", max_size, self.role, instance)
                except EncodingError:
                    raise
                except Exception as e:
                    raise EncodingError("Unexpected error thrown while decoding the solution.", detail=str(e))
                try:
                    solution.validate_solution(instance, Role.solver)
                except ValidationError:
                    raise
                except Exception as e:
                    raise ValidationError("Unexpected error during solution validation.", detail=str(e))

            except _WrappedException as e:
                runtime = e.runtime
                exception_info = ExceptionInfo.from_exception(e.inner)
            except Exception as e:
                exception_info = ExceptionInfo.from_exception(e)
            return SolverResult(
                info=ProgramRunInfo(runtime=runtime, overriden=specs.overriden, error=exception_info),
                battle_data=battle_data,
                solution=solution,
            )
