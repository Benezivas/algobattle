# The 2D Knapsack Problem
## The 2D Knapsack Problem
In this section, we implement the so called 2D Knapsack Problem in its entirety,
starting from scratch and ending with a packaged problem archive that
can be handed out to others.

To start, let us define the problem. We are given a two-dimensional, rectangular
space with an integer length and width, each of size at least one. We now
want to pack a number of smaller rectangles into this space, such that no two 
pieces overlap and such that as much space is covered as possible. Each
piece may be rotated by 90 degrees.

An instance for this problem thus consists of the dimensions of the knapsack as
well as a limited set of rectangular items. A solution for this problem then
describes where which piece should be placed and if it should be rotated by 90
degrees before being placed. The size of the solution is then the total area
covered.

## Starting Off
As in the previous section, we use the `algobattle` cli to construct a dummy
problem folder for us. Since we are interested in later writing a dummy
generator and dummy solver in python, we let the cli generate a stub of them
for us as well as follows:

```console
~ algobattle init --new -p "2D Knapsack" -l python
Created a new problem file at 2D Knapsack/problem.py
Created a python generator in 2D Knapsack/generator
Created a python solver in 2D Knapsack/solver
Initialized algobattle project in 2D Knapsack
```

We navigate into the newly created folder named `2D Knapsack`, which has the
following file structure:

``` { .sh .no-copy }
.
└─ Our Mockup Problem
   ├─ generator/
   │  ├─ .gitignore
   │  ├─ Dockerfile
   │  ├─ generator.py
   │  └─ pyproject.toml
   ├─ results/
   ├─ solver/
   │  ├─ .gitignore
   │  ├─ Dockerfile
   │  ├─ pyproject.toml
   │  └─ solver.py
   ├─ .gitignore
   ├─ problem.py
   └─ algobattle.toml
```

Before we implement anything, we should take the time to specify exactly how
an instance should look like. This means specifying the names of each key,
their function and which values are legal for each.

First of all, an instance should contain the dimensions of the knapsack that is
to be packed. For this, we introduce two keys `height` and `width`, and would
like each to be an integer of value at least one and at most of value `2**64`.

Secondly, we need to describe the items that are to be packed. Each item itself
has a height and a width, which should again each be of integer size at least
one. As an added restriction, we only want to allow items that are at all able
to fit into the knapsack, so as not to allow spamming a solver with items that
can never be part of a valid solution. To spare us some headache in the validation
step of the instance, we demand each item to fit into the knapsack without any 
rotation, as a sort of normalization of the instance.

Next, we need to specify the contents of a valid solution file. This is in
principle quite simple: We are interested in a list specifying which of 
the items of the instance
* should be placed in the knapsack
* at which position
* being rotated or not.

We will be lazy and define a dictionary `packing` that maps the index of items
to a three-tuple, as described.

## Writing a Mock Generator and Solver
Before we start writing any problem code, we write a mock generator and a mock
solver. This helps us do plausability checks while writing the actual problem file
and is not required for the finished problem file.

We start with filling in the generator.

```py title="generator/generator.py"
"""Main module, will be run as the generator."""
import json
from pathlib import Path


max_size = int(Path("/input/max_size.txt").read_text())

instance = {
    'height': 4,
    'width': 3,
    'items': [
        [1, 3],
        [4, 3],
        [3, 3],
        [4, 2],
        [1, 1]
    ]
}

solution = {
    'packing': {
        0: [0, 0, 'unrotated'],
        3: [1, 0, 'rotated'],
        4: [0, 3, 'unrotated']
    }
}

Path("/output/instance.json").write_text(json.dumps(instance))
Path("/output/solution.json").write_text(json.dumps(solution))
```

We made sure that the solution is not unique for the given instance
to make sure that the framework is able to compare two different solutions.
We next fill in the solver.

```py title="generator/solver.py"
"""Main module, will be run as the solver."""
import json
from pathlib import Path


instance = json.loads(Path("/input/instance.json").read_text())

solution = {
    'packing': {
        1: [0, 0, 'rotated']
    }
}


Path("/output/solution.json").write_text(json.dumps(solution))
```

