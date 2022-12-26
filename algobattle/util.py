"""Collection of utility functions."""
from __future__ import annotations
from abc import ABC
from dataclasses import KW_ONLY, dataclass, fields
from io import BytesIO
import logging
import importlib.util
import sys
from pathlib import Path
import tarfile
from typing import Any, Callable, Generic, Literal, TypeVar, cast, get_type_hints

from algobattle.problem import Problem

logger = logging.getLogger("algobattle.util")


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


class FileArchive(dict[Path, bytes]):
    """A collection of in-memory files."""

    def archive(self) -> bytes:
        """Compress into a tar archive."""
        with BytesIO() as fh, tarfile.open(fileobj=fh, mode="w") as tar:
            for path, data in self.items():
                with BytesIO(initial_bytes=data) as source:
                    info = tarfile.TarInfo(str(path))
                    info.size = len(data)
                    tar.addfile(info, source)
            fh.seek(0)
            return fh.getvalue()

    @staticmethod
    def extract(data: bytes) -> FileArchive:
        """Retrieves the contents of a tar archive."""
        new = FileArchive()
        with BytesIO(initial_bytes=data) as fh, tarfile.open(fileobj=fh, mode="r") as tar:
            for info in tar.getmembers():
                file = tar.extractfile(info)
                if file is not None:
                    new[Path(info.path)] = file.read()
        return new

    def subfolder(self, subfolder: Path) -> FileArchive:
        """Creates a view at the files in a subfolder."""
        return FileArchive({path.relative_to(subfolder): data for path, data in self.items() if subfolder in path.parents})


T = TypeVar("T")


def inherit_docs(obj: T) -> T:
    """Decorator to mark a method as inheriting its docstring.

    Python 3.5+ already does this, but pydocstyle needs a static hint.
    """
    return obj


def check_path(path: str, *, type: Literal["file", "dir", "exists"] = "exists") -> Path:
    """Parses a string into a Path. Raises a :cls:`ValueError` if it doesn't exist as the specified type."""
    _path = Path(path)
    match type:
        case "file":
            test = _path.is_file
        case "dir":
            test = _path.is_dir
        case "exists":
            test = _path.exists
    if test():
        return _path
    else:
        raise ValueError


@dataclass
class _ArgSpec(Generic[T]):
    """Further details of an CLI argument."""

    default: T
    _: KW_ONLY
    alias: str | None = None
    parser: Callable[[str], T] | None = None
    help: str | None = None


def ArgSpec(default: T, *, alias: str | None = None, parser: Callable[[str], T] | None = None, help: str | None = None) -> T:
    """Structure specifying the CLI arg."""
    return cast(T, _ArgSpec(default=default, alias=alias, parser=parser, help=help))


class CLIParsable(ABC):
    """Protocol for dataclass-like objects that can be parsed from the CLI."""

    __args__: dict[str, _ArgSpec[Any]]

    def __init_subclass__(cls) -> None:
        args = {}
        for name, _type in get_type_hints(cls).items():
            if (name.startswith("__") and name.endswith("__")) or not hasattr(cls, name):
                continue
            default_val = getattr(cls, name)
            if isinstance(default_val, _ArgSpec):
                if default_val.parser is None:
                    default_val.parser = _type
                if default_val.alias is None:
                    default_val.alias = name
                args[name] = default_val
                setattr(cls, name, default_val.default)
        cls.__args__ = args
        return super().__init_subclass__()

    @classmethod
    def _argspec(cls, name: str) -> _ArgSpec[Any] | None:
        for c in cls.__mro__:
            if name in getattr(c, "__args__", {}):
                return getattr(c, "__args__")[name]
        return None

    @classmethod
    def as_argparse_args(cls) -> list[tuple[list[str], dict[str, Any]]]:
        """Constructs a list of `*args` and `**kwargs` that can be passed to `ArgumentParser.add_argument()`."""
        arguments = []
        for field in fields(cls):
            arg_spec = cls._argspec(field.name)
            if arg_spec is None:
                continue

            kwargs: dict[str, Any] = {
                "type": arg_spec.parser,
                "help": f"{arg_spec.help} Default: {arg_spec.default}"
                if arg_spec.help is not None
                else f"Default: {arg_spec.default}",
            }
            if field.type == bool:
                kwargs["action"] = "store_const"
                kwargs["const"] = not arg_spec.default
            elif field.type == Literal:
                kwargs["choices"] = cls.__annotations__[field.name].__args__

            arguments.append((arg_spec.alias, kwargs))
        return arguments


def getattr_set(o: object, *attrs: str) -> dict[str, Any]:
    """Returns a dict of the given attributes and their values, if they are not `None`."""
    return {a: getattr(o, a) for a in attrs if getattr(o, a, None) is not None}
