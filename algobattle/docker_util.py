"""Leightweight wrapper around docker functionality."""
from abc import ABC, abstractmethod
from pathlib import Path
from timeit import default_timer
from typing import Any, ClassVar, Iterator, Literal, Mapping, Protocol, Self, TypedDict, cast
from uuid import uuid1
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

from algobattle.util import Encodable, Role, TempDir, encode, decode, inherit_docs, BaseModel
from algobattle.problem import Problem


_client_var: DockerClient | None = None


class RunParameters(BaseModel):
    """The parameters determining how a container is run."""

    timeout: float | None = 30
    space: int | None = None
    cpus: int = 1


class DockerConfig(BaseModel):
    """Grouped config options that are relevant to the interaction with docker."""

    build_timeout: float | None = None
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


def get_os_type() -> Literal["linux", "windows"]:
    """OS running inside docker containers."""
    return client().info()["OSType"]


class BuildError(Exception):
    """Indicates that the build process could not be completed successfully."""


class ProgramError(Exception):
    """Parent class for exceptions raised during the execution of a program."""

    def __init__(self, message: str, *args: object) -> None:
        self.message = message
        super().__init__(*args)

    def __str__(self) -> str:
        return f"{self.__class__.__name__}: {self.message}"


class ExecutionError(ProgramError):
    """Indicates that the program could not be executed successfully."""

    def __init__(self, message: str, runtime: float, *args: object) -> None:
        self.runtime = runtime
        super().__init__(message, *args)


class ExecutionTimeout(ExecutionError):
    """Indicates that the program ran into the timeout."""


class EncodingError(ProgramError):
    """Indicates that the given data could not be encoded or decoded properly."""

    def __init__(self, message: str = "", *args: object) -> None:
        super().__init__(message, *args)


class DockerError(ProgramError, BuildError):
    """Indicates that an issue with the docker daemon occured."""


class ProgramUiProxy(Protocol):
    """Provides an interface for :cls:`Program`s to update the Ui."""

    @abstractmethod
    def start(self, timeout: float | None) -> None:
        """Signals that the program execution has been started."""

    @abstractmethod
    def stop(self, runtime: float) -> None:
        """Signals that the program execution has been finished."""


@dataclass
class ArchivedImage:
    """Defines an archived docker image."""

    path: Path
    name: str
    id: str
    description: str

    def restore(self) -> "Image":
        """Restores a docker image from an archive."""
        try:
            with open(self.path, "rb") as file:
                data = file.read()
            images = cast(list[DockerImage], client().images.load(data))
            if self.id not in (i.id for i in images):
                raise KeyError
            self.path.unlink()
        except APIError as e:
            raise DockerError(f"Docker APIError thrown while restoring '{self.name}'") from e
        return Image(self.name, self.id, self.description, path=self.path)


