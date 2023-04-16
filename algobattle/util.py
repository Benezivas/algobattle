"""Collection of utility functions."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from traceback import format_exception
from typing import Any, ClassVar, Iterable, Literal, TypeVar, Self

from pydantic import BaseConfig, BaseModel, Extra, ValidationError as PydanticValidationError


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

    @classmethod
    def io_schema(cls) -> str | None:
        """Generates a schema specifying the I/O for this data.
        
        The schema should specify the structure of the data in the input and output folders.
        In particular, the specification should match precisely what :meth`.decode` accepts, and the output of
        :meth:`.encode` should comply with it.

        Returns:
            The schema, or `None` to indicate no information about the expected shape of the data can be provided.
        """
        return None


class EncodableModel(BaseModel, Encodable, ABC):
    """Problem data that can easily be encoded into and decoded from json files."""

    filename: ClassVar[str]

    @inherit_docs
    @classmethod
    def decode(cls: type[Self], source_dir: Path, size: int, team: Role) -> Self:
        try:
            return cls.parse_file(source_dir / cls.filename)
        except PydanticValidationError as e:
            raise EncodingError("Json data does not fit the schema.", detail=str(e))
        except Exception as e:
            raise EncodingError("Unknown error while decoding the data.", detail=str(e))

    @inherit_docs
    def encode(self, target_dir: Path, size: int, team: Role) -> None:
        try:
            with open(target_dir / self.filename, "w") as f:
                f.write(self.json(exclude=self._excludes(team)))
        except Exception as e:
            raise EncodingError("Unkown error while encoding the data.", detail=str(e))

    @classmethod
    def io_schema(cls) -> str:
        """Uses pydantic to generate a json schema for this class."""
        return cls.schema_json(indent=4)

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


class AlgobattleBaseException(Exception):
    """Base exception class for errors used by the algobattle package."""

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        self.message = message
        self.detail = detail
        super().__init__()


class EncodingError(AlgobattleBaseException):
    """Indicates that the given data could not be encoded or decoded properly."""


class ValidationError(AlgobattleBaseException):
    """Indicates that the decoded problem instance or solution is invalid."""


class BuildError(AlgobattleBaseException):
    """Indicates that the build process could not be completed successfully."""


class ExecutionError(AlgobattleBaseException):
    """Indicates that the program could not be executed successfully."""

    def __init__(self, message: str, *, detail: str | None = None, runtime: float) -> None:
        self.runtime = runtime
        super().__init__(message, detail=detail)


class ExecutionTimeout(ExecutionError):
    """Indicates that the program ran into the timeout."""


class DockerError(AlgobattleBaseException):
    """Indicates that an issue with the docker daemon occured."""


class ExceptionInfo(BaseModel):
    """An exception that can be encoded into a json file."""

    type: str
    message: str
    detail: str | None = None

    @classmethod
    def from_exception(cls, error: AlgobattleBaseException) -> Self:
        """Constructs an instance from a raised exception."""
        return cls(
            type=error.__class__.__name__,
            message=error.message,
            detail=error.detail,
        )
