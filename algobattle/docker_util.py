"""Module providing an interface to interact with the teams' programs."""
from abc import ABC, abstractmethod
from pathlib import Path
from timeit import default_timer
from typing import Any, ClassVar, Iterator, Protocol, Self, TypedDict, cast
from uuid import uuid4
import json
from dataclasses import dataclass

from docker import DockerClient
from docker.errors import APIError, BuildError as DockerBuildError, DockerException, ImageNotFound
from docker.models.images import Image as DockerImage
from docker.models.containers import Container as DockerContainer
from docker.types import Mount, LogConfig, Ulimit
from requests import Timeout, ConnectionError
from pydantic import Field
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
    TempDir,
    inherit_docs,
    BaseModel,
)
from algobattle.problem import Problem


_client_var: DockerClient | None = None


class RunParameters(BaseModel):
    """The parameters determining how a program is run."""

    timeout: float | None = 30
    space: int | None = None
    cpus: int = 1


class DockerConfig(BaseModel):
    """Config options relevant to the way programs are run and built."""

    build_timeout: float | None = None
    set_cpus: str | list[str] | None = None
    generator: RunParameters = RunParameters()
    solver: RunParameters = RunParameters()
    advanced_run_params: "AdvancedRunArgs | None" = None
    advanced_build_params: "AdvancedBuildArgs | None" = None


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


class ProgramUiProxy(Protocol):
    """Provides an interface for :cls:`Program`s to update the Ui."""

    @abstractmethod
    def start(self, timeout: float | None) -> None:
        """Signals that the program execution has been started."""

    @abstractmethod
    def stop(self, runtime: float) -> None:
        """Signals that the program execution has been finished."""