@dataclass
class Image:
    """Class defining a docker image.

    Instances may outlive the actual docker images in the daemon!
    To prevent this don't use the object after calling `.remove()`.
    """

    name: str
    id: str
    description: str
    path: Path

    run_kwargs: ClassVar[dict[str, Any]] = {
        "network_mode": "none",
    }
    build_kwargs: ClassVar[dict[str, Any]] = {
        "rm": True,
        "forcerm": True,
        "quiet": True,
        "network_mode": "host",
    }

    @classmethod
    def build(
        cls,
        path: Path,
        image_name: str,
        description: str | None = None,
        timeout: float | None = None,
        *,
        dockerfile: str | None = None,
    ) -> Self:
        """Constructs the python Image object and uses the docker daemon to build the image.

        Parameters
        ----------
        path
            Path to folder containing the Dockerfile
        image_name
            Name of the image, used both internally and for the docker image name.
        description
            Optional description for the image, defaults to `image_name`
        timeout
            Build timeout in seconds, raises DockerError if exceeded.

        Raises
        ------
        DockerError
            On almost all common issues that might happen during the build, including timeouts, syntax errors,
            OS errors, and errors thrown by the docker daemon.
        """
        if not path.exists():
            raise RuntimeError
        if path.is_file():
            if dockerfile is not None:
                raise RuntimeError
            dockerfile = path.name
            path = path.parent
        try:
            try:
                old_image = cast(DockerImage, client().images.get(image_name))
            except ImageNotFound:
                old_image = None
            image, _logs = cast(
                tuple[DockerImage, Iterator[Any]],
                client().images.build(
                    path=str(path),
                    tag=image_name,
                    timeout=timeout,
                    dockerfile=dockerfile,
                    **cls.build_kwargs,
                ),
            )
            if old_image is not None:
                old_image.reload()
                if len(old_image.tags) == 0:
                    old_image.remove(force=True)

        except Timeout as e:
            raise BuildError(f"Build process for '{path}' ran into a timeout!") from e
        except DockerBuildError as e:
            raise BuildError(f"Building '{path}' did not complete successfully:\n{e.msg}") from e
        except APIError as e:
            raise DockerError(f"Docker APIError thrown while building '{path}':\n{e}") from e

        return cls(image_name, cast(str, image.id), description if description is not None else image_name, path=path)

    def __enter__(self):
        return self

    def __exit__(self, _type, _value_, _traceback):
        self.remove()

    async def run(
        self,
        input_dir: Path | None = None,
        output_dir: Path | None = None,
        timeout: float | None = None,
        memory: int | None = None,
        cpus: int = 1,
        *,
        size: int = 0,
        ui: ProgramUiProxy | None = None,
    ) -> float:
        """Runs a docker image with the provided input and returns its output.

        Parameters
        ----------
        input_dir
            The input folder provided to the docker container.
        input_dir
            The folder where the container places its output.
        timeout
            Timeout in seconds.
        memory
            Maximum memory the container will be allocated in MB.
        cpus
            Number of cpus the container will be allocated.

        Returns
        -------
        Output string of the container.

        Raises
        ------
        DockerError
            On almost all common issues that might happen during the execution, including syntax errors,
            OS errors, and errors thrown by the docker daemon.

        """
        name = f"algobattle_{uuid1().hex[:8]}"
        if memory is not None:
            memory = int(memory * 1000000)
        cpus = int(cpus * 1000000000)

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
                    **self.run_kwargs,
                ),
            )

            if ui is not None:
                ui.start(timeout)
            elapsed_time = await run_sync(self._run_container, container, timeout)
            if ui is not None:
                ui.stop(elapsed_time)

        except ImageNotFound as e:
            raise RuntimeError(f"Image {self.name} (id={self.id}) does not exist") from e
        except APIError as e:
            raise DockerError(str(e)) from e
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except APIError as e:
                    raise DockerError(f"Couldn't remove {name}") from e

        return elapsed_time

    def remove(self) -> None:
        """Removes the image from the docker daemon.

        **This will not cause the python object to be deleted.** Attempting to run the image after it has been removed will
        cause runtime errors.
        Will not throw an error if the image has been removed already.

        Raises
        ------
        DockerError
            When removing the image fails
        """
        try:
            client().images.remove(image=self.id, force=True)
        except ImageNotFound:
            pass
        except APIError as e:
            raise DockerError(f"Docker APIError thrown while removing '{self.name}'") from e

    def archive(self, dir: Path) -> ArchivedImage:
        """Archives the image into a .tar file at the targeted directory."""
        path = dir / f"{self.name}-archive.tar"
        try:
            image = cast(DockerImage, client().images.get(self.name))
            with open(path, "wb") as file:
                for chunk in image.save(named=True):
                    file.write(chunk)
            image.remove(force=True)
        except APIError as e:
            raise DockerError(f"Docker APIError thrown while archiving '{self.name}'") from e
        return ArchivedImage(path, self.name, self.id, self.description)

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
                message = (
                    f"Program crashed with exit code {response['StatusCode']} and error message:\n{container.logs().decode()}"
                )
                raise ExecutionError(message, elapsed_time)
        except (Timeout, ConnectionError) as e:
            container.kill()
            elapsed_time = round(default_timer() - start_time, 2)
            if len(e.args) != 1 or not isinstance(e.args[0], ReadTimeoutError):
                raise
            raise ExecutionTimeout(f"{self.description} exceeded the time limit", elapsed_time)


@dataclass
class ProgramResult:
    """Result of a program execution."""

    result: "Any | Problem.Solution | ProgramError"
    runtime: float
    size: int
    params: RunParameters
    battle_data: dict[str, Encodable] | None = None


@dataclass
class GeneratorResult(ProgramResult):
    """Result of a single generator execution."""

    @dataclass
    class _Data:
        problem: Problem
        solution: Problem.Solution | None = None

    result: _Data | ProgramError


@dataclass
class SolverResult(ProgramResult):
    """Result of a single solver execution."""

    result: Problem.Solution | ProgramError


