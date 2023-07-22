"""Module containung various utility definitions.

In particular, the base classes :class:`BaseModel`, :class:`Encodable`, :class:`EncodableModel`, and exception classes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from traceback import format_exception
from typing import Any, Callable, Iterable, Literal, LiteralString, TypeVar, Self, cast, get_args, overload
from typing_extensions import TypedDict

from pydantic import (
    ConfigDict,
    BaseModel as PydandticBaseModel,
    Extra,
    GetCoreSchemaHandler,
    ValidationError as PydanticValidationError,
    ValidationInfo,
)
from pydantic._internal._decorators import inspect_validator
from pydantic_core import CoreSchema
from pydantic_core.core_schema import general_after_validator_function


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


class InstanceSolutionModel(EncodableModel, ABC):
    """Base Model class for instances or solution classes."""

    @classmethod
    def _annotation_needs_self(cls, annotation: object, model_type: Literal["instance", "solution"]) -> bool:
        if isinstance(annotation, AttributeReferenceValidator):
            return annotation.needs_self(model_type)
        return any(cls._annotation_needs_self(e, model_type) for e in get_args(annotation))

    @classmethod
    def _validate_with_self(cls, model_type: Literal["instance", "solution"]) -> bool:
        return any(cls._annotation_needs_self(info.annotation, model_type) for info in cls.model_fields.values())


ModelReference = Literal["instance", "solution", "self"]


@dataclass(frozen=True, slots=True)
class AttributeReference:
    """Creates a reference to the attribute of a model to be used in validaton schemas."""

    model: ModelReference
    attribute: str

    def get_value(self, info: ValidationInfo) -> Any | None:
        """Returns the referenced value from the correct object in the info context.

        If the correct object is not in the context or doesn't have the referenced attribute it returns None.
        """
        if info.context is None or self.model not in info.context:
            return None
        model = info.context[self.model]
        if hasattr(model, self.attribute):
            return getattr(model, self.attribute)
        else:
            return None

    def __str__(self) -> str:
        return f"{self.model}.{self.attribute}"

    def needs_self(self, model_type: Literal["instance", "solution"]) -> bool:
        """Checks if an attribute reference needs a reference to the current model in order to be resolved."""
        if self.model == "self":
            return True
        else:
            return self.model == model_type


NoInfoAttrValidatorFunction = Callable[[Any, Any], Any]
GeneralAttrValidatorFunction = Callable[[Any, Any, ValidationInfo], Any]
AttrValidatorFunction = NoInfoAttrValidatorFunction | GeneralAttrValidatorFunction


class AttributeReferenceValidator:
    """An AfterValidator that can resolve a reference to a model attribute and pass it to the validator function.

    Using this with a reference to an attribute in the model it is defined may significantly impact performance.
    """

    __slots__ = ("func", "attribute")

    @overload
    @inherit_docs
    def __init__(self, func: AttrValidatorFunction, ref: AttributeReference) -> None:
        ...

    @overload
    @inherit_docs
    def __init__(self, func: AttrValidatorFunction, *, model: ModelReference, attribute: str) -> None:
        ...

    def __init__(
        self,
        func: AttrValidatorFunction,
        ref: AttributeReference | None = None,
        *,
        model: ModelReference | None = None,
        attribute: str | None = None,
    ) -> None:
        """Creates an AttributeReferenceValidator."""
        super().__init__()
        self.func = func
        if ref is not None:
            self.attribute = ref
        else:
            assert model is not None and attribute is not None
            self.attribute = AttributeReference(model, attribute)

    def __get_pydantic_core_schema__(self, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        schema = handler(source_type)
        info_arg = inspect_validator(self.func, "after")
        if info_arg:
            func = cast(GeneralAttrValidatorFunction, self.func)

            def wrapper(value: Any, info: ValidationInfo) -> Any:
                attribute_val = self.attribute.get_value(info)
                if attribute_val is None:
                    return value
                return func(value, attribute_val, info)

        else:
            func = cast(NoInfoAttrValidatorFunction, self.func)

            def wrapper(value: Any, info: ValidationInfo) -> Any:
                attribute_val = self.attribute.get_value(info)
                if attribute_val is None:
                    return value
                return func(value, attribute_val)

        return general_after_validator_function(wrapper, schema=schema)

    def needs_self(self, model_type: Literal["instance", "solution"]) -> bool:
        """Checks if the validator needs a reference to the current model in order to work fully."""
        if self.attribute.model == "self":
            return True
        else:
            return self.attribute.model == model_type


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
