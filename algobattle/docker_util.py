"""Leightweight wrapper around docker functionality."""
from abc import ABC
import logging
from pathlib import Path
from timeit import default_timer
from typing import Any, ClassVar, Iterator, Literal, Mapping, Self, TypedDict, cast
from uuid import uuid1
import json
from dataclasses import dataclass

from docker import DockerClient
from docker.errors import APIError, BuildError, DockerException, ImageNotFound
from docker.models.images import Image as DockerImage
from docker.models.containers import Container as DockerContainer
from docker.types import Mount, LogConfig, Ulimit
from requests import Timeout, ConnectionError
from pydantic import BaseModel, Field
from anyio.to_thread import run_sync

from algobattle.util import Encodable, Role, TempDir, encode, decode, inherit_docs
from algobattle.problem import Problem


logger = logging.getLogger("algobattle.docker")


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
        err = "Could not connect to the docker daemon. Is docker running?"
        logger.error(err)
        raise SystemExit(f"Exited algobattle: {err}")
    return _client_var


def get_os_type() -> Literal["linux", "windows"]:
    """OS running inside docker containers."""
    return client().info()["OSType"]


class DockerError(Exception):
    """Error type for any issue during the execution of a docker command.

    Parent class of all exceptions raised by functions in the docker module.
    """

    pass

class ExecutionError(DockerError):
    """Exception raised when the execution of a container fails."""

    def __init__(self, *args: object, runtime: float, exit_code: int, error_message: str) -> None:
        self.runtime = runtime
        self.exit_code = exit_code
        self.error_message = error_message
        super().__init__(runtime, *args)


class EncodingError(DockerError):
    """Indicates that the given data couldn't be encoded or decoded properly."""

    pass


class SemanticsError(DockerError):
    """Indicates that the parsed data is semantically incorrect."""

    pass


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
            logger.warning(f"Docker APIError thrown while restoring '{self.name}'")
            raise DockerError from e
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
            logger.warning(f"Error when building {image_name}: '{path}' does not exist on the file system.")
            raise DockerError
        if path.is_file():
            if dockerfile is not None:
                logger.warning(f"Error when building {image_name}: '{path}' refers to a file and 'dockerfile' is specified.")
                raise DockerError
            dockerfile = path.name
            path = path.parent
        logger.debug(f"Building docker image with options: {path = !s}, {image_name = }, {timeout = }")
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
            logger.warning(f"Build process for '{path}' ran into a timeout!")
            raise DockerError from e
        except BuildError as e:
            logger.warning(f"Building '{path}' did not complete successfully:\n{e.msg}")
            raise DockerError from e
        except APIError as e:
            logger.warning(f"Docker APIError thrown while building '{path}':\n{e}")
            raise DockerError from e

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
        cpus: int | None = None,
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
        if cpus is not None:
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

            elapsed_time = await run_sync(self._run_container, container, timeout)
            print(f"ELAPSED TIME: {elapsed_time}")

        except ImageNotFound as e:
            logger.warning(f"Image {self.name} (id={self.id}) does not exist")
            raise DockerError from e
        except APIError as e:
            logger.warning(f"Docker API Error thrown while running {self.name}")
            raise DockerError from e
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except APIError as e:
                    raise DockerError(f"Couldn't remove {name}") from e

        logger.debug(f"Approximate elapsed runtime: {elapsed_time}/{timeout} seconds.")
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
            print(f"A current time: {round(default_timer() - start_time, 2)}\n")
            response = container.wait(timeout=timeout)
            print(f"B current time: {round(default_timer() - start_time, 2)}\n")
            elapsed_time = round(default_timer() - start_time, 2)
            if response["StatusCode"] != 0:
                raise ExecutionError(runtime=elapsed_time, exit_code=response["StatusCode"], error_message=container.logs().decode())
        except (Timeout, ConnectionError) as e:
            print(f"C current time: {round(default_timer() - start_time, 2)}\n")
            container.kill()
            print(f"D current time: {round(default_timer() - start_time, 2)}\n")
            elapsed_time = round(default_timer() - start_time, 2)
            if len(e.args) == 0 or isinstance(e.args[0], Timeout):
                raise
            logger.warning(f"{self.description} exceeded time limit!")
        return elapsed_time

