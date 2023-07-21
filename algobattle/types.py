"""Utility types used to easily define Problems."""
from typing import Annotated, Sized, TypeVar, Generic
from annotated_types import Ge, Interval

from pydantic import AfterValidator, ValidationInfo, ValidationError, field_validator
from algobattle.problem import ValidateWith, InstanceModel
from algobattle.util import BaseModel

__all__ = (
    "u64",
    "i64",
    "u32",
    "i32",
    "u16",
    "i16",
    "SizeIndex",
    "SizeLen",
    "DirectedGraph",
    "UndirectedGraph",
    "EdgeWeights",
    "VertexWeights",
)


u64 = Annotated[int, Interval(ge=0, lt=2 ** 64)]
"""64 bit unsigned int."""

i64 = Annotated[int, Interval(ge=-(2**63), lt=2**63)]
"""64 bit signed int."""

u32 = Annotated[int, Interval(ge=0, lt=2 ** 32)]
"""32 bit unsigned int."""

i32 = Annotated[int, Interval(ge=-(2**31), lt=2**31)]
"""32 bit signed int."""

u16 = Annotated[int, Interval(ge=0, lt=2 ** 16)]
"""16 bit unsigned int."""

i16 = Annotated[int, Interval(ge=-(2**15), lt=2 ** 15)]
"""16 bit signed int."""


def get_instance(info: ValidationInfo) -> InstanceModel | None:
    if info.context is None:
        return None
    return info.context.get("instance", None)


def size_index_val(v: int, info: ValidationInfo) -> int:
    instance = get_instance(info)
    if instance is None:
        return v
    if v >= instance.size:
        raise ValueError("SizeIndex is not a valid index into a collection of length `instance.size`")
    return v

SizeIndex = Annotated[int, Ge(0), AfterValidator(size_index_val), ValidateWith.Instance]


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


i16 = Annotated[int, Interval(ge=-(2**15), lt=2 ** 15)]
"""16 bit signed int."""


class DirectedGraph(InstanceModel):
    """Base instance class for problems on directed graphs."""

    num_vertices: u64
    edges: list[tuple[u64, u64]]

    @field_validator("edges", mode="after")
    @classmethod
    def unique_edges(cls, value: list[tuple[u64, u64]]) -> list[tuple[u64, u64]]:
        if len(set(value)) != len(value):
            raise ValueError("Edge list contains duplicate entries.")
        return value

    @property
    def size(self) -> int:
        """A graph's size is the number of vertices in it."""
        return self.num_vertices

    def validate_instance(self):
        """Validates that the graph contains at most `size` many vertices and all edges are well defined."""
        if any(u >= self.num_vertices for edge in self.edges for u in edge):
            raise ValidationError("Graph contains edges whose endpoints aren't valid vertices")


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
