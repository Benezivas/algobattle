"""Module containung various utility definitions.

In particular, the base classes :class:`BaseModel`, :class:`Encodable`, :class:`EncodableModel`, and exception classes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from inspect import Parameter, Signature, signature
from itertools import chain
import json
from pathlib import Path
from traceback import format_exception
from typing import Annotated, Any, Callable, ClassVar, Iterable, Literal, LiteralString, TypeVar, Self, cast, get_args
from annotated_types import GroupedMetadata
from importlib.metadata import EntryPoint, entry_points

from pydantic import (
    AfterValidator,
    ByteSize,
    ConfigDict,
    BaseModel as PydandticBaseModel,
    Extra,
    Field,
    GetCoreSchemaHandler,
    ValidationError as PydanticValidationError,
    ValidationInfo,
)
from pydantic.types import PathType
from pydantic_core import CoreSchema
from pydantic_core.core_schema import general_after_validator_function, union_schema, no_info_after_validator_function


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


def inherit_docs(obj: T) -> T:
    """Decorator to mark a method as inheriting its docstring.

    Python 3.5+ already does this, but pydocstyle needs a static hint.
    """
    return obj


ModelType = Literal["instance", "solution", "other"]
ModelReference = ModelType | Literal["self"]


class BaseModel(PydandticBaseModel):
    """Base class for all pydantic models."""

    model_config = ConfigDict(extra=Extra.forbid, from_attributes=True)


class InstanceSolutionModel(BaseModel):
    """Base class for Instance and solution models."""

    _algobattle_model_type: ClassVar[ModelType] = "other"

    @classmethod
    def model_validate(  # noqa: D102
        cls,
        obj: Any,
        *,
        strict: bool | None = None,
        from_attributes: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> Self:
        model = super().model_validate(obj, strict=strict, from_attributes=from_attributes, context=context)
        if cls._validate_with_self(cls._algobattle_model_type):
            context = (context or {}) | {"self": model, cls._algobattle_model_type: model}
            model = super().model_validate(obj, context=context)
        return model

    @classmethod
    def _annotation_needs_self(cls, annotation: object, model_type: ModelType) -> bool:
        if isinstance(annotation, AttributeReferenceValidator):
            return annotation.needs_self(model_type)
        if isinstance(annotation, GroupedMetadata):
            return any(cls._annotation_needs_self(e, model_type) for e in annotation)
        return any(cls._annotation_needs_self(e, model_type) for e in get_args(annotation))

    @classmethod
    def _validate_with_self(cls, model_type: ModelType) -> bool:
        # info.annotation contains the type and any nested metadata, info.metadata the top level metadata
        # we can use _annotation_needs_self for all of them, so we iterate over all fields and see if any of them
        # either have an annotation or metadata we need to parse with a self reference
        for info in cls.model_fields.values():
            values = chain((info.annotation,), info.metadata)
            if any(cls._annotation_needs_self(value, model_type) for value in values):
                return True
        return False


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


def is_info_validator(validator: AttrValidatorFunction) -> bool:
    """Helper method to discriminate the union."""
    match count_positional_params(signature(validator)):
        case 2:
            return False
        case 3:
            return True
        case _:
            raise TypeError


@dataclass(frozen=True, slots=True)
class AttributeReferenceValidator:
    """An AfterValidator that can resolve a reference to a model attribute and pass it to the validator function.

    Using this with a reference to an attribute in the model it is defined may significantly impact performance.
    """

    func: AttrValidatorFunction
    attribute: AttributeReference

    def __get_pydantic_core_schema__(self, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        schema = handler(source_type)
        info_arg = is_info_validator(self.func)
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

    def needs_self(self, model_type: ModelType) -> bool:
        """Checks if the validator needs a reference to the current model in order to work fully."""
        if self.attribute.model == "self":
            return True
        else:
            return self.attribute.model == model_type


@dataclass
class AttributeReferenceMaker:
    """Helper class to easily create attribute references."""

    _attr_ref_maker_model: ModelReference

    def __getattr__(self, __name: str) -> AttributeReference:
        return AttributeReference(self._attr_ref_maker_model, __name)


SelfRef = AttributeReferenceMaker("self")


InstanceRef = AttributeReferenceMaker("instance")


SolutionRef = AttributeReferenceMaker("solution")


class Encodable(ABC):
    """Represents data that docker containers can interact with."""

    @classmethod
    @abstractmethod
    def decode(cls, source: Path, max_size: int, role: Role) -> Self:
        """Decodes the data found at the given path into a python object.

        Args:
            source: Path to data that can be used to construct an instance of this class. May either point to a folder
                or a single file. The expected type of path should be consistent with the result of :meth:`.encode`.
            max_size: Maximum size the current battle allows.
            role: Role of the program that generated this data.

        Raises:
            EncodingError: If the data cannot be decoded into an instance.

        Returns:
            The decoded object.
        """
        raise NotImplementedError

    @abstractmethod
    def encode(self, target: Path, role: Role) -> None:
        """Encodes the object onto the file system so that it can be passed to a program.

        Args:
            target: Path to the location where the program expects the encoded data. :meth:`.encode` may either create
                a single file at the target location, or an entire folder. If creating a single file, it may append a
                file type ending to the path. It should not affect any other files or directories.
            role: Role of the program that generated this data.

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
    def _decode(cls, source: Path, **context: Any) -> Self:
        """Internal method used by .decode to let Solutions also accept the corresponding instance."""
        if not source.with_suffix(".json").is_file():
            raise EncodingError("The json file does not exist.")
        try:
            with open(source.with_suffix(".json"), "r") as f:
                return cls.model_validate_json(f.read(), context=context)
        except PydanticValidationError as e:
            raise EncodingError("Json data does not fit the schema.", detail=str(e))
        except Exception as e:
            raise EncodingError("Unknown error while decoding the data.", detail=str(e))

    @classmethod
    def decode(cls, source: Path, max_size: int, role: Role) -> Self:
        """Uses pydantic to create a python object from a `.json` file."""
        return cls._decode(source, max_size=max_size, role=role)

    def encode(self, target: Path, role: Role) -> None:
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
class RunningTimer:
    """Basic data holding info on a currently running timer."""

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


def count_positional_params(sig: Signature) -> int:
    """Counts the number of positional parameters in a signature."""
    return sum(1 for param in sig.parameters.values() if can_be_positional(param))


def can_be_positional(param: Parameter) -> bool:
    """Checks whether a parameter is positional."""
    return param.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)


def problem_entrypoints() -> dict[str, EntryPoint]:
    """Returns all currently registered problem entrypoints."""
    return {e.name: e for e in entry_points(group="algobattle.problem")}


def battle_entrypoints() -> dict[str, EntryPoint]:
    """Returns all currently registered battle entrypoints."""
    return {e.name: e for e in entry_points(group="algobattle.battle")}
