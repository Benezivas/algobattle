# The Problem File Structure
## What does a Problem File Look Like?
In the previous section, we gave a very high-level explanation of the
interaction between a problem and the framework.  Let us create a new mock-up
problem to see what we are expected to implement.  We can either copy the files
of an existing problem and modify them, or let `algobattle` create a new problem
template for us. For the sake of clarity, we do the latter by executing 

```console
algobattle init --new -p "Our Mockup Problem"
```

This creates a new folder named `Our Mockup Problem` with the following contents:

``` { .sh .no-copy }
.
└─ Our Mockup Problem
   ├─ generator/
   │  └─ Dockerfile
   ├─ results/
   ├─ solver/
   │  └─ Dockerfile
   ├─ .gitignore
   ├─ problem.py
   └─ algobattle.toml
```

Let us take a look at the contents of the `problem.py` file, which is where
we will implement all of the problem logic.

```py title="problem.py"
"""The Our Mockup Problem problem module."""
from algobattle.problem import Problem, InstanceModel, SolutionModel, maximize
from algobattle.util import Role


class Instance(InstanceModel):
    """Instances of Our Mockup Problem."""

    ...

    @property
    def size(self) -> int:
        ...


class Solution(SolutionModel[Instance]):
    """Solutions of Our Mockup Problem."""

    ...

    @maximize
    def score(self, instance: Instance, role: Role) -> float:
        ...


Problem(
    name="Our Mockup Problem",
    min_size=1,
    instance_cls=Instance,
    solution_cls=Solution,
)
```

The triple dots `...` tell us that problem-specific code is to be implemented at
this point. Let us step through this pre-generated code stubs.

## Imports
The first code snippet of the generated code is the following:

```python
from algobattle.problem import Problem, InstanceModel, SolutionModel, maximize
from algobattle.util import Role
```

The `InstanceModel` and `SolutionModel` are the most basic base classes on which
we can build our instance and solution handling. There are more specific base
classes, such as the `DirectedGraph` class from the `algobattle.types` module
that extend these classes with default arguments such as `num_vertices` and
`edges`. 

///note
Do not worry about these classes right now. Using the basic
classes is never wrong, you may simply safe some work by using extended classes
such as `DirectedGraph`.
///

The imported `Problem` class wraps the instance class, solution class, gives
a name to our problem that is used in the run of the framework and defines
what the smallest valid instance for our given problem should be.

///note
If you rename the string in the `name` argument, make sure that the `name`
argument in the `algobattle.toml` contains an identical string!
///

The `Role` argument is used to let the solution checker differentiate between
a generators solution and a solvers solution. In practice, this is rarely used.

///note
When writing a problem, you will likely add additional imports from the
`algobattle.types` module. To see how and what is available, have a look
the next section of the tutorial that implements a concrete problem.
///

### The Instance Class
The next snippet that was pre-generated is this:

```python
class Instance(InstanceModel):
    """Instances of Our Mockup Problem."""

    ...

    @property
    def size(self) -> int:
        ...
```

This is where some of the magic happens. In the first `...` block, we are
expected to tell the framework which names should be expected in the
`/output/instance.json` file written by a generator. An example could be a key
`edges` in a graph problem, that contains a list of two-tuples describing all
edges of a graph. Accordingly, another key `num_vertices` may be expected,
telling us how many nodes the graph contains in total.

If a key is given that is not in this block, or if a key of the block is not
supplied, the framework will assume that the given instance is malformed and
reject it.

