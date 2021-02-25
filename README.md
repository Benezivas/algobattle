# Algorithmic Battle

The lab course "Algorithmic Battle" is offered by the 
[Computer Science Theory group of RWTH Aachen University](https://tcs.rwth-aachen.de/)
since 2019. This repository contains the necessary code and documentation to
set up the lab course yourself.

The idea of the lab is to pose several, usually NP-complete problems during the
semester.  
Groups of students then write code that generates hard-to-solve instances for
these problems and solvers that solve these problems quickly. In the default
setting, the groups then battle against each other, generating instances of
increasing size that the other group has to solve within a time limit.  
Points are distributed relative to the biggest instance size for which a group
was still able to solve an instance.

# Installation and Usage
This project has been delevoped to run on Linux and may not work on other
platforms. Support for other platforms may be implemented in the future.

`python3` in version at least `3.6` and `docker` are required.

We recommend installing the package as a user using `pip`
```
pip install . --user
```

Adjust the parameters set in the `algobattle/configs/config.ini` file to set
which hardware resources you want to assign. You can pass alternative
configuration files to the script using the `--config_file` option.

To start a basic run on the `pairsum` problem, using the `solver` and `generator` that
are part of the problem directory, execute
```
battle algobattle/problems/pairsum
```
or provide any alternative problem folder path.

Read the section *Creating a New Task* to learn about the expected
structure of a problem.

The `battle` script offers several options, e.g. to give custom paths for
solvers and generators. Run `battle --help` for all options.

# How does a Battle Between Two Teams Work?
There are currently two types of battles implemented. The first one is the
*iterated* version, in which two teams battle against one another up to an 
instance size at which one of the teams fails. This is the default option.  
An alternative is the *averaged* battle, which is still relatively new and will
thus most probably be further adjusted in the future. In this battle, the
solvers and generators of students battle a fixed number of times on a fixed
instance size and try to give good approximative solutions. The approximation
factor is then averaged, with the team having the best average approximation
ratio winning.

Whenever we run the code as described above, we are supplied a generator and a
solver for each team, either explicitly via options on the call or implicitely
from the folders `path/to/problem/generator` and
`path/to/problem/solver` if the option is not set.

Log files are automatically generated for each run and saved to
`~/.algobattle_logs` by default. You can change this path with the
`--output_folder` option.

## The Iterated Battle (default)
What we are interested in is how good each solver of one group is in solving the
instances of the other group. Thus, we start by letting the generator of one
group generate an instance and a certificate for a small instance size (which we
will call `n`) and plug this instance into the solver of the other team. If the
solver is unable to solve this instance to our liking, the solver loses for this
`n`. This could be because its solution size is smaller than that of the
generator or for other reasons the problem description asks for. When a solver
actually solves an instance for an `n`, we have probably not seen the best the
solver can do: We want to see if it can also solve bigger instances. Thus, we
increment the `n`, let the generator create a new instance and plug it into the
solver again. This process is repeated until the solver fails.  
We then do the same by using the generator and solver of the respectively other
group.

While this is the general idea of how a battle works, there are some details
which were introduced to optimize the code and make it fairer.
### The Step Size Increment
When we want to increment the instance size, we can hardly know how big the
biggest instances are that a solver can solve. This is because we rarely know
how clever the instances of the generator are designed or how good the solver is
at solving them. They are essentially blackboxes for us.  
Thus, we do not want to simply increment the `n` by one every time the solver wins,
as we may wait for a very long time until we have results, otherwise.

In this implementation, we increase the step size more aggressively: If the
solver has solved `i` increments in a row already, the next step size increase
is `i^2`. This usually leads to the solver overshooting its target and failing
after a big increment. In this case, we set `i = 1`, take back the last, big
increment and start incrementing by `i^2` again. This is done until the solver
fails after an increment of `1`. To not overly favor randomized approaches, the
biggest instance size reached may not exceed that of each failed instance size.

Finally, there is also a cutoff value set in the `config.ini` after which the
incrementation is automatically stopped.
### Averaging the Results Over Several Battles
As the machines on which the code is executed cannot be guaranteed to be free of
load at every time and since randomized approaches may fail due to outliers, we
are executing several battles in a row and report back the results of each battle
such that an average number of points can be computed.
### Handling Malformed Inputs
We are very lenient with malformed instances: If an output line does not follow
the problem specification, the parser is tasked with discarding it and logging a
warning.  
If the verifier gets an empty instance or the certificate of the generator is
not valid, the solver automatically wins for this instance size. This usually
happens due to the generator timing out before writing the instance and
certificate out.
### Optional Approximative Battles
It is possible to allow for approximative solutions up to a fixed factor to be
a solution criteria. This can be easily set using the `--approx_ratio` option,
provided the problem is compatible with the notion of approximation.  
A solver then only fails if its solution is either invalid or outside the given
approximation ratio.

## The Averaged Battle
In this alternative battle version, we are interested in the students ability
to write good approximation algorithms. For a fixed instance size set with the
option `-approx_inst_size`, the students generate a number of instances set by
the option `--approx_iterations`. The task is then to provide an approximative
solution that is as close to the optimal solution as possible within the solver
time limit.  
The approximation ratios are then averaged, and points are awarded relative to
the averaged ratio of the other team.

# Creating a New Task
Tasks are created as packages and are automatically imported by supplying their
path to the `battle` executable.

The basic directory structure of a task is the following:
<pre>
newtask
├── generator
│   └── Dockerfile
├── solver
│   └── Dockerfile
├── parser.py
├── problem.py
├── verifier.py
└── __init__.py
</pre>

The `problem.py` file is the easiest to fill. It defines a new subclass of the
abstract `Problem` class, imports the verifier and parser and sets the lowest
value for which a battle is to be executed for the specific problem.

The `parser.py` implements methods that are used for cleaning up whatever
instance or solutions the solvers and generators produce, such that the verifier
is able to semantically check them for correctness. Lines of the input that do
not conform to the defined format are discarded, along with a warning.

The `verfier.py`, as already mentioned, checks the input semantically. At least
two functions need to be implemented: One that verifies that a solution is
correct for an instance and one that verifies that a solvers solution is of a
required quality (usually that its size is at least equal to that of the
generator). The verifier should be able to handle the cases that an empty
instance is given (the solution is automatically valid) or that an empty
solution is given (the solution is automatically invalid).

In order to integrate a problem file, an `__init__.py` is required that contains
an import of the class created in the `problem.py` file, renaming it to
`Problem`:
```
from .problem import MyNewProblemClass as Problem 
```
In order to test the functionality of your problem implementation, it is
recommended to create a dummy `solver` and `generator` in the problem directory.
These can return the same instance and solution for each instance size, assuming
the problem definition allows this. The `solver` and `generator` folders are
also the default paths for solvers and generators of both teams if no other path
is given.

If you want to execute a run on your newly created problem, execute
```
battle /path/to/newtask
```
There are a few example tasks in the `algobattle/problems` directory of this
repository with task descriptions, if you want a reference for creating your own
tasks.