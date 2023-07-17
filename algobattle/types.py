"""Utility types used to easily define Problems."""
from typing import Annotated
from annotated_types import Interval

__all__ = (
    "u64",
    "i64",
    "u32",
    "i32",
    "u16",
    "i16",
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