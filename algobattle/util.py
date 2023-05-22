"""Module containung various utility definitions.

In particular, the base classes :class:`BaseModel`, :class:`Encodable`, :class:`EncodableModel`, and exception classes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from tempfile import TemporaryDirectory
from traceback import format_exception
from typing import Annotated, Any, Iterable, Literal, LiteralString, TypeVar, Self

from pydantic import (
    BaseConfig,
    BaseModel as PydandticBaseModel,
    Extra,
    ValidationError as PydanticValidationError,
    conint,
)


class Role(Enum):
    """Indicates whether the role of a program is to generate or to solve instances."""

    generator = "generator"
    solver = "solver"


MatchMode = Literal["tournament", "testing"]
"""Indicates what type of match is being fought."""
T = TypeVar("T")


def str_with_traceback(exception: Exception) -> str:
    """Returns the full exception info with a stacktrace."""
    return "\n".join(format_exception(exception))


class BaseModel(PydandticBaseModel):
    """Base class for all pydantic models."""

    class Config(BaseConfig):
        """Base config for all pydandic configs."""

        extra = Extra.forbid
        underscore_attrs_are_private = False


u64 = Annotated[conint(ge=0, le=2**64 - 1), ...]
"""Helper type to easily define model fields that fit into a 64 bit unsigned int."""
i64 = Annotated[conint(ge=-(2**63), le=2**63 - 1), ...]
"""Helper type to easily define model fields that fit into a 64 bit signed int."""


def inherit_docs(obj: T) -> T:
    """Decorator to mark a method as inheriting its docstring.

    Python 3.5+ already does this, but pydocstyle needs a static hint.
    """
    return obj


def check_path(path: str, *, type: Literal["file", "dir", "exists"] = "exists") -> Path:
    """Parses a string into a :class:`Path` and checks that it is valid.

    Args:
        path: The string to be parsed.
        type: What kind of check to perform on the path.

    Raises:
        ValueError: If the path fails the check.

    Returns:
        The parsed path object.
    """
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


class TempDir(TemporaryDirectory[Any]):
    """A :class:`TemporaryDirecroty`, but it's context manager returns a :class:`Path` object instead of a bare string."""

    def __enter__(self):
        return Path(super().__enter__())


class Encodable(ABC):
    """Represents data that docker containers can interact with."""

    @classmethod
    @abstractmethod
    def decode(cls, source: Path, max_size: int, team: Role) -> Self:
        """Decodes the data found at the given path into a python object.

        Args:
            source: Path to data that can be used to construct an instance of this class. May either point to a folder
                or a single file. The expected type of path should be consistent with the result of :meth:`.encode`.
            max_size: The size of the fight for which this data is being decoded.
            team: Role of the team that output the data.

        Raises:
            EncodingError: If the data cannot be decoded into an instance.

        Returns:
            The decoded object.
        """
        raise NotImplementedError

    @abstractmethod
    def encode(self, target: Path, team: Role) -> None:
        """Encodes the object onto the file system so that it can be passed to a program.

        Args:
            target: Path to the location where the program expects the encoded data. :meth:`.encode` may either create
                a single file at the target location, or an entire folder. If creating a single file, it may append a
                file type ending to the path. It should not affect any other files or directories.
            team: Role of the team that receives the data.

        Raises:
            EncodingError: If the data cannot be properly encoded.
        """
        raise NotImplementedError

    @classmethod
    def io_schema(cls) -> str | None:
        """Generates a schema specifying the I/O for this data.

        The schema should specify the structure of the data in the input and output files or folders.
        In particular, the specification should match precisely what :meth`.decode` accepts, and the output of
        :meth:`.encode` should comply with it.

        Returns:
            The schema, or `None` to indicate no information about the expected shape of the data can be provided.
        """
        return None


class EncodableModel(BaseModel, Encodable, ABC):
    """Problem data that can easily be encoded into and decoded from json files."""

    @classmethod
    def decode(cls, source: Path, max_size: int, team: Role) -> Self:
        """Uses pydantic to create a python object from a `.json` file."""
        if not source.with_suffix(".json").is_file():
            raise EncodingError("The json file does not exist.")
        try:
            return cls.parse_file(source.with_suffix(".json"))
        except PydanticValidationError as e:
            raise EncodingError("Json data does not fit the schema.", detail=str(e))
        except Exception as e:
            raise EncodingError("Unknown error while decoding the data.", detail=str(e))

    def encode(self, target: Path, team: Role) -> None:
        """Uses pydantic to create a json representation of the object at the targeted file."""
        try:
            with open(target.with_suffix(".json"), "w") as f:
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

    def __init__(self, message: LiteralString, *, detail: str | None = None) -> None:
        """Base exception class for errors used by the algobattle package.

        Args:
            message: Simple error message that can always be displayed.
            detail: More detailed error message that may include sensitive information.
        """
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

    def __init__(self, message: LiteralString, *, detail: str | None = None, runtime: float) -> None:
        """Indicates that the program could not be executed successfully.

        Args:
            message: Simple error message that can always be displayed.
            runtime: Runtime of the program in seconds until the error occured.
            detail: More detailed error message that may include sensitive information.
        """
        self.runtime = runtime
        super().__init__(message, detail=detail)


class ExecutionTimeout(ExecutionError):
    """Indicates that the program ran into the timeout."""


class DockerError(AlgobattleBaseException):
    """Indicates that an issue with the docker daemon occured."""


class ExceptionInfo(BaseModel):
    """Details about an exception that was raised."""

    type: str
    message: str
    detail: str | None = None

    @classmethod
    def from_exception(cls, error: Exception) -> Self:
        """Constructs an instance from a raised exception."""
        if isinstance(error, AlgobattleBaseException):
            return cls(
                type=error.__class__.__name__,
                message=error.message,
                detail=error.detail,
            )
        else:
            return cls(
                type=error.__class__.__name__,
                message=str(error),
                detail=str_with_traceback(error),
            )
