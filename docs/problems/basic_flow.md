# Basic Interactions
## Interactions between the Framework and Problems

We take a look at the structure of a problem in three steps. In this part of the
tutorial, we will first talk about the high-level interaction between a problem
and the `algobattle` framework. Second, we will generate a mock problem and see
where these high-level concepts are implemented.  Lastly, we will build a
concrete problem.

### What is the Flow of an Algobattle run?

We first need to understand the basic steps of how the framework will interact
with the problem file that we want to create.  This is not very complicated.
Assume you start a run of `algobattle` with two teams configured in the
`algobattle.toml`, like so:

```toml
[match]
problem = "Pairsum"

[teams.Penguins]
generator = "peng_generator"
solver = "peng_solver"

[teams.Squirrels]
generator = "squi_generator"
solver = "squi_solver"
```

The `peng_generator` will automatically be given access to a file
`/input/max_size.txt` that contains the size of the instance to be generated.
The generator is then expected to write two files: `/output/instance.json` and
`/output/solution.json`. The framework will by default expect these two files to
be present after a run of a generator. If not, the generators run is counted as
a failure.

Here is the first point at which we need to write some code. We need to ensure
that the instance is formatted exactly as we want it to be. We need to catch and
handle any deviation from the format that we expect. Luckily, the framework
does most of the heavy lifting for this, as we will see soon.

If the instance is formatted in accordance to our specification, our code next
needs to check the certificate solution. As with the instance, we first need to
check if the solution is well-formatted. As an additional step, we need to check
if the certificate contains a valid solution for the given instance.

///note
The quality of the solution does not matter at this point! We only want
to check if the solution is *valid*.
///

If this is the case, our problem file needs to tell the framework what the
*size* of the solution is. This will later be used to check if the solution of
the other teams `squi_solver` is better or worse than the certificate one. 

///note
This comparison itself is done by the framework. You can specify if a
smaller or larger solution is better.
///

If all checks are successful, the framework handles the job of supplying the
instance to the other teams solver, which may expect a file
`/input/instance.json` upon being run. The solver itself then outputs another
file `/output/solution.json`. This is then handled exactly in the same way as
the certificate solution of the generator, if not specified otherwise. This
means you do not need to write additional code for handling the solvers
solution.

///note
If you *do* want to handle the solutions of solvers and generators differently,
the `validate_solution` method supplies a `role` argument that you can use.
///

And that is all we need to take care of.
