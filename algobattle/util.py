"""Module containung various utility definitions.

In particular, the base classes :class:`BaseModel`, :class:`Encodable`, :class:`EncodableModel`, and exception classes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from inspect import isclass
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from traceback import format_exception
from typing import Any, ClassVar, Iterable, Literal, LiteralString, TypeVar, Self, get_args
from typing_extensions import TypedDict

from pydantic import (
    ConfigDict,
    BaseModel as PydandticBaseModel,
    Extra,
    ValidationError as PydanticValidationError,
    ValidationInfo,
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


class AlgobattleContext(TypedDict, total=False):
    """Context passed to validation methods used to parse Program output."""

    role: Role
    max_size: int


class BaseModel(PydandticBaseModel):
    """Base class for all pydantic models."""

    model_config = ConfigDict(extra=Extra.forbid, from_attributes=True)


@dataclass(frozen=True, slots=True)
class AttributeReference:
    """Base class so we can search for model attribute references."""

    attribute: str

    _key: ClassVar[str]

    def get_value(self, info: ValidationInfo) -> Any | None:
        """Returns the referenced value from the correct object in the info context.

        If the correct object is not in the context or doesn't have the referenced attribute it returns None.
        """
        if info.context is None or self._key not in info.context:
            return None
        model = info.context[self._key]
        if hasattr(model, self.attribute):
            return getattr(model, self.attribute)
        else:
            return None

    @classmethod
    def in_annotation(cls, annotation: object) -> bool:
        """Checks if a type appears in an annotation metadata."""
        if isclass(annotation) and issubclass(annotation, cls):
            return True
        return any(cls.in_annotation(e) for e in get_args(annotation))

    @staticmethod
    def validate_with_self(model: BaseModel, model_type: Literal["instance", "solution"]) -> bool:
        """Checks if a model needs to be parsed with itself in the context."""
        metadata_cls = InstanceReference if model_type == "instance" else SolutionReference
        return any(metadata_cls.in_annotation(info.annotation) for info in model.model_fields.values())


class InstanceReference(AttributeReference):
    """A reference to an attribute of an instance."""

    __slots__ = ()

    _key = "instance"

    def __str__(self) -> str:
        return f"instance.{self.attribute}"


class SolutionReference(AttributeReference):
    """A reference to an attribute of a solution."""

    __slots__ = ()

    _key = "solution"

    def __str__(self) -> str:
        return f"solution.{self.attribute}"


class SelfReference(InstanceReference, SolutionReference):
    """A reference to an attribute of the object currently being validated."""

    __slots__ = ()

    _key = "self"

    def __str__(self) -> str:
        return f"self.{self.attribute}"


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
    """A `TemporaryDirecroty`, but it's context manager returns a :class:`Path` object instead of a bare string."""

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
            with open(source.with_suffix(".json"), "r") as f:
                return cls.model_validate_json(f.read(), context={"role": team, "max_size": max_size})
        except PydanticValidationError as e:
            raise EncodingError("Json data does not fit the schema.", detail=str(e))
        except Exception as e:
            raise EncodingError("Unknown error while decoding the data.", detail=str(e))

    def encode(self, target: Path, team: Role) -> None:
        """Uses pydantic to create a json representation of the object at the targeted file."""
        try:
            with open(target.with_suffix(".json"), "w") as f:
                f.write(self.model_dump_json())
        except Exception as e:
            raise EncodingError("Unkown error while encoding the data.", detail=str(e))

    @classmethod
    def io_schema(cls) -> str:
        """Uses pydantic to generate a json schema for this class."""
        return json.dumps(cls.model_json_schema(), indent=4)


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
