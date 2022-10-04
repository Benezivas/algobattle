"""Collection of utility functions."""
from __future__ import annotations
from io import BytesIO
import logging
import importlib.util
import sys
from pathlib import Path
import tarfile

from algobattle.problem import Problem

logger = logging.getLogger('algobattle.util')


def import_problem_from_path(problem_path: Path) -> Problem:
    """Try to import and initialize a Problem object from a given path.

    Parameters
    ----------
    problem_path : Path
        Path in the file system to a problem folder.

    Returns
    -------
    Problem
        Returns an object of the problem.

    Raises
    ------
    ValueError
        If the path doesn't point to a file containing a valid problem.
    """
    if not (problem_path / "__init__.py").is_file():
        raise ValueError

    try:
        spec = importlib.util.spec_from_file_location("problem", problem_path / "__init__.py")
        assert spec is not None
        assert spec.loader is not None
        Problem = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = Problem
        spec.loader.exec_module(Problem)
        return Problem.Problem()
    except ImportError as e:
        logger.critical(f"Importing the given problem failed with the following exception: {e}")
        raise ValueError from e


def update_nested_dict(current_dict: dict, updates: dict) -> dict:
    """Update a nested dictionary with new data recursively.

    Parameters
    ----------
    current_dict : dict
        The dict to be updated.
    updates : dict
        The dict containing the updates

    Returns
    -------
    dict
        The updated dict.
    """
    for key, value in updates.items():
        if isinstance(value, dict):
            current_dict[key] = update_nested_dict(current_dict.get(key, {}), value)
        else:
            current_dict[key] = value
    return current_dict


def archive(input: str, filename: str) -> bytes:
    """Compresses a string into a tar archive."""
    encoded = input.encode()
    with BytesIO() as fh:
        with BytesIO(initial_bytes=encoded) as source, tarfile.open(fileobj=fh, mode="w") as tar:
            info = tarfile.TarInfo(filename)
            info.size = len(encoded)
            tar.addfile(info, source)
        fh.seek(0)
        return fh.getvalue()


def extract(archive: bytes, filename: str) -> str:
    """Retrieves the contents of a file from a tar archive."""
    with BytesIO(initial_bytes=archive) as fh, tarfile.open(fileobj=fh, mode="r") as tar:
        file = tar.extractfile(filename)
        assert file is not None
        with file as f:
            return f.read().decode()
