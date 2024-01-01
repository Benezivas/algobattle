# Creating Problems
## Creating Problems for Others

When starting off with `algobattle`, especially when using the
[algobattle-web](https://github.com/Benezivas/algobattle-web) framework, you may
first want to use ready-made problem files to get familiar using
`algobattle`. We have collected a few of such ready-made problem files in a
[repository](https://github.com/Benezivas/algobattle-problems) for you.

After familiarizing yourself with the flow of the `algobattle` tool, you may
next want to write your own problems. If you have peeked into the files of any
ready-made problems, you may have noticed that they are very slim! As an
example, the following is essentially all of the code that makes the `pairsum`
problem run, which is discussed in the [tutorial of the `algobattle`
tool](tutorial/index.md).

```py title="problem.py"
"""Main module of the Pairsum problem."""
from typing import Annotated

from algobattle.problem import Problem, InstanceModel, SolutionModel
from algobattle.util import Role, ValidationError
from algobattle.types import u64, MinLen, SizeIndex, UniqueItems


Number = SizeIndex


class Instance(InstanceModel):
    """An instance of a Pairsum problem."""

    numbers: Annotated[list[u64], MinLen(4)]

    @property
    def size(self) -> int:
        return len(self.numbers)


class Solution(SolutionModel[Instance]):
    """A solution to a Pairsum problem."""

    indices: Annotated[tuple[Number, Number, Number, Number], UniqueItems]

    def validate_solution(self, instance: Instance, role: Role) -> None:
        super().validate_solution(instance, role)
        first = instance.numbers[self.indices[0]] + instance.numbers[self.indices[1]]
        second = instance.numbers[self.indices[2]] + instance.numbers[self.indices[3]]
        if first != second:
            raise ValidationError("Solution elements don't have the same sum.")


Pairsum = Problem(
    name="Pairsum",
    min_size=4,
    instance_cls=Instance,
    solution_cls=Solution,
)
```

The problem files are this short as the framework does most of the heavy
lifting.  It is nevertheless important to understand what the framework does and
does not care for already.

This tutorial aims to prepare you to start writing your own problems. It is
aimed at instructors that want to learn how to prepare tasks for their students.

The tutorial sections build on each other and are best read in sequence. We
assume that you have already read the (tutorial for users)[tutorial/index.md],
have a basic understanding of theoretical computer science and have basic
knowledge of the Python language.


## Quick Overview

We recommend reading this tutorial in sequence, but you can skip
over sections that seem clear to you.

We assume throughout this part of the tutorial that the default `iterated`
battle class is used -- which is the case if you do not explicitly configure it
to be something else.

Here are the steps that we will be going through.

1. [What characteristics should a problem have in order to be used in the framework?](characteristics.md)

2. [What is the high-level interaction flow between the framework and a problem file?](basic_flow.md)

3. [What are the parts of a problem file?](problem_parts.md)

4. [Creating a concrete problem: The 2D Knapsack Problem](2dkp.md)

5. [Using different I/O formats](io.md)
