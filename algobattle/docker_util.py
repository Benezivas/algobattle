"""Module providing an interface to interact with the teams' programs."""
from abc import ABC, abstractmethod
from os import environ
from pathlib import Path
from tempfile import TemporaryDirectory
from timeit import default_timer
from types import TracebackType
from typing import Annotated, Any, ClassVar, Iterator, Protocol, Self, cast
from typing_extensions import TypedDict
from uuid import uuid4
import json
from dataclasses import dataclass

from docker import DockerClient
from docker.errors import APIError, BuildError as DockerBuildError, DockerException, ImageNotFound
from docker.models.images import Image as DockerImage
from docker.models.containers import Container as DockerContainer
from docker.types import Mount, LogConfig, Ulimit
from requests import Timeout, ConnectionError
from pydantic import AfterValidator, Field
from anyio.to_thread import run_sync
from urllib3.exceptions import ReadTimeoutError

from algobattle.util import (
    AlgobattleBaseException,
    BuildError,
    DockerError,
    Encodable,
    EncodingError,
    ExceptionInfo,
    ExecutionError,
    ExecutionTimeout,
    ValidationError,
    Role,
    inherit_docs,
    BaseModel,
)
from algobattle.problem import AnyProblem, Instance, Solution


AnySolution = Solution[Instance]


_client_var: DockerClient | None = None


def parse_none(value: Any) -> Any | None:
    """Used as a validator to parse false-y values into Python None objects."""
    return None if not value else value


NoneFloat = Annotated[float | None, AfterValidator(parse_none)]
NoneInt = Annotated[int | None, AfterValidator(parse_none)]
NoneStr = Annotated[str | None, AfterValidator(parse_none)]


class RunParameters(BaseModel):
    """The parameters determining how a program is run."""

    timeout: NoneFloat = 30
    space: NoneInt = None
    cpus: int = 1


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

    class _LogConfigArgs(TypedDict):
        type: str
        conifg: dict[Any, Any]

    class _UlimitArgs(TypedDict):
        name: str
        soft: int
        hard: int

    network_mode: str = "none"
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
    log_config: _LogConfigArgs | None = None
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
    ulimits: list[_UlimitArgs] | None = None
    use_config_proxy: bool | None = None
    user: str | int | None = None
    userns_mode: str | None = None
    uts_mode: str | None = None
    version: str | None = None
    volume_driver: str | None = None
    volumes: dict[Any, Any] | list[Any] | None = None
    volumes_from: list[Any] | None = None
    working_dir: str | None = None

    def to_docker_args(self) -> dict[str, Any]:
        """Transforms the object into :meth:`client.containers.run` kwargs."""
        kwargs = self.model_dump(exclude_none=True)
        if "log_config" in kwargs:
            kwargs["log_config"] = LogConfig(**kwargs["log_config"])
        if "ulimits" in kwargs:
            kwargs["ulimits"] = Ulimit(**kwargs["ulimits"])
        return kwargs


class AdvancedBuildArgs(BaseModel):
    """Advanced docker build options.

    Contains all options exposed on the python docker build api, except those set by :meth:`Image.build` itself.
    """

    class _ContainerLimits(TypedDict):
        memory: int
        memswap: int
        cpushares: int
        cpusetcpus: str

    quiet: bool = True
    nocache: bool | None = None
    rm: bool = True
    encoding: str | None = None
    pull: bool | None = True
    forcerm: bool = True
    buildargs: dict[Any, Any] | None = None
    container_limits: _ContainerLimits | None = None
    shmsize: int | None = None
    labels: dict[Any, Any] | None = None
    cache_from: list[Any] | None = None
    target: str | None = None
    network_mode: str = "host"
    squash: bool | None = None
    extra_hosts: dict[Any, Any] | None = None
    platform: str | None = None
    isolation: str | None = None
    use_config_proxy: bool | None = None

    def to_docker_args(self) -> dict[str, Any]:
        """Transforms the object into :meth:`client.images.build` kwargs."""
        return self.model_dump(exclude_none=True)


