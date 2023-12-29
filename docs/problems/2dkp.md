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
   │  ├─ Dockerfile
   │  ├─ problem.py
   │  └─ pyproject.toml
   ├─ results/
   ├─ solver/
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
can never be part of a valid solution.

Next, we need to specify how a solution looks like.

## Handling Instances

## Handling Solutions

## Writing a Mock Generator and Solver

## Best Practice: Writing Tests

## Writing a Description

## Packaging Everything Together