We are now able to immediately test any code that we write.

## Handling Instances
We already know that we expect three keys in any instance: A `height`,
a `width` and a list of `items`.

///note
For brevity, the following code snippets do not include all necessary imports.
We provide the complete content of the `problem.py` at the end of this section.
///

Our first approach uses only very rough type annotations for our expected keys
and does a lot of the validation of the instance explicitely.

```python
"""The 2D Knapsack problem module."""
from algobattle.problem import Problem, InstanceModel, SolutionModel, maximize
from algobattle.util import Role, ValidationError
from algobattle.types import u64


class Instance(InstanceModel):
    """Instances of 2D Knapsack."""

    height: u64
    width: u64

    items: list[u64, u64]

    def validate_instance(self) -> None:
        super().validate_instance()
        if self.height < 1 or self.width < 1:
            raise ValidationError("The knapsack is smaller than allowed!")
        if any(item[0] < 1 or item[1] < 1 for item in self.items):
            raise ValidationError("An item of the instance is smaller than 1x1!")
        if any((item[0] > self.height or item[1] > self.width) for item in self.items):
            raise ValidationError("An item of the instance cannot fit in the knapsack!")

    @property
    def size(self) -> int:
        return len(self.items)
```

We can clean this code up by tightening up the annotations a bit. 

```python
"""The 2D Knapsack problem module."""
from pydantic import Field
from typing import Annotated

from algobattle.problem import Problem, InstanceModel, SolutionModel, maximize
from algobattle.util import Role, ValidationError
from algobattle.types import u64, Interval, InstanceRef


item_height = Annotated[int, Interval(ge=1, le=InstanceRef.height)]
item_width = Annotated[int, Interval(ge=1, le=InstanceRef.width)]
point = tuple[item_height, item_width]


class Instance(InstanceModel):
    """Instances of 2D Knapsack."""

    height: u64 = Field(ge=1)
    width: u64 = Field(ge=1)


    items: list[point]

    @property
    def size(self) -> int:
        return len(self.items)
```

As you can see, we have moved all explicit checks from the `validate_instance`
method into the annotations. Do note that by using the `InstanceRef` import,
we are able to use the values of some keys to annotate other keys!

