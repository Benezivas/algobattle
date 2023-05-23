# Battle Types

When Algobattle runs a match it executes several battles that score how good one team is at solving another team's
instances. In this page we will take a look at how exactly this works by going through all battle types.

///note
Algobattle lets users create custom battle types. If you're looking for information to how the battle type you're using
works and can't find it here it is best you ask your course instructor about it.
///

# Iterated

The basic idea behind iterated battles is very straightforward. Generally solving bigger instances is much harder than
solving smaller ones. So we can judge how well a solver is doing by searching for the biggest instance size it can
solve correctly. But we of course the only thing we care about isn't just whether a solver is able to solve some
instance, but whether it is able to do so using a reasonable amount of system resources. 
Algorithmically this means that we give each program some fixed amount of time, memory space, and cpu cores and then
try to find the largest size where the solver can still correctly solver instances generated for it. The easiest way to
do this would be to just steadily increase the instance size one by one and stop when the solver fails.

A big issue with this is that "hard" instance sizes may be rather large. For example, even a very inefficient solver
can easily solve Pairsum instances containing less than a few hundred numbers within seconds. To speed things up
iterated battles take a more aggressive approach, they increase the instance size in larger (and growing) steps until
the solver fails. For example, the progression of instance sizes might be 1, 2, 5, 14, 30, 55, 91, etc. This quickly
gives us a rough idea that we then fine tune recursively. Say the biggest size the solver can tackle is 64, this first
series of fights would then succeed til 55 and fail at 91. The progression is then restarted at 55 going up, 56, 60, 64,
73, etc. Here the solver fails at 73 which causes the battle to again reset the size to 65. The solver again fails at
this size, which means that the battle has found the correct size since the solver succeeded at everything below 64 but
not anything higher.

This system works very well for programs that have a very sharp cutoff between instance sizes they can solve easily and
ones they struggle with. On the other hand, it has trouble assessing ones that operate with random elements since they
might fail very early due to bad luck. To smooth things out and provide a fair experience for many approaches the
Iterated battle repeats this process of increasing the instance size several times and averages the reached sizes.

# Averaged

It can also be interesting to restrict generators and solvers to a very narrow set of possible instances and see what
possibilities for optimization this opens up. In particular, instead of considering how good a solver is at dealing
with instances of increasing size we can judge how well it is at solving instances of a single, fixed size. This
changes the thought process when writing the programs to favor more specialized approaches that try to tease out the
best possible performance.

Averaged battles fix not only the program runtime, memory, and cpu access, but also the instance size. A series of
fights is run with these parameters and their results averaged.
