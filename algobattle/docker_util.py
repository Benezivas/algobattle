"""Leightweight wrapper around docker functionality."""
from __future__ import annotations
from abc import ABC
import logging
from pathlib import Path
from time import sleep
from timeit import default_timer
from typing import Any, Generic, Iterator, Literal, Mapping, Self, TypeVar, cast
from uuid import uuid1
import json
from dataclasses import dataclass
from docker import DockerClient
from docker.errors import APIError, BuildError, DockerException, ImageNotFound
from docker.models.images import Image as DockerImage
from docker.models.containers import Container as DockerContainer
from docker.types import Mount
from requests import Timeout
from algobattle.util import Encodable, CustomEncodable, Role, TempDir, encode, decode
from algobattle.problem import Problem


logger = logging.getLogger("algobattle.docker")


_client_var: DockerClient | None = None


@dataclass
class RunParameters:
    timeout: float | None = 30
    space: int | None = None
    cpus: int = 1


@dataclass
class DockerConfig:
    build_timeout: float | None = None
    generator: RunParameters = RunParameters()
    solver: RunParameters = RunParameters()


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

    def restore(self) -> Image:
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

    @classmethod
    def build(
        cls,
        path: Path,
        image_name: str,
        description: str | None = None,
        timeout: float | None = None,
        *,
        dockerfile: str | None = None,
    ) -> Image:
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
                    rm=True,
                    forcerm=True,
                    quiet=True,
                    network_mode="host",
                    dockerfile=dockerfile,
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

    def run(self, input_dir: Path | None = None, output_dir: Path | None = None, timeout: float | None = None, memory: int | None = None, cpus: int | None = None) -> float:
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
                    network_mode="none",
                    mounts=mounts,
                ),
            )

            container.start()
            start_time = default_timer()
            while container.reload() or container.status == "running":
                if timeout is not None and default_timer() - start_time > timeout:
                    logger.warning(f"{self.description} exceeded time limit!")
                    container.kill()
                    break
                sleep(0.01)
            elapsed_time = round(default_timer() - start_time, 2)

            if (exit_code := cast(dict[str, Any], container.attrs)["State"]["ExitCode"]) != 0:
                raise ExecutionError(runtime=elapsed_time, exit_code=exit_code, error_message=container.logs().decode())

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


T = TypeVar("T", bound=Encodable)


@dataclass
class Result(Generic[T]):
    """Result of a single generator or solver execution."""

    data: T
    runtime: float
    battle_data: dict[str, Encodable] | None


class Program(ABC):
    """A higher level interface for a team's programs."""

    role: Role
    data_role: Literal["instance", "solution"]

    def __init_subclass__(cls) -> None:
        cls.data_role = "instance" if cls.role == "generator" else "solution"
        return super().__init_subclass__()

    def __init__(self, image: Image, config: RunParameters, team_name: str, data_type: type[CustomEncodable]) -> None:
        self.image = image
        self.config = config
        self.team_name = team_name  # we can't take a ref to the Team object here since it won't be created til after the Programs
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

    def _run(self,
        size: int,
        input_instance: Problem | None = None,
        *,
        timeout: float | None = ...,
        space: int | None = ...,
        cpus: int = ...,
        battle_input: Mapping[str, Encodable] = {},
        battle_output: Mapping[str, type[Encodable]] = {},
        ) -> Result[Any]:
        """Execute the program, processing input and output data."""
        set_params: dict[str, Any] = {}
        if timeout is Ellipsis:
            timeout = self.config.timeout
            set_params["timeout"] = timeout
        if space is Ellipsis:
            space = self.config.space
            set_params["space"] = space
        if cpus is Ellipsis:
            cpus = self.config.cpus
            set_params["cpus"] = cpus
        if set_params:
            param_msg = "with parameters " + ", ".join(f"{k}: {v}" for k, v in set_params.items())
        else:
            param_msg = ""
        logger.debug(f"Running {self.role} of team {self.team_name} at size {size}{param_msg}.")

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
                    logger.critical(f"Problem instance couldn't be encoded into files!")
                    raise DockerError from e
            if battle_input:
                (input / "battle_data").mkdir()
                try:
                    encode(battle_input, input / "battle_data", size, self.role)
                except Exception as e:
                    logger.critical(f"Battle data couldn't be encoded into files!")
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
            if battle_output:
                (output / "battle_data").mkdir()

            try:
                runtime = self.image.run(input, output, timeout=timeout, memory=space, cpus=cpus)
            except ExecutionError as e:
                logger.warning(f"{self.role.capitalize()} of team {self.team_name} crashed!")
                logger.info(f"After {e.runtime:.2f}s, with exit code {e.exit_code} and error message:\n{e.error_message}")
                raise
            except DockerError as e:
                logger.warning(f"{self.role.capitalize()} of team {self.team_name} couldn't be executed successfully!")
                raise

            try:
                output_data = self.data_type.decode(output / "instance", size)
            except Exception as e:
                logger.warning(f"{self.role.capitalize()} of team {self.team_name} output a syntactically incorrect {self.data_role}!")
                raise EncodingError from e

            if battle_output:
                decoded_battle_output = decode(battle_output, output / "battle_data", size)
            else:
                decoded_battle_output = None

        if self.role == "generator":
            assert isinstance(output_data, Problem)
            correct_semantics = output_data.check_semantics(size)
        else:
            assert isinstance(output_data, Problem.Solution)
            correct_semantics = output_data.check_semantics(size, input_instance)
        
        if not correct_semantics:
            logger.warning(f"{self.role.capitalize()} of team {self.team_name} output a semantically incorrect {self.data_role}!")
            raise SemanticsError
        

        logger.info(f"{self.role.capitalize()} of team {self.team_name} output a valid {self.data_role}.")
        return Result(data=output_data, runtime=runtime, battle_data=decoded_battle_output)

    def remove(self) -> None:
        """Removes the underlying image from the docker daemon.

        **This will not cause the python object to be deleted.** Attempting to run the image after it has been removed will
        cause runtime errors.
        Will not throw an error if the image has been removed already.

        Raises
        ------
        DockerError
            When removing the image fails
        """
        self.image.remove()

    def __enter__(self):
        return self

    def __exit__(self, _type, _value_, _traceback):
        self.remove()

class Generator(Program):
    """A higher level interface for a team's generator."""

    role = "generator"

    def run(
        self,
        size: int,
        *,
        timeout: float | None = ...,
        space: int | None = ...,
        cpus: int = ...,
        battle_input: Mapping[str, Encodable] = {},
        battle_output: Mapping[str, type[Encodable]] = {},
        ) -> Result[Problem]:
        """Execute the generator, passing in the size and processing the created problem instance."""
        return self._run(
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

    role = "generator"

    def run(
        self,
        instance: Problem,
        size: int,
        *,
        timeout: float | None = ...,
        space: int | None = ...,
        cpus: int = ...,
        battle_input: Mapping[str, Encodable] = {},
        battle_output: Mapping[str, type[Encodable]] = {},
        ) -> Result[Problem.Solution]:
        """Execute the solver, passing in the problem instance and processing the created solution."""
        return self._run(
            size=size,
            input_instance=instance,
            timeout=timeout,
            space=space,
            cpus=cpus,
            battle_input=battle_input,
            battle_output=battle_output
        )
