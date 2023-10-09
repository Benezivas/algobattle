"""Module containung various utility definitions.

In particular, the base classes :class:`BaseModel`, :class:`Encodable`, :class:`EncodableModel`, and exception classes.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from traceback import format_exception
from types import ModuleType
from typing import Any, LiteralString, TypeVar, Self

from pydantic import (
    ConfigDict,
    BaseModel as PydandticBaseModel,
    ValidationError as PydanticValidationError,
)


class Role(StrEnum):
    """Indicates whether the role of a program is to generate or to solve instances."""

    generator = "generator"
    solver = "solver"


T = TypeVar("T")


class BaseModel(PydandticBaseModel):
    """Base class for all pydantic models."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)


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


class AlgobattleBaseException(Exception):
    """Base exception class for errors used by the algobattle package."""

    def __init__(self, message: LiteralString, *, detail: str | list[str] | list[dict[str, Any]] | None = None) -> None:
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
    detail: str | list[str] | list[dict[str, Any]] | None = None

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
                detail=format_exception(error),
            )


class TempDir(TemporaryDirectory):
    """Python's `TemporaryDirectory` but with a contextmanager returning a Path."""

    def __enter__(self) -> Path:
        return Path(super().__enter__())


def timestamp() -> str:
    """Formats the current time into a filename-safe string."""
    t = datetime.now()
    return f"{t.year:04d}-{t.month:02d}-{t.day:02d}_{t.hour:02d}-{t.minute:02d}-{t.second:02d}"


def import_file_as_module(path: Path, name: str) -> ModuleType:
    """Imports a file as a module.

    Args:
        path: A path to a python file.

    Raises:
        ValueError: If the path doesn't point to a module
        RuntimeError: If the file cannot be imported properly
    """
    if not path.is_file():
        raise ValueError(f"'{path}' does not point to a python file or a proper parent folder of one.")

    try:
        spec = spec_from_file_location(name, path)
        assert spec is not None
        assert spec.loader is not None
        module = module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        raise RuntimeError from e