However, only because a key is given does not mean that the corresponding
*value* is of the expected form. This is where a parser has to come into play.
Luckily, we build heavily on the [pydantic](https://docs.pydantic.dev/latest/)
python library to do this job for us. As a small example, we could parse the
two aforementioned keys as follows:

```python
class Instance(InstanceModel):
    """Instances of Our Mockup Problem."""

    num_vertices: u64
    edges: Annotated[list[tuple[SizeIndex, SizeIndex]], UniqueItems]

    @property
    def size(self) -> int:
        ...
```

This would of course require us to add an import:

```python
from typing import Annotated
from algobattle.types import u64, SizeIndex, UniqueItems
```

That is the parsing done! Note that the `SizeIndex` field tells the framework
that no edge label should exceed the size of the instance.

There are two things left to do. Maybe the instance should have some semantic
constraints that cannot be easily checked by simple type-checking. If this is the
case, you can add a method `validate_instance` to the `Instance` class to do
just that:

```python
def validate_instance(self) -> None:
        super().validate_instance()
        if not very_important_property_holds:
            raise ValidationError(
                "A very important property does not hold!",
                detail=f"Given property is {very_important_property_holds}.",
            )
```

If anything is not as expected, raise a `ValidationError` (imported from
`algobattle.util`). This tells the framework that the instance is malformed and
to output the given error message.

///note
You may notice the optional `detail` argument of the `ValidationError`
exception.  When the logs are visible for everyone, accidentally leaking
information about parts of an instance, may reveal the strategy of a team. On
the other hand, when developing code, a team may nevertheless *want* to see
exactly what went wrong. The `detail` field is thus part of a more verbose log
that is not visible by default.
///

This validation step is optional.
You do however have to tell the framework what the size of a given instance is.
You do this by overwriting the `size` method. The complete `Instance` class
could thus look like this:

```python
class Instance(InstanceModel):
    """Instances of Our Mockup Problem."""

    num_vertices: u64
    edges: Annotated[list[tuple[SizeIndex, SizeIndex]], UniqueItems]

    def validate_instance(self) -> None:
        super().validate_instance()
        if not very_important_property_holds:
            raise ValidationError(
                "A very important property does not hold.",
                detail=f"Property {very_important_property_holds} does not hold.",
            )

    @property
    def size(self) -> int:
        return self.num_vertices
```

### The Solution
Handling a solution given in the `/output/solution.json` is very similar to
handling an instance. Let us take a look at the stub we were given:
```python
class Solution(SolutionModel[Instance]):
    """Solutions of Our Mockup Problem."""

    ...

    @maximize
    def score(self, instance: Instance, role: Role) -> float:
        ...
```

In the first block of three dots and just like with the instance, we determine
which keys the framework should expect and give additional typing information.

You then, most likely, want to make sure that the solution fits the given
instance. As with the validation of the instance, you can do this by overwriting
a specific method, namely the `validate_solution` one. This method supplies an
`instance` argument, through which you can access the attributes of the given
instance.

```python
class Solution(SolutionModel[Instance]):
    """Solutions of Our Mockup Problem."""

    path: list[Vertex]

    def validate_solution(self, instance: Instance, role: Role) -> None:
        super().validate_solution(instance, role)
        if not return len(self.path) == len(set(self.path)):
            raise ValidationError("The given path contains repeated nodes.")

        for edge in set(instance.edges):
            ...
```

Again, any `ValidationError` that is raised communicates to the framework that
the solution should be seen as invalid and thus be rejected.

Finally, we need to tell the framework whether we are dealing with a
minimization or a maximization problem -- the default -- and what the size of
the solution should be.

Put all together, the `Solution` class may look like this:

```python
class Solution(SolutionModel[Instance]):
    """Solutions of Our Mockup Problem."""

    path: list[Vertex]  # Vertex needs to be imported from algobattle.types

    def validate_solution(self, instance: Instance, role: Role) -> None:
        super().validate_solution(instance, role)
        if not return len(self.path) == len(set(self.path)):
            raise ValidationError("The given path contains repeated nodes.")

        for edge in set(instance.edges):
            ...

    @maximize
    def score(self, instance: Instance, role: Role) -> float:
        return len(self.path)
```

## Handling Dependencies
You may want to import some additional python libraries to use in your
`problem.py`, such as [networkx](https://networkx.org/). This can be automated
by adding these dependencies to the `algobattle.toml` file:

```toml
[match]
problem = "Our Mockup Problem"

[problem]
dependencies = [
    "networkx",
]
```

These packages are then installed through `pip` on the users machine, if not
present already.