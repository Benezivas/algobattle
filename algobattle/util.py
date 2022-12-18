"""Collection of utility functions."""
from __future__ import annotations
from abc import ABC
from dataclasses import KW_ONLY, dataclass, field, fields
from io import BytesIO
import logging
import importlib.util
import sys
from pathlib import Path
import tarfile
from typing import Any, Callable, Generic, Literal, TypeVar, cast, get_type_hints

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


class _MISSING_TYPE:
    pass
MISSING = _MISSING_TYPE()

@dataclass
class _ArgSpec(Generic[T]):
    """Further details of an CLI argument."""
    default: T
    _: KW_ONLY
    extra_names: list[str] = field(default_factory=list)
    parser: Callable[[str], T] | _MISSING_TYPE = MISSING
    help: str | _MISSING_TYPE = MISSING


def ArgSpec(*, default: T | _MISSING_TYPE = MISSING, extra_names: list[str] | None = None, parser: Callable[[str], T] | _MISSING_TYPE = MISSING, help: str | _MISSING_TYPE = MISSING) -> T:
    if extra_names is None:
        extra_names = []
    return cast(T, _ArgSpec(default=default, extra_names=extra_names, parser=parser, help=help))


class CLIParsable(ABC):
    """Protocol for dataclass-like objects that can be parsed from the CLI."""

    __args__: dict[str, _ArgSpec[Any]]

    def __init_subclass__(cls) -> None:
        args = {}
        for name, _type in get_type_hints(cls).items():
            if name.startswith("__") and name.endswith("__"):
                continue
            if not hasattr(cls, name):
                raise ValueError(f"CLIParsable class {cls} has no default value specified for field {name}!")
            default_val = getattr(cls, name)
            if isinstance(default_val, _ArgSpec):
                if default_val.parser is MISSING:
                    default_val.parser = _type
                args[name] = default_val
                setattr(cls, name, default_val.default)
            else:
                args[name] = _ArgSpec(default=default_val, parser=_type)
        cls.__args__ = args
        return super().__init_subclass__()

    @classmethod
    def _argspec(cls, name: str) -> _ArgSpec[Any]:
        for c in cls.__mro__:
            if name in getattr(c, "__args__", {}):
                return getattr(c, "__args__")[name]
        raise ValueError

    @classmethod
    def as_argparse_args(cls) -> list[tuple[list[str], dict[str, Any]]]:
        """Constructs a list of `*args` and `**kwargs` that can be passed to `ArgumentParser.add_argument()`."""
        arguments = []
        for field in fields(cls):
            arg_spec = cls._argspec(field.name)
            args = [f"--{field.name}"] + arg_spec.extra_names
            kwargs = {
                "type": arg_spec.parser,
                "default": arg_spec.default,
            }
            if arg_spec.help is not MISSING:
                kwargs["help"] = arg_spec.help
            if field.type == bool:
                if arg_spec.default == True:
                    kwargs["action"] = "store_true"
                elif arg_spec.default == False:
                    kwargs["action"] = "store_false"
            elif field.type == Literal:
                kwargs["choices"] = list(cls.__annotations__[field.name].__args__)

            arguments.append((args, kwargs))
        return arguments
