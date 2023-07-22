"""Utility types used to easily define Problems."""
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Iterator, Sized, TypeVar, Generic, overload
import operator
from annotated_types import (
    BaseMetadata,
    Ge as AnnotatedGe,
    GroupedMetadata,
    Gt as AnnotatedGt,
    Le as AnnotatedLe,
    Lt as AnnotatedLt,
    Interval as AnnotatedInterval,
    SupportsGe,
    SupportsGt,
    SupportsLe,
    SupportsLt,
)

from pydantic import AfterValidator, ValidationInfo, ValidationError, field_validator
from algobattle.problem import ValidateWith, InstanceModel
from algobattle.util import BaseModel, AttributeReference, InstanceReference

__all__ = (
    "u64",
    "i64",
    "u32",
    "i32",
    "u16",
    "i16",
    "Gt",
    "Ge",
    "Lt",
    "Le",
    "SizeIndex",
    "SizeLen",
    "DirectedGraph",
    "UndirectedGraph",
    "EdgeWeights",
    "VertexWeights",
)


u64 = Annotated[int, AnnotatedInterval(ge=0, lt=2**64)]
"""64 bit unsigned int."""

i64 = Annotated[int, AnnotatedInterval(ge=-(2**63), lt=2**63)]
"""64 bit signed int."""

u32 = Annotated[int, AnnotatedInterval(ge=0, lt=2**32)]
"""32 bit unsigned int."""

i32 = Annotated[int, AnnotatedInterval(ge=-(2**31), lt=2**31)]
"""32 bit signed int."""

u16 = Annotated[int, AnnotatedInterval(ge=0, lt=2**16)]
"""16 bit unsigned int."""

i16 = Annotated[int, AnnotatedInterval(ge=-(2**15), lt=2**15)]
"""16 bit signed int."""


CmpOpType = Callable[[Any, Any], bool]


def attribute_cmp_validator(attribute: AttributeReference, operator_func: CmpOpType, phrase: str) -> AfterValidator:
    def validator(value: Any, info: ValidationInfo) -> Any:
        attribute_val = attribute.get_value(info)
        if attribute_val is None:
            return value

        if not operator_func(value, attribute_val):
            raise ValueError(f"Value is not {phrase} {attribute}")
        return value

    return AfterValidator(validator)


@overload
def Gt(gt: SupportsGt) -> AnnotatedGt:
    ...


@overload
def Gt(gt: AttributeReference) -> AfterValidator:
    ...


def Gt(gt: SupportsGt | AttributeReference) -> AnnotatedGt | AfterValidator:
    """Implies that the value must be greater than the argument.

    Passing an `AttributeReferece` means that the value must be greater than the value on the referenced property of
    the instance or solution. E.g. `Gt(InstanceReference("size"))` in a solution model implies that the value must be
    greater than the size of the instance it solves.

    It can be used with any type that supports the ``>`` operator,
    including numbers, dates and times, strings, sets, and so on.
    """
    if isinstance(gt, AttributeReference):
        return attribute_cmp_validator(gt, operator.gt, "greater than")
    else:
        return AnnotatedGt(gt)


@overload
def Ge(ge: SupportsGe) -> AnnotatedGe:
    ...


@overload
def Ge(ge: AttributeReference) -> AfterValidator:
    ...


def Ge(ge: SupportsGe | AttributeReference) -> AnnotatedGe | AfterValidator:
    """Implies that the value must be greater than or equal to the argument.

    Passing an `AttributeReferece` means that the value must be greater than or equal to the value on the referenced
    property of the instance or solution. E.g. `Ge(InstanceReference("size"))` in a solution model implies that the
    value must be greater than or equal to the size of the instance it solves.

    It can be used with any type that supports the ``>=`` operator,
    including numbers, dates and times, strings, sets, and so on.
    """
    if isinstance(ge, AttributeReference):
        return attribute_cmp_validator(ge, operator.ge, "greater than or equal to")
    else:
        return AnnotatedGe(ge)


@overload
def Lt(lt: SupportsLt) -> AnnotatedLt:
    ...


@overload
def Lt(lt: AttributeReference) -> AfterValidator:
    ...


def Lt(lt: SupportsLt | AttributeReference) -> AnnotatedLt | AfterValidator:
    """Implies that the value must be less than the argument.

    Passing an `AttributeReferece` means that the value must be less than the value on the referenced property of
    the instance or solution. E.g. `Lt(InstanceReference("size"))` in a solution model implies that the value must be
    less than the size of the instance it solves.

    It can be used with any type that supports the ``<`` operator,
    including numbers, dates and times, strings, sets, and so on.
    """
    if isinstance(lt, AttributeReference):
        return attribute_cmp_validator(lt, operator.lt, "less than")
    else:
        return AnnotatedLt(lt)


@overload
def Le(le: SupportsLe) -> AnnotatedLe:
    ...


@overload
def Le(le: AttributeReference) -> AfterValidator:
    ...


