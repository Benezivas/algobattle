"""Module providing an interface to interact with the teams' programs."""
from abc import ABC, abstractmethod
from functools import cached_property
from os import environ
from pathlib import Path
from tempfile import TemporaryDirectory
from timeit import default_timer
from types import EllipsisType
from typing import Any, ClassVar, Iterator, Protocol, Self, TypeVar, cast
from typing_extensions import TypedDict
from uuid import uuid4
import json
from dataclasses import dataclass

from docker import DockerClient
from docker.errors import APIError, BuildError as DockerBuildError, DockerException, ImageNotFound
from docker.models.images import Image as DockerImage
from docker.models.containers import Container as DockerContainer
from docker.types import Mount, LogConfig, Ulimit
from pydantic_core import CoreSchema
from pydantic_core.core_schema import no_info_after_validator_function
from requests import Timeout, ConnectionError
from pydantic import Field, GetCoreSchemaHandler
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
    RunConfig,
    RunConfigOverride,
    RunSpecs,
    ValidationError,
    Role,
    BaseModel,
)
from algobattle.problem import AnyProblem, Instance, Problem, Solution


AnySolution = Solution[Instance]


_client_var: DockerClient | None = None


T = TypeVar("T")


class _Adapter:
    """Turns a docker library config class into a pydantic parseable one."""

    _Args: ClassVar[type[TypedDict]]

    @classmethod
    def _construct(cls, kwargs: dict[str, Any]) -> Self:
        return cls(**kwargs)

    @classmethod
    def __get_pydantic_core_schema__(cls, source: type, handler: GetCoreSchemaHandler) -> CoreSchema:
        return no_info_after_validator_function(cls._construct, handler(cls._Args))


class PydanticLogConfig(LogConfig, _Adapter):  # noqa: D101
    class _Args(TypedDict):
        type: str
        conifg: dict[Any, Any]


class PydanticUlimit(Ulimit, _Adapter):  # noqa: D101
    class _Args(TypedDict):
        name: str
        soft: int
        hard: int


class AdvancedRunArgs(BaseModel):
    """Advanced docker run options.

    Contains all options exposed on the python docker run api, except `device_requests`
    and those set by :meth:`Image.run` itself.
    """

    class _BlockIOWeight(TypedDict):
        Path: str
        Weight: int

    class _DeviceRate(TypedDict):
        Path: str
        Rate: int

    class _HealthCheck(TypedDict):
        test: list[str] | str
        interval: int
        timeout: int
        retries: int
        start_period: int

    # defaults set by us
    network_mode: str = "none"

    # actual docker defaults
    command: str | list[str] | None = None
    auto_remove: bool | None = None
    blkio_weight_device: list[_BlockIOWeight] | None = None
    blkio_weight: int | None = Field(default=None, ge=10, le=1000)
    cap_add: list[str] | None = None
    cap_drop: list[str] | None = None
    cgroup_parent: str | None = None
    cgroupns: str | None = None
    cpu_count: int | None = None
    cpu_percent: int | None = None
    cpu_period: int | None = None
    cpu_quota: int | None = None
    cpu_rt_period: int | None = None
    cpu_rt_runtime: int | None = None
    cpu_shares: int | None = None
    cpuset_mems: str | None = None
    device_cgroup_rules: list[str] | None = None
    device_read_bps: list[_DeviceRate] | None = None
    device_read_iops: list[_DeviceRate] | None = None
    device_write_bps: list[_DeviceRate] | None = None
    device_write_iops: list[_DeviceRate] | None = None
    devices: list[str] | None = None
    dns: list[str] | None = None
    dns_opt: list[str] | None = None
    dns_search: list[str] | None = None
    domainname: str | list[str] | None = None
    entrypoint: str | list[str] | None = None
    environment: dict[str, str] | list[str] | None = None
    extra_hosts: dict[str, str] | None = None
    group_add: list[str] | None = None
    healthcheck: _HealthCheck | None = None
    hostname: str | None = None
    init: bool | None = None
    init_path: str | None = None
    ipc_mode: str | None = None
    isolation: str | None = None
    kernel_memory: int | str | None = None
    labels: dict[str, str] | list[str] | None = None
    links: dict[str, str] | None = None
    log_config: PydanticLogConfig | None = None
    lxc_conf: dict[Any, Any] | None = None
    mac_address: str | None = None
    mem_limit: int | str | None = None
    mem_reservation: int | str | None = None
    mem_swappiness: int | None = None
    memswap_limit: str | int | None = None
    network: str | None = None
    network_disabled: bool | None = None
    oom_kill_disable: bool | None = None
    oom_score_adj: int | None = None
    pid_mode: str | None = None
    pids_limit: int | None = None
    platform: str | None = None
    ports: dict[Any, Any] | None = None
    privileged: bool | None = None
    publish_all_ports: bool | None = None
    read_only: bool | None = None
    restart_policy: dict[Any, Any] | None = None
    runtime: str | None = None
    security_opt: list[str] | None = None
    shm_size: str | int | None = None
    stdin_open: bool | None = None
    stdout: bool | None = None
    stderr: bool | None = None
    stop_signal: str | None = None
    storage_opt: dict[Any, Any] | None = None
    stream: bool | None = None
    sysctls: dict[Any, Any] | None = None
    tmpfs: dict[Any, Any] | None = None
    tty: bool | None = None
    ulimits: list[PydanticUlimit] | None = None
    use_config_proxy: bool | None = None
    user: str | int | None = None
    userns_mode: str | None = None
    uts_mode: str | None = None
    version: str | None = None
    volume_driver: str | None = None
    volumes: dict[Any, Any] | list[Any] | None = None
    volumes_from: list[Any] | None = None
    working_dir: str | None = None

    @cached_property
    def kwargs(self) -> dict[str, Any]:
        """Transforms the object into :meth:`client.containers.run` kwargs."""
        return self.model_dump(exclude_none=True)


