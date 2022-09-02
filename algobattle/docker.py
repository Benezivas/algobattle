"""Leightweight wrapper around docker functionality.

We are not using the Python Docker SDK lib since it does not provide needed
functionality like timeouts and windows support requires annoying workarounds atm.
"""

from __future__ import annotations
import logging
import os
from pathlib import Path
from subprocess import CalledProcessError, TimeoutExpired, run
from timeit import default_timer
from uuid import uuid1
from dataclasses import dataclass
from signal import SIGTERM

import algobattle.problems.delaytest as DelaytestProblem


logger = logging.getLogger("algobattle.docker")

if os.name == "posix":
    _flag = 0
else:
    from subprocess import CREATE_NEW_PROCESS_GROUP
    from signal import CTRL_BREAK_EVENT
    _flag = CREATE_NEW_PROCESS_GROUP


class DockerError(Exception):
    """Error type for any issue during the execution of a docker command.

    The only error raised by any function in the docker module.
    """

    pass


@dataclass
class DockerConfig:
    """Specifies settings relevant for the building and execution of docker images/containers."""

    timeout_build: float | None = None
    timeout_generator: float | None = None
    timeout_solver: float | None = None
    space_generator: int | None = None
    space_solver: int | None = None
    cpus: int | None = None
    cache_containers: bool = True

    def add_overhead(self, overhead: float) -> None:
        """Adds some amount of runtime overhead to the timeouts."""
        def _map(f):
            return f if f is None else f + overhead

        self.timeout_build = _map(self.timeout_build)
        self.timeout_generator = _map(self.timeout_generator)
        self.timeout_solver = _map(self.timeout_solver)


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
        cache: bool = True,
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
        cache
            Unset to instruct docker to not cache the image build.

        Raises
        ------
        DockerError
            On almost all common issues that might happen during the build, including timeouts, syntax errors,
            OS errors, and errors thrown by the docker daemon.
        """
        cmd = ["docker", "build", "-q", "--network=host"]
        if image_name is not None:
            cmd += ["-t", image_name]
        if not cache:
            cmd.append("--no-cache")
        cmd.append(str(path))

        logger.debug(f"Building docker container with the following command: {' '.join(cmd)}")
        try:
            result = run(cmd, capture_output=True, timeout=timeout, check=True, text=True, creationflags=_flag)

        except TimeoutExpired as e:
            logger.error(f"Build process for '{path}' ran into a timeout!")
            raise DockerError from e

        except CalledProcessError as e:
            if e.stderr.find("error during connect") != -1:
                logger.error("Could not connect to the docker daemon. Is docker running?")
                raise SystemExit("Exited algobattle: Could not connect to the docker daemon. Is docker running?")

            logger.warning(f"Building '{path}' did not complete successfully:\n{e.stderr}")
            raise DockerError from e

        except OSError as e:
            logger.warning(f"OSError thrown while building '{path}':\n{e}")
            raise DockerError from e

        except ValueError as e:
            logger.warning(f"Build process for '{path}' created with invalid arguments:\n{e}")
            raise DockerError from e

        self.name = image_name
        self.id = result.stdout.strip()[7:]
        self.description = description if description is not None else image_name

    def run(
        self, input: str | None = None, timeout: float | None = None, memory: int | None = None, cpus: int | None = None
    ) -> str:
        """Runs a docker image with the provided input and returns its output.

        Parameters
        ----------
        input
            The input string the container will be provided with.
        timeout
            Timeout in seconds. Returns an empty output if exceeded.
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
        start_time = default_timer()
        name = f"algobattle_{uuid1().hex[:8]}"
        cmd = ["docker", "run", "--rm", "--network", "none", "-i", "--sig-proxy=true", "--name", name]
        if memory is not None:
            cmd.append(f"-m={memory}mb")
        if cpus is not None:
            cmd.append(f"--cpus={cpus}")
        cmd.append(self.id)

        result = None
        try:
            result = run(cmd, input=input, capture_output=True, timeout=timeout, check=True, text=True, creationflags=_flag)

        except TimeoutExpired:
            logger.warning(f"'{self.description}' exceeded time limit!")
            raise DockerError

        except CalledProcessError as e:
            if e.stderr.find("error during connect") != -1:
                logger.error("Could not connect to the docker daemon. Is docker running?")
                raise SystemExit("Exited algobattle: Could not connect to the docker daemon. Is docker running?")

            logger.warning(f"Running '{self.description}' did not complete successfully:\n{e.stderr}")
            raise DockerError from e

        except OSError as e:
            logger.warning(f"OSError thrown while running '{self.description}':\n{e}")
            raise DockerError from e

        except ValueError as e:
            logger.warning(f"Process '{self.description}' created with invalid arguments:\n{e}")
            raise DockerError from e

        finally:
            if result is None:
                _kill_container(self, name)
                if os.name == "posix":
                    try:
                        os.killpg(os.getpid(), SIGTERM)
                    except ProcessLookupError:
                        pass
                else:
                    os.kill(os.getpid(), CTRL_BREAK_EVENT)

        elapsed_time = round(default_timer() - start_time, 2)
        logger.debug(f"Approximate elapsed runtime: {elapsed_time}/{timeout} seconds.")

        return result.stdout  # type: ignore

    def remove(self) -> None:
        """Removes the image from the docker daemon.

        **This will not cause the python object to be deleted.** Attempting to run the image after it has been removed will
        cause runtime errors.
        Will not throw an error if the image has been removed already.

        Raises
        ------
        DockerError
            On almost all common issues that might happen during the execution, including syntax errors,
            OS errors, and errors thrown by the docker daemon.

        """
        cmd = ["docker", "image", "rm", "--no-prune", "-f", self.id]
        try:
            run(cmd, capture_output=True, check=True, text=True, creationflags=_flag)

        except CalledProcessError as e:
            if e.stderr.find("error during connect") != -1:
                logger.error("Could not connect to the docker daemon. Is docker running?")
                raise SystemExit("Exited algobattle: Could not connect to the docker daemon. Is docker running?")

            if e.stderr.find("No such image") == -1:
                logger.warning(f"Removing '{self.description}' did not complete successfully:\n{e.stderr}")

            raise DockerError from e

        except OSError as e:
            logger.warning(f"OSError thrown while trying to remove '{self.description}':\n{e}")
            raise DockerError from e

        except ValueError as e:
            logger.warning(f"Trying to remove '{self.description}' with invalid arguments:\n{e}")
            raise DockerError from e


