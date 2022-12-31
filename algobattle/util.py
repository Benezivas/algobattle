"""Collection of utility functions."""
from abc import ABC, abstractmethod
from dataclasses import KW_ONLY, dataclass, fields
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, ClassVar, Generic, Literal, Protocol, TypeVar, cast, get_type_hints, Self
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