@dataclass
class GeneratorResult:
    """Result of a single generator or solver execution."""

    problem: Problem
    runtime: float
    solution: Problem.Solution | None = None
    battle_data: dict[str, Encodable] | None = None


@dataclass
class SolverResult:
    """Result of a single generator or solver execution."""

    solution: Problem.Solution
    runtime: float
    battle_data: dict[str, Encodable] | None = None


class Program(ABC):
    """A higher level interface for a team's programs."""

    role: Role
    data_role: Literal["instance", "solution"]

    def __init_subclass__(cls) -> None:
        cls.data_role = "instance" if cls.role == "generator" else "solution"
        return super().__init_subclass__()

    def __init__(
        self,
        image: Image,
        config: RunParameters,
        team_name: str,
        data_type: type[Problem] | type[Problem.Solution]
    ) -> None:
        # we can't take a ref to the Team object here since it won't be created til after the Programs
        self.image = image
        self.config = config
        self.team_name = team_name
        self.data_type = data_type
        super().__init__()

    @classmethod
    def build(
        cls,
        image: Path | Image | ArchivedImage,
        team_name: str,
        problem_type: type[Problem],
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

        if cls.role == "generator":
            data_type = problem_type
        else:
            data_type = problem_type.Solution
        return cls(image, config, team_name, data_type)

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
    ) -> Any:
        """Execute the program, processing input and output data."""
        set_params: dict[str, Any] = {}
        if timeout is Ellipsis:
            timeout = self.config.timeout
        else:
            set_params["timeout"] = timeout
        if space is Ellipsis:
            space = self.config.space
        else:
            set_params["space"] = space
        if cpus is Ellipsis:
            cpus = self.config.cpus
        else:
            set_params["cpus"] = cpus
        if self.role == "generator":
            param_msg = f" at size {size}"
        else:
            param_msg = ""
        if set_params:
            param_msg += " with parameters " + ", ".join(f"{k}: {v}" for k, v in set_params.items())
        logger.info(f"Running {self.role} of team {self.team_name}{param_msg}.")

        with TempDir() as input, TempDir() as output:
            if self.role == "generator":
                with open(input / "size", "w+") as f:
                    f.write(str(size))
            else:
                assert input_instance is not None
                (input / "instance").mkdir()
                try:
                    input_instance.encode(input / "instance", size, self.role)
                except Exception as e:
                    logger.critical("Problem instance couldn't be encoded into files!")
                    raise DockerError from e
            if battle_input:
                (input / "battle_data").mkdir()
                try:
                    encode(battle_input, input / "battle_data", size, self.role)
                except Exception as e:
                    logger.critical("Battle data couldn't be encoded into files!")
                    raise DockerError from e
            with open(input / "info.json", "w+") as f:
                json.dump({
                    "size": size,
                    "timeout": timeout,
                    "space": space,
                    "cpus": cpus,
                    "battle_input": {name: obj.__class__.__name__ for name, obj in battle_input.items()},
                    "battle_output": {name: cls.__name__ for name, cls in battle_output.items()},
                }, f)

            (output / self.data_role).mkdir()
            if issubclass(self.data_type, Problem) and self.data_type.with_solution:
                (output / "solution").mkdir()
            if battle_output:
                (output / "battle_data").mkdir()

            try:
                runtime = await self.image.run(input, output, timeout=timeout, memory=space, cpus=cpus)
            except ExecutionError as e:
                logger.warning(f"{self.role.capitalize()} of team {self.team_name} crashed!")
                logger.info(f"After {e.runtime:.2f}s, with exit code {e.exit_code} and error message:\n{e.error_message}")
                raise
            except DockerError:
                logger.warning(f"{self.role.capitalize()} of team {self.team_name} couldn't be executed successfully!")
                raise

            try:
                output_data = self.data_type.decode(output / self.data_role, size, self.role)
            except Exception as e:
                logger.warning(
                    f"The {self.data_role} output of team {self.team_name}'s {self.role} can not be decoded properly!"
                )
                raise EncodingError from e
            if self.role == "generator" and isinstance(output_data, Problem) and output_data.with_solution:
                try:
                    generator_solution = output_data.Solution.decode(output / "solution", size, self.role)
                except Exception as e:
                    logger.warning(
                        f"The solution output of team {self.team_name}'s generator can not be decoded properly!"
                    )
                    raise EncodingError from e
            else:
                generator_solution = None

            if battle_output:
                decoded_battle_output = decode(battle_output, output / "battle_data", size, self.role)
            else:
                decoded_battle_output = None

        if self.role == "generator":
            assert isinstance(output_data, Problem)
            is_valid = output_data.is_valid(size)
        else:
            assert isinstance(output_data, Problem.Solution)
            is_valid = output_data.is_valid(input_instance, size)

        if not is_valid:
            logger.warning(
                f"{self.role.capitalize()} of team {self.team_name} output an invalid {self.data_role}!"
            )
            raise SemanticsError

        if generator_solution is not None:
            is_valid = generator_solution.is_valid(output_data, size)
            if not is_valid:
                logger.warning(f"The generator of team {self.team_name} output an invalid solution!")
                raise SemanticsError

        logger.info(f"{self.role.capitalize()} of team {self.team_name} output a valid {self.data_role}.")
        if isinstance(output_data, Problem):
            return GeneratorResult(output_data, runtime, generator_solution, decoded_battle_output)
        else:
            return SolverResult(output_data, runtime, decoded_battle_output)

    @inherit_docs
    def remove(self) -> None:
        self.image.remove()

    def __enter__(self):
        return self

    def __exit__(self, _type, _value_, _traceback):
        self.remove()

