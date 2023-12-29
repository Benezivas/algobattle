# Battle Types

When Algobattle runs a match it executes several battles that score how good one team is at solving another team's
instances. In this page we will take a look at how exactly this works by going through all battle types.

!!! note "Custom battle types"
    Algobattle lets users create custom battle types. If you're looking for information to how the battle type you're
    using works and can't find it here it's best you ask your course instructor about it.

## Iterated

The basic idea behind iterated battles is very straightforward. Generally solving bigger instances is much harder than
solving smaller ones. So we can judge how well a solver is doing by searching for the biggest instance size it can
solve correctly. But we of course the only thing we care about isn't just whether a solver is able to solve some
instance, but whether it is able to do so using a reasonable amount of system resources. 
Algorithmically this means that we give each program some fixed amount of time, memory space, and CPU cores and then
try to find the largest size where the solver can still correctly solver instances generated for it. The easiest way to
do this would be to just steadily increase the instance size one by one and stop when the solver fails.

A big issue with this is that "hard" instance sizes may be rather large. For example, even a very inefficient solver
can easily solve Pairsum instances containing less than a few hundred numbers within seconds. To speed things up
iterated battles take a more aggressive approach, they increase the instance size in larger (and growing) steps until
the solver fails. For example, the progression of instance sizes might be 1, 2, 5, 14, 30, 55, 91, etc. This quickly
gives us a rough idea that we then fine tune recursively. Say the biggest size the solver can tackle is 64, this first
series of fights would then succeed until 55 and fail at 91. The progression is then restarted at 55 going up, 56, 60, 64,
73, etc. Here the solver fails at 73 which causes the battle to again reset the size to 65. The solver again fails at
this size, which means that the battle has found the correct size since the solver succeeded at everything below 64 but
not anything higher.

This system works very well for programs that have a very sharp cut-off between instance sizes they can solve easily and
ones they struggle with. On the other hand, it has trouble assessing ones that operate with random elements since they
might fail very early due to bad luck. To smooth things out and provide a fair experience for many approaches the
Iterated battle repeats this process of increasing the instance size several times and averages the reached sizes.

### Config

The Iterated battle type uses the following keys in the `match.battle` table in addition to `#!toml type = "Iterated`:

`rounds`
: Number of rounds that will be run and averaged. A _round_ is one sequence of fights until a size has been found
where the solver succeeds at all smaller sizes and fails at all bigger ones. Defaults to 5.

`maximum_size`
: Maximum size that will be iterated to. Defaults to 50000.

`exponent`
: An integer that determines how quickly the size increases. For example, an exponent of 2 results in a size sequence
of 1, 2, 6, 15, 31, etc. while an exponent of 3 leads to 1, 2, 9, 36, 100, 255, etc. Defaults to 2.

`minimum_score`
: A float between 0 and 1 (inclusive) that is the minimum score a solver needs to achieve to "successfully" solve
an instance. Defaults to 1.

`max_generator_errors`
: If a generator fails to produce a valid instance, the solver wins the fight by default. This may create very lengthy
battles where the generator keeps failing at higher and higher `max_size`s. You can use this setting to early exit and
award the solver the full score if this happens. Set to an integer to exit after that many consecutive failures, or
`#!toml "unlimited"` to never exit early.

### UI Data

Iterated battles display two values to the UI:

reached
: The biggest instance size reached in each round so far.

cap
: The current cap on the instance size.

## Averaged

It can also be interesting to restrict generators and solvers to a very narrow set of possible instances and see what
possibilities for optimization this opens up. In particular, instead of considering how good a solver is at dealing
with instances of increasing size we can judge how well it is at solving instances of a single, fixed size. This
changes the thought process when writing the programs to favour more specialized approaches that try to tease out the
best possible performance.

Averaged battles fix not only the program runtime, memory, and CPU access, but also the instance size. A series of
fights is run with these parameters and their results averaged.

### Config

`instance_size`
: The instance size every fight in each match will be fought at. Defaults to 25.

`num_fights`
: The number of fights that will be fought in each match. Defaults to 10.

### UI Data

Averaged battles display a single value to the UI:

round
: The current round that is being fought.


## Improving

The idea behind this battle type is that the teams don't just create the best possible instances and solutions out of
thin air, but try to learn over time and improve their output. We run multiple rounds, similar to
[Averaged battles](#averaged), but programs will also receive information about the previous round's result. By default,
this includes their score, the instances, and each program's own solutions.

!!! example "Example program input"
    Using the default settings and the Pairsum problem, in the third round the solver would see an input folder
    like this:

    ``` { .sh .no-copy }
    /input
    ├─ instance.json
    ├─ info.json
    └─ battle_data/
       ├─ 0/
       │  ├─ score.txt
       │  ├─ instance.json
       │  └─ solver_solution.json
       └─ 1/
           ├─ score.txt
           ├─ instance.json
           └─ solver_solution.json
    ```

    The `instance.json` file contains the actual instance that needs to be solved this round. The folders in
    `/input/battle_data` are named after the index of each previous fight and contain that fight's data.

!!! attention "Missing files"
    The instance and solution files may be missing in some or all of the fights. This happens if e.g. one of the
    programs crashes or outputs invalid data. In those cases the battle will continue with the corresponding files
    not existing in the input folder. Always check if the files are actually there and have a fallback ready!

You can also configure this battle type to only include some of this information or reveal even more details about the
previous fights to each team. This can lead to interesting challenges where e.g. every instance and generator's solution
is fully revealed and the generating team thus needs to come up with very different instances every run.

The overall score is calculated by averaging each round's score, but with later fights being weighted more. This means
that cleverly using the given information about previous fights is more important than just having strong programs.

### Config

`instance_size`
: The instance size every fight in each match will be fought at. Defaults to 25.

`num_fights`
: The number of fights that will be fought in each match. Defaults to 10.

`weighting`
: How much additional weight each successive fight receives in the overall score. Needs to be a positive integer that
expresses percentages. E.g. a `weighting` of `2` means the second fight is twice as impactful as the first, the third
four times, etc. Note that series exhibits exponential growth and thus `weightings` close to `1` should be used to not
make all but the last few fights matter. Defaults to `1.1`.

`scores`
: A set of roles (a role is either `#!toml "generator"` or `#!toml "solver"`) that specifies which programs will see
each previous rounds' scores. Defaults to `#!toml ["generator", "solver"]`.

`instances`
: Similar to `scores` but regarding the problem instances. Defaults to `#!toml ["generator", "solver"]`.

`generator_solutions`
: Similar to `scores` but regarding the generator's solutions (if the problem uses them). Defaults to
`#!toml ["generator"]`.

`solver_solutions`
: Similar to `scores` but regarding the solver's solutions. Defaults to `#!toml ["solver"]`.

### UI Data

Improving battles display a single value to the UI:

round
: The current round that is being fought.