class AdvancedBuildArgs(BaseModel):
    """Advanced docker build options.

    Contains all options exposed on the python docker build api, except those set by :meth:`Image.build` itself.
    """

    class _ContainerLimits(TypedDict):
        memory: int
        memswap: int
        cpushares: int
        cpusetcpus: str

    # defaults set by us
    rm: bool = True
    forcerm: bool = True
    quiet: bool = True
    network_mode: str = "host"
    pull: bool | None = True

    # actual Docker defaults
    nocache: bool | None = None
    encoding: str | None = None
    buildargs: dict[Any, Any] | None = None
    container_limits: _ContainerLimits | None = None
    shmsize: int | None = None
    labels: dict[Any, Any] | None = None
    cache_from: list[Any] | None = None
    target: str | None = None
    squash: bool | None = None
    extra_hosts: dict[Any, Any] | None = None
    platform: str | None = None
    isolation: str | None = None
    use_config_proxy: bool | None = None

    @cached_property
    def kwargs(self) -> dict[str, Any]:
        """Transforms the object into :meth:`client.images.build` kwargs."""
        return self.model_dump(exclude_none=True)


class DockerConfig(BaseModel):
    """Settings passed directly to the docker daemon."""

    build: AdvancedBuildArgs = AdvancedBuildArgs()
    run: AdvancedRunArgs = AdvancedRunArgs()


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
    problem: Problem[Instance, Solution[Instance]]
    """The problem this program creates instances and/or solutions for."""
    config: RunConfig
    """Config settings this program will use."""
    strict_timeouts: bool
    """Wether this program will raise an exception if the container times out."""
    docker_config: DockerConfig
    """Advanced config settings this program will use to run."""

    role: ClassVar[Role]
    """Role of this program."""

    @classmethod
    async def build(
        cls,
        path: Path,
        *,
        timeout: float | None = 600,
        max_size: int | None = None,
        team_name: str | None = None,
        problem: AnyProblem,
        config: RunConfig = RunConfig(),
        strict_timeouts: bool = False,
        docker_config: DockerConfig = DockerConfig(),
    ) -> Self:
        """Creates a program by building the specified docker image.

        Args:
            path: Path to a Dockerfile (or folder containing one) from which to build the image.
            timeout: Build timeout.
            max_size: Maximum size of the built image.
            team_name: If set the image will be given a descriptive name.
            problem: Problem this program is solving/generating instances for.
            config: Run config for this program.
            strict_timeouts: Wether to raise an error if the container times out but produces valid output.
            docker_config: Docker config that will be used to build and run this program.

        Returns:
            The built Program.

        Raises:
            BuildError: If the build fails for any reason.
        """
        if not path.exists():
            raise RuntimeError
        if path.is_file():
            dockerfile = path.name
            path = path.parent
        else:
            dockerfile = None

        if team_name is not None:
            name = f"algobattle_{team_name}_{cls.role.name}"
            try:
                old_image = cast(DockerImage, client().images.get(name))
            except ImageNotFound:
                old_image = None
        else:
            name = None
            old_image = None

        try:
            image = await run_sync(
                cls._build_daemon_call,
                str(path),
                name,
                timeout,
                dockerfile,
                docker_config.build.kwargs,
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
            strict_timeouts=strict_timeouts,
            docker_config=docker_config,
        )
        used_size = cast(dict[str, Any], image.attrs).get("Size", 0)
        if max_size is not None and used_size > max_size:
            try:
                self.remove()
            finally:
                raise BuildError("Built image is too large.", detail=f"Size: {used_size}B, limit: {max_size}B.")
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
                    **self.docker_config.run.kwargs,
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
            if self.strict_timeouts:
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
        specs = self.config.reify(timeout, space, cpus)
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
        specs = self.config.reify(timeout, space, cpus)
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