///note
If you are not familiar with pydantics annotations, we recommend
using the [pydantic documentation](https://docs.pydantic.dev/2.4/concepts/models/)
as a reference. As you have seen in the previous iteration of the code,
they are not essential, but very helpful to reduce code clutter and potential
mistakes.
///

This is already everything we need to implement for the instance. The `size`
method ensures that the number of items does not exceed the allowed limit given
by the instance size. We next turn to the solutions.

## Handling Solutions
The `packing` key is slightly more involved to construct. To
recapitulate, we would like this key to be a dictionary that maps
indices of items to a two-dimensional position and an indicator
whether they should be rotated. We use a similar approach as for the
`items` list. We additionally import the `Literal` class from the
`typing` module as well as the `SizeIndex` type alias from
`algobattle.types`.

```python
position_height = Annotated[int, Interval(ge=0, lt=InstanceRef.height)]
position_width = Annotated[int, Interval(ge=0, lt=InstanceRef.width)]
rotation = Literal["unrotated", "rotated"]


class Solution(SolutionModel[Instance]):
    """Solutions of 2D Knapsack."""

    packing: dict[SizeIndex, tuple[position_height, position_width, rotation]]
```

This of course does not at all ensure that the given solution is valid, yet.
We did not yet check whether items overlap or extend beyond the boundaries
of the knapsack. Since these checks are arguably beyond the scope of simple
type checking, we implement these tests explicitely in the `validate_solution`
method. For convenience, we import the `itertools` library.

```python
    def validate_solution(self, instance: Instance, role: Role) -> None:
        flattened_packing = []
        for index, (pos_height, pos_width, rotation) in self.packing.items():
            item_height = instance.items[index][0 if rotation == "unrotated" else 1]
            item_width = instance.items[index][1 if rotation == "unrotated" else 0]

            height_endpoint = pos_height + item_height
            width_endpoint = pos_width + item_width
            flattened_packing.append(
                (index, pos_height, height_endpoint, pos_width, width_endpoint)
            )

        if height_endpoint > instance.height or width_endpoint > instance.width:
            raise ValidationError(
                "Item extends the knapsack boundaries.",
                detail=f"Item {index} was placed at position ({pos_height, pos_width}), extending the knapsack boundaries."
            )

        for item, other_item in itertools.combinations(flattened_packing, 2):
            if item[1] < other_item[2] and item[2] > other_item[1]:
                if item[3] < other_item[4] and item[4] > other_item[3]:
                    raise ValidationError(
                        "Two items overlap.",
                        detail=f"Items {item[0]} and {other_item[0]} overlap."
                    )
```

We are almost done writing the problem class. The next step is to tell
the framework what the quality of a solution is, i.e. which values it
should compare when given two solutions to determine which is the better one.

```python
    @maximize
    def score(self, instance: Instance, role: Role) -> float:
        area = 0
        for index in self.packing:
            area += instance.items[index][0] * instance.items[index][1]
        return area
```

## Best Practice: Writing Tests

## Writing a Description

## Packaging Everything Together

## The Completed problem.py File
This is the final content of the `problem.py` that we have created.

```py title="problem.py"
"""The 2D Knapsack problem module."""
import itertools
from pydantic import Field
from typing import Annotated, Literal

from algobattle.problem import Problem, InstanceModel, SolutionModel, maximize
from algobattle.util import Role, ValidationError
from algobattle.types import u64, Interval, InstanceRef, SizeIndex


item_height = Annotated[int, Interval(ge=1, le=InstanceRef.height)]
item_width = Annotated[int, Interval(ge=1, le=InstanceRef.width)]
point = tuple[item_height, item_width]


class Instance(InstanceModel):
    """Instances of 2D Knapsack."""

    height: u64 = Field(ge=1)
    width: u64 = Field(ge=1)

    items: list[point]

    @property
    def size(self) -> int:
        return len(self.items)


position_height = Annotated[int, Interval(ge=0, lt=InstanceRef.height)]
position_width = Annotated[int, Interval(ge=0, lt=InstanceRef.width)]
rotation = Literal["unrotated", "rotated"]


class Solution(SolutionModel[Instance]):
    """Solutions of 2D Knapsack."""

    packing: dict[SizeIndex, tuple[position_height, position_width, rotation]]

    def validate_solution(self, instance: Instance, role: Role) -> None:
        flattened_packing = []
        for index, (pos_height, pos_width, rotation) in self.packing.items():
            item_height = instance.items[index][0 if rotation == "unrotated" else 1]
            item_width = instance.items[index][1 if rotation == "unrotated" else 0]

            height_endpoint = pos_height + item_height
            width_endpoint = pos_width + item_width
            flattened_packing.append(
                (index, pos_height, height_endpoint, pos_width, width_endpoint)
            )

        if height_endpoint > instance.height or width_endpoint > instance.width:
            raise ValidationError(
                "Item extends the knapsack boundaries.",
                detail=f"Item {index} was placed at position ({pos_height, pos_width}), extending the knapsack boundaries."
            )

        for item, other_item in itertools.combinations(flattened_packing, 2):
            if item[1] < other_item[2] and item[2] > other_item[1]:
                if item[3] < other_item[4] and item[4] > other_item[3]:
                    raise ValidationError(
                        "Two items overlap.",
                        detail=f"Items {item[0]} and {other_item[0]} overlap."
                    )

    @maximize
    def score(self, instance: Instance, role: Role) -> float:
        area = 0
        for index in self.packing:
            area += instance.items[index][0] * instance.items[index][1]
        return area


Problem(
    name="2D Knapsack",
    min_size=1,
    instance_cls=Instance,
    solution_cls=Solution,
)
```