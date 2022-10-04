"""Leightweight wrapper around docker functionality."""
from __future__ import annotations
import logging
from pathlib import Path
from time import sleep
from timeit import default_timer
from typing import Any, Iterator, cast
from uuid import uuid1
from dataclasses import dataclass
from docker import DockerClient
from docker.errors import APIError, BuildError, DockerException, ImageNotFound
from docker.models.images import Image as DockerImage
from docker.models.containers import Container as DockerContainer
from requests import Timeout

from algobattle.util import archive, extract


logger = logging.getLogger("algobattle.docker")


_client_var: DockerClient | None = None
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


class DockerError(Exception):
    """Error type for any issue during the execution of a docker command.

    The only error raised by any function in the docker module.
    """

    def __init__(self, message: str = "", level: int = logging.WARNING, *args: object) -> None:
        logger.log(level=level, msg=message)
        super().__init__(message, *args)


@dataclass
class DockerConfig:
    """Specifies settings relevant for the building and execution of docker images/containers."""

    timeout_build: float | None = None
    timeout_generator: float | None = None
    timeout_solver: float | None = None
    space_generator: int | None = None
    space_solver: int | None = None
    cpus: int | None = None


class Image:
    """Class defining a docker image.

    Instances may outlive the actual docker images in the daemon!
    To prevent this don't use the object after calling `.remove()`.
    """

    def __init__(
        self,
        path: Path,
        image_name: str,
        description: str | None = None,
        timeout: float | None = None,
    ) -> None:
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
            raise DockerError(f"Error when building {image_name}: '{path}' does not exist on the file system.")
        logger.debug(f"Building docker container with options: {path = !s}, {image_name = }, {timeout = }")
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
                ),
            )
            if old_image is not None:
                old_image.reload()
                if len(old_image.tags) == 0:
                    old_image.remove(force=True)

        except Timeout as e:
            raise DockerError(f"Build process for '{path}' ran into a timeout!") from e
        except BuildError as e:
            raise DockerError(f"Building '{path}' did not complete successfully:\n{e.msg}") from e
        except APIError as e:
            raise DockerError(f"Docker APIError thrown while building '{path}':\n{e}") from e

        self.name = image_name
        self.id = cast(str, image.id)
        self.description = description if description is not None else image_name

    def __enter__(self):
        return self

    def __exit__(self, _type, _value_, _traceback):
        self.remove()

    def run(
        self, input: str = "", timeout: float | None = None, memory: int | None = None, cpus: int | None = None
    ) -> str:
        """Runs a docker image with the provided input and returns its output.

        Parameters
        ----------
        input
            The input string the container will be provided with.
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

        container: DockerContainer | None = None
        try:
            container = cast(DockerContainer, client().containers.create(
                image=self.id,
                name=name,
                mem_limit=memory,
                nano_cpus=cpus,
                detach=True,
                network_mode="none",
            ))
            ok = container.put_archive("/", archive(input, "input"))
            if not ok:
                raise DockerError(f"Copying input into container {self.name} failed")

            container.start()
            start_time = default_timer()
            while container.reload() or container.status == "running":
                if timeout is not None and default_timer() - start_time > timeout:
                    logger.warning(f"{self.description} exceeded time limit!")
                    container.kill()
                    break
                sleep(0.01)
            elapsed_time = round(default_timer() - start_time, 2)

            if exit_code := cast(dict, container.attrs)["State"]["ExitCode"] != 0:
                raise DockerError(f"{self.description} exited with error code: {exit_code}")
            output_iter, _stat = container.get_archive("output")
            output = extract(b"".join(output_iter), "output")

        except ImageNotFound as e:
            raise DockerError(f"Image {self.name} (id={self.id}) does not exist") from e
        except APIError as e:
            if cast(str, e.explanation).startswith("Could not find the file output in container"):
                return ""
            raise DockerError(f"Docker API Error thrown while running {self.name}") from e
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except APIError as e:
                    raise DockerError(f"Couldn't remove {name}") from e

        logger.debug(f"Approximate elapsed runtime: {elapsed_time}/{timeout} seconds.")
        return output

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

        except APIError as e:
            raise DockerError(f"Docker APIError thrown while removing '{self.name}'") from e