class ProgramConfig(BaseModel):
    """Config options relevant to the way programs are run and built."""

    build_timeout: NoneFloat = None
    strict_timeouts: bool = False
    set_cpus: NoneStr | list[str] | None = None
    image_size: NoneInt = None
    generator: RunParameters = RunParameters()
    solver: RunParameters = RunParameters()
    advanced_build_params: AdvancedBuildArgs = AdvancedBuildArgs()
    advanced_run_params: AdvancedRunArgs = AdvancedRunArgs()


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


def set_docker_config(config: ProgramConfig) -> None:
    """Sets up the static docker config attributes.

    Various classes in the docker_util module need statically set config options, e.g. advanced build/run arguments or
    the strict_timeout option. This function propagates initializes all of these correctly.
    """
    Image.build_kwargs = config.advanced_build_params.to_docker_args()
    Image.run_kwargs = config.advanced_run_params.to_docker_args()
    Program.docker_config = config
    Image.docker_config = config


class ProgramUiProxy(Protocol):
    """Provides an interface for :class:`Program` to update the Ui."""

    @abstractmethod
    def start(self, timeout: float | None) -> None:
        """Signals that the program execution has been started."""

    @abstractmethod
    def stop(self, runtime: float) -> None:
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


@dataclass
class Image:
    """Class defining a docker image.

    Instances may outlive the actual docker images in the daemon!
    To prevent this don't use the object after calling `.remove()`.
    """

    id: str
    path: Path

    docker_config: ClassVar[ProgramConfig] = ProgramConfig()

    run_kwargs: ClassVar[dict[str, Any]] = {
        "network_mode": "none",
    }
    """Advanced docker options passed to the docker run command.

    A full description can be found at the docker api reference."""
    build_kwargs: ClassVar[dict[str, Any]] = {
        "rm": True,
        "forcerm": True,
        "quiet": True,
        "network_mode": "host",
        "pull": True,
    }
    """Advanced docker options passed to the docker build command.

    A full description can be found at the docker api reference."""

    @classmethod
    def _build_image(cls, path: str, tag: str | None, timeout: float | None, dockerfile: str | None) -> DockerImage:
        image, _logs = cast(
            tuple[DockerImage, Iterator[Any]],
            client().images.build(
                path=str(path),
                tag=tag,
                timeout=timeout,
                dockerfile=dockerfile,
                **cls.build_kwargs,
            ),
        )
        return image

    @classmethod
    async def build(
        cls,
        path: Path,
        name: str | None = None,
        timeout: float | None = None,
    ) -> Self:
        """Builds a docker image using the dockerfile found at the provided path.

        Args:
            path: The path to the directory containing a `Dockerfile`, or a path to such a file itself.
            name: A tag assigned to the docker image, if set to `None` the image will receive no tag.
            timeout: Timeout in seconds for the build process.

        Raises:
            BuildError: On all errors that are expected to happen during the build process.
        """
        if not path.exists():
            raise RuntimeError
        if path.is_file():
            dockerfile = path.name
            path = path.parent
        else:
            dockerfile = None
        try:
            if name is not None:
                try:
                    old_image = cast(DockerImage, client().images.get(name))
                except ImageNotFound:
                    old_image = None
            else:
                old_image = None
            image = await run_sync(cls._build_image, str(path), name, timeout, dockerfile)
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

        self = cls(cast(str, image.id), path=path)
        size_limit = cls.docker_config.image_size
        used_size = cast(dict[str, Any], image.attrs).get("Size", 0)
        if size_limit is not None and used_size > size_limit:
            try:
                self.remove()
            finally:
                raise BuildError("Built image is too large.", detail=f"Built size: {used_size}, limit: {size_limit}.")
        return self

    def __enter__(self):
        return self

    def __exit__(self, _type: type[Exception], _value: Exception, _traceback: TracebackType):
        self.remove()

    async def run(
        self,
        io: ProgramIO | None = None,
        *,
        timeout: float | None = None,
        memory: int | None = None,
        cpus: int = 1,
        set_cpus: str | None = None,
        ui: ProgramUiProxy | None = None,
    ) -> float:
        """Runs a docker image.

        Args:
            io: ProgramIO object tracking an input directory with data for the container and one for its output data.
            timeout: Timeout in seconds.
            memory: Memory limit in MB.
            cpus: Number of physical cpus the container can use.
            set_cpus: Which cpus to execute the container on. Either a comma separated list or a hyphen-separated range.
                A value of `None` means the container can use any core (but still only `cpus` many of them).
            ui: Interface to update the ui with new data about the executing program.

        Raises:
            RuntimeError: If the image does not actually exist in the docker daemon.
            ExecutionError: If the program does not execute successfully.
            ExecutionTimeout: If the program times out.
            DockerError: If there is some kind of error originating from the docker daemon.

        Returns:
            The runtime of the program.
        """
        name = f"algobattle_{uuid4().hex[:8]}"
        if memory is not None:
            memory = memory * 1_000_000
        cpus = cpus * 1_000_000_000

        container: DockerContainer | None = None
        elapsed_time = 0
        try:
            container = cast(
                DockerContainer,
                client().containers.create(
                    image=self.id,
                    name=name,
                    mem_limit=memory,
                    nano_cpus=cpus,
                    detach=True,
                    mounts=io.mounts if io else None,
                    cpuset_cpus=set_cpus,
                    **self.run_kwargs,
                ),
            )

            if ui is not None:
                ui.start(timeout)
            elapsed_time = await run_sync(self._run_container, container, timeout)
            if ui is not None:
                ui.stop(elapsed_time)

        except ImageNotFound as e:
            raise RuntimeError("Image (id: {self.id}) does not exist.") from e
        except APIError as e:
            raise DockerError("Docker APIError thrown while running container.", detail=str(e)) from e
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except APIError as e:
                    raise DockerError("Couldn't remove container.", detail=str(e)) from e

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

    def _run_container(self, container: DockerContainer, timeout: float | None = None) -> float:
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
            raise ExecutionTimeout("The docker container exceeded the time limit.", runtime=elapsed_time)