class Generator(Program):
    """A higher level interface for a team's generator."""

    role = "generator"

    async def run(
        self,
        size: int,
        *,
        timeout: float | None = ...,
        space: int | None = ...,
        cpus: int = ...,
        battle_input: Mapping[str, Encodable] = {},
        battle_output: Mapping[str, type[Encodable]] = {},
    ) -> GeneratorResult:
        """Execute the generator, passing in the size and processing the created problem instance."""
        return await self._run(
            size=size,
            input_instance=None,
            timeout=timeout,
            space=space,
            cpus=cpus,
            battle_input=battle_input,
            battle_output=battle_output
        )


class Solver(Program):
    """A higher level interface for a team's solver."""

    role = "solver"

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
    ) -> SolverResult:
        """Execute the solver, passing in the problem instance and processing the created solution."""
        return await self._run(
            size=size,
            input_instance=instance,
            timeout=timeout,
            space=space,
            cpus=cpus,
            battle_input=battle_input,
            battle_output=battle_output
        )


class AdvancedRunArgs(BaseModel):
    """Advanced docker run options.

    Contains all options exposed on the python docker run api, except `device_requests`
    and those set by :meth:`Image.run` itself.
    """

    class BlockIOWeight(TypedDict):
        Path: str
        Weight: int

    class DeviceRate(TypedDict):
        Path: str
        Rate: int

    class HealthCheck(TypedDict):
        test: list[str] | str
        interval: int
        timeout: int
        retries: int
        start_period: int

    class LogConfigArgs(TypedDict):
        type: str
        conifg: dict[Any, Any]

    class UlimitArgs(TypedDict):
        name: str
        soft: int
        hard: int

    network_mode: str = "none"
    command: str | list[str] | None = None
    auto_remove: bool | None = None
    blkio_weight_device: list[BlockIOWeight] | None = None
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
    device_read_bps: list[DeviceRate] | None = None
    device_read_iops: list[DeviceRate] | None = None
    device_write_bps: list[DeviceRate] | None = None
    device_write_iops: list[DeviceRate] | None = None
    devices: list[str] | None = None
    dns: list[str] | None = None
    dns_opt: list[str] | None = None
    dns_search: list[str] | None = None
    domainname: str | list[str] | None = None
    entrypoint: str | list[str] | None = None
    environment: dict[str, str] | list[str] | None = None
    extra_hosts: dict[str, str] | None = None
    group_add: list[str] | None = None
    healthcheck: HealthCheck | None = None
    hostname: str | None = None
    init: bool | None = None
    init_path: str | None = None
    ipc_mode: str | None = None
    isolation: str | None = None
    kernel_memory: int | str | None = None
    labels: dict[str, str] | list[str] | None = None
    links: dict[str, str] | None = None
    log_config: LogConfigArgs | None = None
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
    ulimits: list[UlimitArgs] | None = None
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

    class ContainerLimits(TypedDict):
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
    container_limits: ContainerLimits | None = None
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