def Le(le: SupportsLe | AttributeReference) -> AnnotatedLe | AfterValidator:
    """Implies that the value must be less than or equal to the argument.

    Passing an `AttributeReferece` means that the value must be less than or equal to the value on the referenced
    property of the instance or solution. E.g. `Le(InstanceReference("size"))` in a solution model implies that the
    value must be less than or equal to the size of the instance it solves.

    It can be used with any type that supports the ``<=`` operator,
    including numbers, dates and times, strings, sets, and so on.
    """
    if isinstance(le, AttributeReference):
        return attribute_cmp_validator(le, operator.le, "less than or equal to")
    else:
        return AnnotatedLe(le)


@dataclass(frozen=True, kw_only=True, slots=True)
class Interval(GroupedMetadata):
    """Interval can express inclusive or exclusive bounds with a single object.

    It accepts keyword arguments ``gt``, ``ge``, ``lt``, and/or ``le``, which
    are interpreted the same way as the single-bound constraints.
    """

    gt: SupportsGt | AttributeReference | None = None
    ge: SupportsGe | AttributeReference | None = None
    lt: SupportsLt | AttributeReference | None = None
    le: SupportsLe | AttributeReference | None = None

    def __iter__(self) -> Iterator[BaseMetadata | AfterValidator]:  # type: ignore
        """Unpack an Interval into zero or more single-bounds."""
        if self.gt is not None:
            yield Gt(self.gt)
        if self.ge is not None:
            yield Ge(self.ge)
        if self.lt is not None:
            yield Lt(self.lt)
        if self.le is not None:
            yield Le(self.le)


SizeIndex = Annotated[u64, AnnotatedGe(0), Lt(InstanceReference("size"))]


def get_instance(info: ValidationInfo) -> InstanceModel | None:
    if info.context is None:
        return None
    return info.context.get("instance", None)


S = TypeVar("S", bound=Sized)


def size_len_val(v: S, info: ValidationInfo) -> S:
    """Validates that the collection has length `instance.size`."""
    instance = get_instance(info)
    if instance is None:
        return v
    if len(v) != instance.size:
        raise ValueError("Value does not have length `instance.size`")
    return v


SizeLen = Annotated[S, AfterValidator(size_len_val), ValidateWith.Instance]


class DirectedGraph(InstanceModel):
    """Base instance class for problems on directed graphs."""

    num_vertices: u64
    edges: list[tuple[SizeIndex, SizeIndex]]

    @field_validator("edges", mode="after")
    @classmethod
    def _unique_edges(cls, value: list[tuple[u64, u64]]) -> list[tuple[u64, u64]]:
        if len(set(value)) != len(value):
            raise ValueError("Edge list contains duplicate entries.")
        return value

    @property
    def size(self) -> int:
        """A graph's size is the number of vertices in it."""
        return self.num_vertices


class UndirectedGraph(DirectedGraph):
    """Base instance class for problems on undirected graphs."""

    def validate_instance(self):
        """Validates that the graph is well formed and contains no self loops.

        Also brings it into a normal form where every edge {u, v} occurs exactly once in the list.
        I.e. `[(0, 1), (1, 0), (1, 2)]` is accepted as valid and normalised to `[(0, 1), (1, 2)]`.
        """
        super().validate_instance()
        if any(u == v for u, v in self.edges):
            raise ValidationError("Undirected graph contains self loops.")

        # we remove the redundant edge definitions to create an easy to use normal form
        normalized_edges: set[tuple[int, int]] = set()
        for u, v in self.edges:
            if (v, u) not in normalized_edges:
                normalized_edges.add((u, v))
        self.edges = list(normalized_edges)


def edge_index_val(v: int, info: ValidationInfo) -> int:
    instance = get_instance(info)
    if instance is None:
        return v
    assert isinstance(instance, DirectedGraph)
    if v >= len(instance.edges):
        raise ValueError("Value is not a valid index into `instance.`")
    return v


EdgeIndex = Annotated[u64, AfterValidator(edge_index_val), ValidateWith.Instance]


def edge_len_val(v: S, info: ValidationInfo) -> S:
    """Validates that the collection has length `instance.size`."""
    instance = get_instance(info)
    if not isinstance(instance, DirectedGraph):
        return v
    if len(v) != len(instance.edges):
        raise ValueError("Value does not have the same length `instance.edges`")
    return v


SizeLen = Annotated[S, AfterValidator(size_len_val), ValidateWith.Instance]


Weight = TypeVar("Weight")


class EdgeWeights(DirectedGraph, BaseModel, Generic[Weight]):
    """Mixin for graphs with weighted edges."""

    edge_weights: list[Weight]

    def validate_instance(self):
        """Validates that each edge has an associated weight."""
        super().validate_instance()
        if len(self.edge_weights) != len(self.edges):
            raise ValidationError("Number of edge weights doesn't match the number of edges.")


class VertexWeights(DirectedGraph, BaseModel, Generic[Weight]):
    """Mixin for graphs with weighted vertices."""

    vertex_weights: list[Weight]

    def validate_instance(self):
        """Validates that each vertex has an associated weight."""
        super().validate_instance()
        if len(self.vertex_weights) != self.num_vertices:
            raise ValidationError("Number of vertex weights doesn't match the number of vertices.")