class ProgramRunInfo(BaseModel):
    """Data about a program's execution."""

    params: RunParameters
    runtime: float
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
class _GenResData:
    problem: Instance
    solution: AnySolution | None


@dataclass
class Program(ABC):
    """A higher level interface for a team's programs."""

    image: Image
    """The underlying docker image."""
    config: RunParameters
    """The default config options this program will be executed with."""
    problem: AnyProblem
    """The problem this program creates instances and/or solutions for."""

    role: ClassVar[Role]
    docker_config: ClassVar[ProgramConfig] = ProgramConfig()

    @classmethod
    async def build(
        cls,
        image: Path | Image,
        problem: AnyProblem,
        config: RunParameters,
        timeout: float | None = None,
        team_name: str | None = None,
    ) -> Self:
        """Creates a program by building the specified docker image.

        Args:
            image: Path to a Dockerfile (or folder containing one) from which to build the image.
                Or an already built image.
            problem_class: Problem class this program is solving/generating instances for.
            config: Config options for this program.
            team_name: If set the image will be given a descriptive name.

        Returns:
            The built Program.
        """
        if isinstance(image, Path):
            if team_name is not None:
                name = f"algobattle_{team_name}_{cls.role.name}"
            else:
                name = None
            image = await Image.build(
                path=image,
                name=name,
                timeout=timeout,
            )

        return cls(image, config, problem)

    @abstractmethod
    def _encode_input(self, input: Path, max_size: int, instance: Instance | None) -> None:
        """Sets up the i/o folders as required for the specific type of program."""
        raise NotImplementedError

    @abstractmethod
    def _parse_output(self, output: Path, max_size: int, instance: Instance | None) -> _GenResData | AnySolution:
        """Parses the data in the output folder into problem instances/solutions."""
        raise NotImplementedError

    async def _run(
        self,
        max_size: int,
        input_instance: Instance | None = None,
        *,
        timeout: float | None = ...,
        space: int | None = ...,
        cpus: int = ...,
        battle_input: Encodable | None = None,
        battle_output: type[Encodable] | None = None,
        set_cpus: str | None = None,
        ui: ProgramUiProxy | None = None,
    ) -> GeneratorResult | SolverResult:
        """Execute the program, processing input and output data."""
        if timeout is Ellipsis:
            timeout = self.config.timeout
        if space is Ellipsis:
            space = self.config.space
        if cpus is Ellipsis:
            cpus = self.config.cpus
        run_params = RunParameters(timeout=timeout, space=space, cpus=cpus)
        result_class = GeneratorResult if self.role == Role.generator else SolverResult

        with ProgramIO() as io:
            try:
                self._encode_input(io.input, max_size, input_instance)
            except AlgobattleBaseException as e:
                return result_class(ProgramRunInfo(params=run_params, runtime=0, error=ExceptionInfo.from_exception(e)))
            with open(io.input / "info.json", "w+") as f:
                json.dump(
                    {
                        "max_size": max_size,
                        "timeout": timeout,
                        "space": space,
                        "cpus": cpus,
                    },
                    f,
                )
            if battle_input is not None:
                try:
                    battle_input.encode(io.input / "battle_data", self.role)
                except Exception as e:
                    return result_class(
                        ProgramRunInfo(
                            params=run_params,
                            runtime=0,
                            error=ExceptionInfo(type="EncodingError", message=f"Battle data couldn't be encoded:\n{e}"),
                        )
                    )

            try:
                runtime = await self.image.run(io, timeout=timeout, memory=space, cpus=cpus, ui=ui, set_cpus=set_cpus)
            except ExecutionTimeout as e:
                if self.docker_config.strict_timeouts:
                    return result_class(
                        ProgramRunInfo(params=run_params, runtime=e.runtime, error=ExceptionInfo.from_exception(e))
                    )
                else:
                    runtime = e.runtime
            except ExecutionError as e:
                return result_class(
                    ProgramRunInfo(
                        params=run_params,
                        runtime=e.runtime,
                        error=ExceptionInfo.from_exception(e),
                    )
                )
            except AlgobattleBaseException as e:
                return result_class(
                    ProgramRunInfo(
                        params=run_params,
                        runtime=0,
                        error=ExceptionInfo.from_exception(e),
                    )
                )

            try:
                output_data = self._parse_output(io.output, max_size, input_instance)
            except AlgobattleBaseException as e:
                return result_class(
                    ProgramRunInfo(
                        params=run_params,
                        runtime=runtime,
                        error=ExceptionInfo.from_exception(e),
                    )
                )

            if battle_output:
                decoded_battle_output = battle_output.decode(io.output / "battle_data", max_size, self.role)
            else:
                decoded_battle_output = None

        if isinstance(output_data, _GenResData):
            return GeneratorResult(
                ProgramRunInfo(
                    params=run_params,
                    runtime=runtime,
                ),
                battle_data=decoded_battle_output,
                instance=output_data.problem,
                solution=output_data.solution,
            )
        else:
            return SolverResult(
                ProgramRunInfo(
                    params=run_params,
                    runtime=runtime,
                ),
                battle_data=decoded_battle_output,
                solution=output_data,
            )

    @inherit_docs
    def remove(self) -> None:
        self.image.remove()

    def __enter__(self):
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any):
        self.remove()