@dataclass
class Image:
    """Class defining a docker image.

    Instances may outlive the actual docker images in the daemon!
    To prevent this don't use the object after calling `.remove()`.
    """

    id: str
    path: Path

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
    }
    """Advanced docker options passed to the docker build command.

    A full description can be found at the docker api reference."""

    @classmethod
    def _build_image(cls, path: str, timeout: float | None, dockerfile: str | None) -> DockerImage:
        image, _logs = cast(
            tuple[DockerImage, Iterator[Any]],
            client().images.build(
                path=str(path),
                tag=f"algobattle_{uuid4().hex[:8]}",
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
        timeout: float | None = None,
    ) -> Self:
        """Builds a docker image using the dockerfile found at the provided path.

        Args:
            path: The path to the directory containing a `Dockerfile`, or a path to such a file itself.
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
            image = await run_sync(cls._build_image, str(path), timeout, dockerfile)

        except Timeout as e:
            raise BuildError(f"Build ran into a timeout.") from e
        except DockerBuildError as e:
            raise BuildError(f"Build did not complete successfully.", detail=e.msg) from e
        except APIError as e:
            raise BuildError(f"Docker APIError thrown while building.", detail=str(e)) from e

        return cls(cast(str, image.id), path=path)

    def __enter__(self):
        return self

    def __exit__(self, _type, _value_, _traceback):
        self.remove()

    async def run(
        self,
        input_dir: Path | None = None,
        output_dir: Path | None = None,
        *,
        timeout: float | None = None,
        memory: int | None = None,
        cpus: int = 1,
        set_cpus: str | None = None,
        ui: ProgramUiProxy | None = None,
    ) -> float:
        """Runs a docker image.

        Args:
            input_dir: Path to a directory containing input data for the container.
            output_dir: Path to a directory where the container will place output data.
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

        mounts = []
        if input_dir is not None:
            mounts.append(Mount(target="/input", source=str(input_dir), type="bind", read_only=True))
        if output_dir is not None:
            mounts.append(Mount(target="/output", source=str(output_dir), type="bind"))

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
                    mounts=mounts,
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
            raise RuntimeError(f"Image (id: {self.id}) does not exist.") from e
        except APIError as e:
            raise DockerError(f"Docker APIError thrown while running container.", detail=str(e)) from e
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except APIError as e:
                    raise DockerError(f"Couldn't remove container.", detail=str(e)) from e

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
            raise DockerError(f"Docker APIError thrown while removing image.", detail=str(e)) from e

    def _run_container(self, container: DockerContainer, timeout: float | None = None) -> float:
        container.start()
        start_time = default_timer()
        elapsed_time = 0
        try:
            response = container.wait(timeout=timeout)
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

    instance: Problem | None = None
    solution: Problem.Solution | None = None


@dataclass
class SolverResult(ProgramResult):
    """Result of a single solver execution."""

    solution: Problem.Solution | None = None


@dataclass
class _GenResData:
    problem: Problem
    solution: Problem.Solution | None


@dataclass
class Program(ABC):
    """A higher level interface for a team's programs."""

    image: Image
    """The underlying docker image."""
    config: RunParameters
    """The default config options this program will be executed with."""
    problem_class: type[Problem]
    """The problem this program creates instances and/or solutions for."""

    role: ClassVar[Role]

    @classmethod
    async def build(
        cls,
        image: Path | Image,
        problem_class: type[Problem],
        config: RunParameters,
        timeout: float | None = None,
    ) -> Self:
        """Creates a program by building the specified docker image."""
        if isinstance(image, Path):
            image = await Image.build(
                path=image,
                timeout=timeout,
            )

        return cls(image, config, problem_class)

    @abstractmethod
    def _encode_input(self, input: Path, output: Path, size: int, instance: Problem | None) -> None:
        """Sets up the i/o folders as required for the specific type of program."""
        raise NotImplementedError

    @abstractmethod
    def _parse_output(self, output: Path, size: int, instance: Problem | None) -> _GenResData | Problem.Solution:
        """Parses the data in the output folder into problem instances/solutions."""
        raise NotImplementedError

    async def _run(
        self,
        size: int,
        input_instance: Problem | None = None,
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
        result_class = GeneratorResult if self.role == "generator" else SolverResult

        with TempDir() as input, TempDir() as output:
            try:
                self._encode_input(input, output, size, input_instance)
            except AlgobattleBaseException as e:
                return result_class(ProgramRunInfo(params=run_params, runtime=0, error=ExceptionInfo.from_exception(e)))
            with open(input / "info.json", "w+") as f:
                json.dump(
                    {
                        "size": size,
                        "timeout": timeout,
                        "space": space,
                        "cpus": cpus,
                    },
                    f,
                )
            if battle_input is not None:
                try:
                    battle_input.encode(input / "battle_data", size, self.role)
                except Exception as e:
                    return result_class(
                        ProgramRunInfo(
                            params=run_params,
                            runtime=0,
                            error=ExceptionInfo(type="EncodingError", message=f"Battle data couldn't be encoded:\n{e}"),
                        )
                    )

            try:
                runtime = await self.image.run(
                    input, output, timeout=timeout, memory=space, cpus=cpus, ui=ui, set_cpus=set_cpus
                )
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
                output_data = self._parse_output(output, size, input_instance)
            except AlgobattleBaseException as e:
                return result_class(
                    ProgramRunInfo(
                        params=run_params,
                        runtime=runtime,
                        error=ExceptionInfo.from_exception(e),
                    )
                )

            if battle_output:
                decoded_battle_output = battle_output.decode(output / "battle_data", size, self.role)
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

    def __exit__(self, _type, _value_, _traceback):
        self.remove()


class Generator(Program):
    """A higher level interface for a team's generator."""

    role: ClassVar[Role] = "generator"

    def _encode_input(self, input: Path, output: Path, size: int, instance: Problem | None) -> None:
        assert instance is None
        with open(input / "size.txt", "w+") as f:
            f.write(str(size))

    def _parse_output(self, output: Path, size: int, instance: Problem | None) -> _GenResData:
        assert instance is None
        try:
            problem = self.problem_class.decode(output / "instance", size, self.role)
        except EncodingError:
            raise
        except Exception as e:
            raise EncodingError("Error thrown while decoding the problem instance.", detail=str(e)) from e
        try:
            problem.validate_instance(size)
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError("Unknown error during instance validation.", detail=str(e)) from e

        if problem.with_solution:
            try:
                solution = problem.Solution.decode(output / "solution", size, self.role)
            except EncodingError:
                raise
            except Exception as e:
                raise EncodingError("Error thrown while decoding the solution.", detail=str(e)) from e
            try:
                solution.validate_solution(problem, size)
            except ValidationError:
                raise
            except Exception as e:
                raise ValidationError("Unknown error during solution validation.", detail=str(e)) from e
        else:
            solution = None
        return _GenResData(problem, solution)

    async def run(
        self,
        size: int,
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
            size: Size of the instance that the generator will be asked to generate.
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
                size=size,
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

    role: ClassVar[Role] = "solver"

    def _encode_input(self, input: Path, output: Path, size: int, instance: Problem | None) -> None:
        assert instance is not None
        instance.encode(input / "instance", size, self.role)

    def _parse_output(self, output: Path, size: int, instance: Problem | None) -> Problem.Solution:
        assert instance is not None
        try:
            solution = self.problem_class.Solution.decode(output / "solution", size, self.role)
        except EncodingError:
            raise
        except Exception as e:
            raise EncodingError("Error thrown while decoding the solution.", detail=str(e)) from e
        try:
            solution.validate_solution(instance, size)
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError("Unknown error during solution validation.", detail=str(e)) from e
        return solution

    async def run(
        self,
        instance: Problem,
        size: int,
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
            size: Size of the instance that the solver will be asked to generate.
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
                size=size,
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
        kwargs = self.dict(exclude_none=True)
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
    pull: bool | None = None
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
        return self.dict(exclude_none=True)


DockerConfig.update_forward_refs()