@dataclass
class Program(ABC):
    """A higher level interface for a team's programs."""

    image: Image
    config: RunParameters
    team_name: str
    problem_class: type[Problem]

    role: ClassVar[Role]

    @classmethod
    def build(
        cls,
        image: Path | Image | ArchivedImage,
        team_name: str,
        problem_class: type[Problem],
        config: RunParameters,
        timeout: float | None = None,
    ) -> Self:
        """Creates a program by building the specified docker image."""
        if isinstance(image, Path):
            image = Image.build(
                path=image,
                image_name=f"{cls.role}-{team_name}",
                description=f"{cls.role} for team {team_name}",
                timeout=timeout,
            )
        elif isinstance(image, ArchivedImage):
            image = image.restore()

        return cls(image, config, team_name, problem_class)

    @abstractmethod
    def _setup_folders(self, input: Path, output: Path, size: int, instance: Problem | None) -> None:
        raise NotImplementedError

    @abstractmethod
    def _parse_output(self, output: Path, size: int, instance: Problem | None) -> GeneratorResult._Data | Problem.Solution:
        raise NotImplementedError

    async def _run(
        self,
        size: int,
        input_instance: Problem | None = None,
        *,
        timeout: float | None = ...,
        space: int | None = ...,
        cpus: int = ...,
        battle_input: Mapping[str, Encodable] = {},
        battle_output: Mapping[str, type[Encodable]] = {},
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
                self._setup_folders(input, output, size, input_instance)
            except ProgramError as e:
                return result_class(e, 0, size, run_params)
            with open(input / "info.json", "w+") as f:
                json.dump(
                    {
                        "size": size,
                        "timeout": timeout,
                        "space": space,
                        "cpus": cpus,
                        "battle_input": {name: obj.__class__.__name__ for name, obj in battle_input.items()},
                        "battle_output": {name: cls.__name__ for name, cls in battle_output.items()},
                    },
                    f,
                )
            if battle_input:
                (input / "battle_data").mkdir()
                try:
                    encode(battle_input, input / "battle_data", size, self.role)
                except Exception as e:
                    return result_class(EncodingError(f"Battle data couldn't be encoded:\n{e}"), 0, size, run_params)
            if battle_output:
                (output / "battle_data").mkdir()

            try:
                runtime = await self.image.run(input, output, timeout=timeout, memory=space, cpus=cpus, ui=ui)
            except ExecutionError as e:
                return result_class(e, e.runtime, size, run_params)
            except ProgramError as e:
                return result_class(e, 0, size, run_params)

            try:
                output_data = self._parse_output(output, size, input_instance)
            except ProgramError as e:
                return result_class(e, runtime, size, run_params)

            if battle_output:
                decoded_battle_output = decode(battle_output, output / "battle_data", size, self.role)
            else:
                decoded_battle_output = None

        return result_class(output_data, runtime, size, run_params, decoded_battle_output)  # type: ignore

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

    def _setup_folders(self, input: Path, output: Path, size: int, instance: Problem | None) -> None:
        assert instance is None
        with open(input / "size", "w+") as f:
            f.write(str(size))
        (output / "instance").mkdir()
        if self.problem_class.with_solution:
            (output / "solution").mkdir()

    def _parse_output(self, output: Path, size: int, instance: Problem | None) -> GeneratorResult._Data:
        assert instance is None
        try:
            problem = self.problem_class.decode(output / "instance", size, self.role)
        except EncodingError:
            raise
        except Exception as e:
            raise EncodingError(f"The output of team {self.team_name}'s {self.role} can not be decoded properly!\n{e}") from e
        if not problem.is_valid(size):
            raise EncodingError(f"{self.role.capitalize()} of team {self.team_name} output an invalid instance!")

        if problem.with_solution:
            try:
                solution = problem.Solution.decode(output / "solution", size, self.role)
            except EncodingError:
                raise
            except Exception as e:
                raise EncodingError(f"The solution output of team {self.team_name}'s generator can not be decoded properly!\n{e}") from e
            if not solution.is_valid(problem, size):
                raise EncodingError(f"The generator of team {self.team_name} output an invalid solution!")
        else:
            solution = None
        return GeneratorResult._Data(problem, solution)

    async def run(
        self,
        size: int,
        *,
        timeout: float | None = ...,
        space: int | None = ...,
        cpus: int = ...,
        battle_input: Mapping[str, Encodable] = {},
        battle_output: Mapping[str, type[Encodable]] = {},
        ui: ProgramUiProxy | None = None,
    ) -> GeneratorResult:
        """Execute the generator, passing in the size and processing the created problem instance."""
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
                ui=ui,
            ),
        )


class Solver(Program):
    """A higher level interface for a team's solver."""

    role: ClassVar[Role] = "solver"

    def _setup_folders(self, input: Path, output: Path, size: int, instance: Problem | None) -> None:
        assert instance is not None
        (input / "instance").mkdir()
        instance.encode(input / "instance", size, self.role)
        (output / "solution").mkdir()

    def _parse_output(self, output: Path, size: int, instance: Problem | None) -> Problem.Solution:
        assert instance is not None
        try:
            solution = self.problem_class.Solution.decode(output / "solution", size, self.role)
        except EncodingError:
            raise
        except Exception as e:
            raise EncodingError(f"The output of team {self.team_name}'s {self.role} can not be decoded properly!\n{e}") from e
        if not solution.is_valid(instance, size):
            raise EncodingError(f"{self.role.capitalize()} of team {self.team_name} output an invalid solution!")
        return solution

    async def run(
        self,
        instance: Problem,
        size: int,
        *,
        timeout: float | None = ...,
        space: int | None = ...,
        cpus: int = ...,
        battle_input: Mapping[str, Encodable] = {},
        battle_output: Mapping[str, type[Encodable]] = {},
        ui: ProgramUiProxy | None = None,
    ) -> SolverResult:
        """Execute the solver, passing in the problem instance and processing the created solution."""
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
    cpuset_cpus: str | None = None
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