class Generator(Program):
    """A higher level interface for a team's generator."""

    role: ClassVar[Role] = Role.generator

    def _encode_input(self, input: Path, max_size: int, instance: Instance | None) -> None:
        assert instance is None
        with open(input / "max_size.txt", "w+") as f:
            f.write(str(max_size))

    def _parse_output(self, output: Path, max_size: int, instance: Instance | None) -> _GenResData:
        assert instance is None
        try:
            instance_ = self.problem.instance_cls.decode(output / "instance", max_size, self.role)
        except EncodingError:
            raise
        except Exception as e:
            raise EncodingError("Error thrown while decoding the problem instance.", detail=str(e)) from e
        if instance_.size > max_size:
            raise EncodingError("Instance is too large.", detail=f"Generated: {instance_.size}, maximum: {max_size}")
        try:
            instance_.validate_instance()
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError("Unknown error during instance validation.", detail=str(e)) from e

        if self.problem.with_solution:
            try:
                solution = self.problem.solution_cls.decode(output / "solution", max_size, self.role)
            except EncodingError:
                raise
            except Exception as e:
                raise EncodingError("Error thrown while decoding the solution.", detail=str(e)) from e
            try:
                solution.validate_solution(instance_, Role.generator)
            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError("Unknown error during solution validation.", detail=str(e)) from e
        else:
            solution = None
        return _GenResData(instance_, solution)

    async def run(
        self,
        max_size: int,
        *,
        timeout: float | None = ...,
        space: int | None = ...,
        cpus: int = ...,
        battle_input: Encodable | None = None,
        battle_output: type[Encodable] | None = None,
        set_cpus: str | None = None,
        ui: ProgramUiProxy | None = None,
    ) -> GeneratorResult:
        """Executes the generator and parses its output into a problem instance.

        Args:
            max_size: Maximum size of the instance that the generator is allowed to generate.
            timeout: Timeout in seconds.
            space: Memory limit in MB.
            cpus: Number of physical cpus the generator can use.
            battle_input: Additional data that will be given to the generator.
            battle_output: Class that will be used to parse additional data the generator outputs.
            set_cpus: Which cpus to execute the container on. Either a comma separated list or a hyphen-separated range.
                A value of `None` means the container can use any core (but still only `cpus` many of them).
            ui: Interface the program execution uses to update the ui.

        Returns:
            Datastructure containing all info about the generator execution and the created problem instance.
        """
        return cast(
            GeneratorResult,
            await self._run(
                max_size=max_size,
                input_instance=None,
                timeout=timeout,
                space=space,
                cpus=cpus,
                battle_input=battle_input,
                battle_output=battle_output,
                set_cpus=set_cpus,
                ui=ui,
            ),
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
        timeout: float | None = ...,
        space: int | None = ...,
        cpus: int = ...,
        battle_input: Encodable | None = None,
        battle_output: type[Encodable] | None = None,
        set_cpus: str | None = None,
        ui: ProgramUiProxy | None = None,
    ) -> SolverResult:
        """Executes the solver on the given problem instance and parses its output into a problem solution.

        Args:
            max_size: Maximum size of the instance that the generator is allowed to generate.
            timeout: Timeout in seconds.
            space: Memory limit in MB.
            cpus: Number of physical cpus the solver can use.
            battle_input: Additional data that will be given to the solver.
            battle_output: Class that will be used to parse additional data the solver outputs.
            set_cpus: Which cpus to execute the container on. Either a comma separated list or a hyphen-separated range.
                A value of `None` means the container can use any core (but still only `cpus` many of them).
            ui: Interface the program execution uses to update the ui.

        Returns:
            Datastructure containing all info about the solver execution and the solution it computed.
        """
        return cast(
            SolverResult,
            await self._run(
                max_size=max_size,
                input_instance=instance,
                timeout=timeout,
                space=space,
                cpus=cpus,
                battle_input=battle_input,
                battle_output=battle_output,
                set_cpus=set_cpus,
                ui=ui,
            ),
        )