def _kill_container(image: Image, name: str) -> None:
    """Kills a running container.

    Do not call this function if you didn't start the container,
    it's rather unsafe and may cause downstream errors.

    Parameters
    ----------
    image
        Image that the container was built from.
    name
        Name of the container, not of the image.
    """
    try:
        run(["docker", "kill", name], capture_output=True, check=True, text=True)

    except CalledProcessError as e:
        if e.stderr.find("error during connect") != -1:
            logger.error("Could not connect to the docker daemon. Is docker running?")
            raise SystemExit("Exited algobattle: Could not connect to the docker daemon. Is docker running?")

        if e.stderr.find(f"No such container: {name}") == -1 and e.stderr.find("is not running") == -1:
            logger.warning(f"Could not kill container '{image.description}':\n{e.stderr}")


def measure_runtime_overhead() -> float:
    """Calculate the I/O delay for starting and stopping docker on the host machine.

    Returns
    -------
    float
        I/O overhead in seconds, rounded to two decimal places.
    """
    delaytest_path = Path(DelaytestProblem.__file__).parent / "generator"
    try:
        image = Image(delaytest_path, "delaytest_generator", "delaytest generator", timeout=300)
    except DockerError:
        return 0

    overheads = []
    for i in range(5):
        try:
            start_time = default_timer()
            image.run(str(50 * i), timeout=300)
            overheads.append(default_timer() - start_time)
        except DockerError:
            overheads.append(300)
    image.remove()
    return round(max(overheads), 2)
