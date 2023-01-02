"""Collection of utility functions."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, ClassVar, Literal, Mapping, Protocol, TypeVar, dataclass_transform, get_origin, Self, get_type_hints
from pydantic import BaseModel


Role = Literal["generator", "solver"]

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


def argspec(*, default: T, help: str = "", parser: Callable[[str], T] | None = None) -> T:
    """Structure specifying the CLI arg."""
    metadata = {
        "help": help,
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
    def as_argparse_args(cls) -> list[tuple[str, dict[str, Any]]]:
        """Constructs a list of `*args` and `**kwargs` that can be passed to `ArgumentParser.add_argument()`."""
        arguments: list[tuple[str, dict[str, Any]]] = []
        resolved_annotations = get_type_hints(cls)
        for field in fields(cls):
            kwargs = {
                "type": field.metadata.get("parser", resolved_annotations[field.name]),
                "help": field.metadata.get("help", "") + f" Default: {field.default}",
            }
            if field.type == bool:
                kwargs["action"] = "store_const"
                kwargs["const"] = not field.default
            elif get_origin(field.type) == Literal:
                kwargs["choices"] = field.type.__args__

            arguments.append((field.name, kwargs))
        return arguments


def getattr_set(o: object, *attrs: str) -> dict[str, Any]:
    """Returns a dict of the given attributes and their values, if they are not `None`."""
    return {a: getattr(o, a) for a in attrs if getattr(o, a, None) is not None}


class TempDir(TemporaryDirectory[Any]):
    
    def __enter__(self):
        super().__enter__()
        return Path(self.name)


class CustomEncodable(ABC):
    """Represents problem data that docker containers can interact with."""

    @classmethod
    @abstractmethod
    def decode(cls: type[Self], source_dir: Path, size: int) -> Self:
        """Parses the container output into problem data."""
        ...

    @abstractmethod
    def encode(self, target_dir: Path, size: int, team: Role) -> None:
        """Encodes the data into files that can be passed to docker containers."""
        ...


Encodable = CustomEncodable | str | bytes | dict[Any, Any] | None


def encode(data: Mapping[str, Encodable], target_dir: Path, size: int, team: Role) -> None:
    """Encodes data into a folder.
    
    Each element will be encoded into a file or folder named after its key. :cls:`CustomEncodables` use their own method,
    strings will be encoded with utf8, bytes are written as is, and dictionaries will be encoded as json.
    """
    for name, obj in data.items():
        try:
            if isinstance(obj, CustomEncodable):
                (target_dir / name).mkdir()
                obj.encode(target_dir / name, size, team)
            elif isinstance(obj, str):
                with open(target_dir / name, "w+") as f:
                    f.write(obj)
            elif isinstance(obj, bytes):
                with open(target_dir / name, "wb+") as f:
                    f.write(obj)
            elif isinstance(obj, dict):
                with open(target_dir / name, "w+") as f:
                    json.dump(obj, f)
        except Exception as e:
            logger.critical(f"Failed to encode {obj} from into files at {target_dir / name}!\nException: {e}")



def decode(data_spec: Mapping[str, type[Encodable]], source_dir: Path, size: int) -> dict[str, Encodable | None]:
    """Decodes data from a folder.
    
    The output is a dictionary with the same keys as `data_spec` and values that are objects of the specified types.
    :cls:`CustomEncodables` use their own method, strings will be decoded with utf8, bytes are read directly,
    and dictionaries will be decoded from json.
    Any :cls:`Excpeption`s are caught and the corresponding field in the dict be set to `None`.
    """
    out = {}
    for name, cls in data_spec.items():
        try:
            if issubclass(cls, CustomEncodable):
                (source_dir / name).mkdir()
                out[name] = cls.decode(source_dir / name, size)
            elif issubclass(cls, str):
                with open(source_dir / name, "r") as f:
                    out[name] = f.read()
            elif issubclass(cls, bytes):
                with open(source_dir / name, "rb") as f:
                    out[name] = f.read()
            elif issubclass(cls, dict):
                with open(source_dir / name, "r") as f:
                    out[name] = json.load(f)
        except Exception as e:
            logger.critical(f"Failed to decode {cls} object from data at {source_dir / name}!\nException: {e}")
            out[name] = None
    return out


class BaseModel(BaseModel, CustomEncodable, ABC):
    """Problem data that can easily be encoded into and decoded from json files."""

    filename: ClassVar[str]

    @inherit_docs
    @classmethod
    def decode(cls: type[Self], source_dir: Path, size: int) -> Self:
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
            elif isinstance(getattr(self, name, None), BaseModel):
                excludes[name] = getattr(self, name)._excludes(team)
        return excludes
