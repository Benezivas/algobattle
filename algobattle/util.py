"""Collection of utility functions."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from traceback import format_exception
from typing import Any, ClassVar, Iterable, Literal, Mapping, TypeVar, Self

from pydantic import BaseConfig, BaseModel, Extra


Role = Literal["generator", "solver"]


T = TypeVar("T")


def str_with_traceback(exception: Exception) -> str:
    """Returns the full exception info with a stacktrace."""
    return "\n".join(format_exception(exception))


class BaseModel(BaseModel):
    """Base class for all pydantic models."""

    class Config(BaseConfig):
        """Base config for all pydandic configs."""

        extra = Extra.forbid
        underscore_attrs_are_private = False


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


def getattr_set(o: object, *attrs: str) -> dict[str, Any]:
    """Returns a dict of the given attributes and their values, if they are not `None`."""
    return {a: getattr(o, a) for a in attrs if getattr(o, a, None) is not None}


class TempDir(TemporaryDirectory[Any]):
    """A :cls:`TemporaryDirecroty`, but it's enter returns a :cls:`Path`."""

    def __enter__(self):
        super().__enter__()
        return Path(self.name)


class Encodable(ABC):
    """Represents data that docker containers can interact with."""

    @classmethod
    @abstractmethod
    def decode(cls: type[Self], source_dir: Path, size: int, team: Role) -> Self:
        """Parses the container output into a python object."""
        raise NotImplementedError

    @abstractmethod
    def encode(self, target_dir: Path, size: int, team: Role) -> None:
        """Encodes the data into files that can be passed to docker containers."""
        raise NotImplementedError


class EncodableModel(BaseModel, Encodable, ABC):
    """Problem data that can easily be encoded into and decoded from json files."""

    filename: ClassVar[str]

    @inherit_docs
    @classmethod
    def decode(cls: type[Self], source_dir: Path, size: int, team: Role) -> Self:
        return cls.parse_file(source_dir / cls.filename)

    @inherit_docs
    def encode(self, target_dir: Path, size: int, team: Role) -> None:
        with open(target_dir / self.filename, "w") as f:
            f.write(self.json(exclude=self._excludes(team)))

    def _excludes(self, team: Role) -> dict[str | int, Any]:
        excludes = {}
        for name, field in self.__fields__.items():
            hidden = field.field_info.extra.get("hidden", False)
            if (isinstance(hidden, str) and hidden == team) or (isinstance(hidden, bool) and hidden):
                excludes[name] = True
            elif isinstance(getattr(self, name, None), EncodableModel):
                excludes[name] = getattr(self, name)._excludes(team)
        return excludes


@dataclass
class TimerInfo:
    """Basic data holding info on a timer."""

    start: datetime
    timeout: float | None


def flat_intersperse(iterable: Iterable[Iterable[T]], element: T) -> Iterable[T]:
    """Inserts `element` between each iterator in `iterable`."""
    iterator = iter(iterable)
    yield from next(iterator)
    for item in iterator:
        yield element
        yield from item
