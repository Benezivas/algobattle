"""Collection of utility functions."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, ClassVar, Literal, Protocol, TypeVar, dataclass_transform, get_origin, get_type_hints, Self
from pydantic import BaseModel


logger = logging.getLogger("algobattle.util")


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


def argspec(*, default: T, help: str = "", alias: str | None = None, parser: Callable[[str], T] | None = None) -> T:
    """Structure specifying the CLI arg."""
    metadata = {
        "help": help,
        "alias": alias,
        "parser": parser,
    }
    return field(default=default, metadata={key: val for key, val in metadata.items() if val is not None})


@dataclass_transform(field_specifiers=(argspec,))
class CLIParsable(Protocol):
    """Protocol for dataclass-like objects that can be parsed from the CLI."""

    def __init_subclass__(cls) -> None:
        dataclass(cls)
        super().__init_subclass__()

    def __init__(self, **kwargs) -> None:
        super().__init__()

    @classmethod
    def as_argparse_args(cls) -> list[tuple[list[str], dict[str, Any]]]:
        """Constructs a list of `*args` and `**kwargs` that can be passed to `ArgumentParser.add_argument()`."""
        arguments = []
        for field in fields(cls):
            kwargs = {
                "type": field.metadata.get("parser", field.type),
                "help": field.metadata.get("help", "") + f" Default: {field.default}",
            }
            if field.type == bool:
                kwargs["action"] = "store_const"
                kwargs["const"] = not field.default
            elif get_origin(field.type) == Literal:
                kwargs["choices"] = field.type.__args__

            arguments.append(([field.metadata.get("alias", field.name)], kwargs))
        return arguments


def getattr_set(o: object, *attrs: str) -> dict[str, Any]:
    """Returns a dict of the given attributes and their values, if they are not `None`."""
    return {a: getattr(o, a) for a in attrs if getattr(o, a, None) is not None}


class TempDir(TemporaryDirectory[Any]):
    
    def __enter__(self):
        super().__enter__()
        return Path(self.name)


class Encodable(Protocol):
    """Represents problem data that docker containers can interact with."""

    @abstractmethod
    @classmethod
    def decode(cls: type[Self], source_dir: Path, size: int) -> Self:
        """Parses the container output into problem data."""
        ...

    @abstractmethod
    def encode(self, target_dir: Path, size: int, team: Literal["generator", "solver"]) -> None:
        """Encodes the data into files that can be passed to docker containers."""
        ...


@dataclass(kw_only=True)
class Hidden:
    """Marker class indicating that a field will not be parsed into the solver input."""
    generator: bool = True
    solver: bool = True


class BaseModel(BaseModel, ABC):
    """Problem data that can easily be encoded into and decoded from json files."""

    filename: ClassVar[str]

    @inherit_docs
    @classmethod
    def decode(cls: type[Self], source_dir: Path, size: int) -> Self:
        return cls.parse_file(source_dir / cls.filename)

    @inherit_docs
    def encode(self, target_dir: Path, size: int, team: Literal["generator", "solver"]) -> None:
        with open(target_dir / self.filename, "w") as f:
            f.write(self.json(exclude=self._excludes(team)))

    @classmethod
    def _excludes(cls, team: Literal["generator", "solver"]) -> dict[str | int, Any]:
        excludes = {}
        for name, annotation in get_type_hints(cls, include_extras=True).items():
            if hasattr(annotation, "__metadata__"):
                excludes[name] = any(isinstance(o, Hidden) and getattr(o, team) for o in annotation.__metadata__)
            elif issubclass(annotation, BaseModel):
                excludes[name] = annotation._excludes(team)
        return excludes
