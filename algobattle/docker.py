"""Leightweight wrapper around docker functionality.
We are not using the Python Docker SDK lib since it does not provide needed
functionality like timeouts and windows support requires annoying workarounds atm.
"""

from __future__ import annotations
from dataclasses import dataclass
import logging
from subprocess import CalledProcessError, TimeoutExpired, run
from timeit import default_timer
from typing import Callable
from uuid import uuid1

import algobattle.problems.delaytest as DelaytestProblem


logger = logging.getLogger("algobattle.docker")

class DockerError(Exception):
    pass


def build(path: str,
        image_name: str = "",
        description: str = "",
        timeout: float | None = None,
        cache: bool = True,
        )-> Image:
    cmd = ["docker", "build", "-q", "--network=host"]
    if image_name is not None:
        cmd += ["-t", image_name]
    if not cache:
        cmd.append("--no-cache")
    cmd.append(path)
    
    logger.debug(f"Building docker container with the following command: {' '.join(cmd)}")
    try:
        result = run(cmd, capture_output=True, timeout=timeout, check=True, text=True)

    except TimeoutExpired as e:
        logger.error(f"Build process for '{path}' ran into a timeout!")
        raise DockerError from e

    except CalledProcessError as e:
        logger.warning(f"Building '{path}' did not complete successfully:\n{e.stderr}")
        raise DockerError from e

    except OSError as e:
        logger.warning(f"OSError thrown while building '{path}':\n{e}")
        raise DockerError from e

    except ValueError as e:
        logger.warning(f"Build process for '{path}' created with invalid arguments:\n{e}")
        raise DockerError from e

    return Image(image_name, result.stdout.strip()[7:], description)


_running_containers: set[tuple[Image, str]] = set()

@dataclass(frozen=True)
class Image:
    name: str
    id: str
    description: str

    def run(self,
            input: str | None = None,
            timeout: float | None = None,
            memory: int | None = None,
            cpus: int | None = None
            ) -> str:
        start_time = default_timer()
        name = f"algobattle_{uuid1().hex[:8]}"
        cmd = ["docker", "run", "--rm", "--network", "none", "-i", "--name", name]
        if memory is not None:
            cmd.append(f"-m={memory}mb")
        if cpus is not None:
            cmd.append(f"--cpus={cpus}")
        cmd.append(self.id)

        logger.debug(f"Running {self.description}.")
        _running_containers.add((self, name))
        try:
            result = run(cmd, input=input, capture_output=True, timeout=timeout, check=True, text=True)

        except TimeoutExpired as e:
            logger.warning(f"'{self.description}' exceeded time limit!")
            return ""

        except CalledProcessError as e:
            logger.warning(f"Running '{self.description}' did not complete successfully:\n{e.stderr}")
            raise DockerError from e

        except OSError as e:
            logger.warning(f"OSError thrown while running '{self.description}':\n{e}")
            raise DockerError from e

        except ValueError as e:
            logger.warning(f"Process '{self.description}' created with invalid arguments:\n{e}")
            raise DockerError from e
        
        finally:
            _kill_container(self, name)
        
        elapsed_time = round(default_timer() - start_time, 2)
        logger.debug(f'Approximate elapsed runtime: {elapsed_time}/{timeout} seconds.')

        return result.stdout

def _kill_container(image: Image, name: str) -> None:
    try:
        run(["docker", "kill", name], capture_output=True, check=True, text=True)
    except CalledProcessError as e:
        if e.stderr.find(f"No such container: {name}") == -1:
            logger.warning(f"Could not kill container '{image.description}':\n{e.stderr}")
    _running_containers.discard((image, name))

def kill_all_running_containers() -> None:
    for container in _running_containers.copy():
        _kill_container(*container)

def measure_runtime_overhead() -> float:
    """Calculate the I/O delay for starting and stopping docker on the host machine.

    Returns
    -------
    float
        I/O overhead in seconds, rounded to two decimal places.
    """

    delaytest_path = DelaytestProblem.__file__[:-12] + '/generator' # remove /__init__.py
    try:
        image = build(delaytest_path, "delaytest_generator", "delaytest generator", timeout=300)
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
    
    return round(max(overheads), 2)
 

def docker_running(function: Callable) -> Callable:
    """Ensure that internal methods are only callable if docker is running."""
    def wrapper(self, *args, **kwargs):
        try:
            run(["docker", "info"], capture_output=True, check=True, text=True)
        except CalledProcessError:
            logger.error("could not connect to the docker daemon. Is docker running?")
            raise DockerError
        return function(self, *args, **kwargs)
    return wrapper