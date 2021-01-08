# Algorithmic Battle (Lab course at tcs.rwth-aachen.de)

The lab course "Algorithmic Battle" is offered by the [Computer Science Theory group of RWTH Aachen University](https://tcs.rwth-aachen.de/) since 2019. This repository contains the necessary code and documentation to set up the lab course yourself. 

The idea of the lab is to pose several, usually NP-complete problems during the semester.  
Groups of students then write code that generates hard-to-solve instances for these problems and solvers that solve these problems quickly.
The groups then battle against each other, generating instances of increasing size that the other group has to solve within a time limit.  
Points are distributed relative to the biggest instance size for which a group was still able to solve an instance.

# Installation and Usage
`python3` and `docker` are required to run this code. We recommend using the latest version of `docker` on your machine, as your students may want to use the lastest features for their code.

Adjust the parameters set in the `config.ini` to set which hardware ressources you want to assign to the students code.

To start a basic run on a given problem, using the `solver` and `generator` that are part of the problem directory, execute
```
./run.py /path/to/problem
```
The `run.py` offers several options, e.g. to give custom paths for solvers and generators. Run `./run.py --help` for all options.

# Creating a new Task
Tasks are created as packages and are automatically imported by supplying 
their path to `run.py` if the `__init__.py` of the task is correctly 
configured.

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

The `problem.py` file is the easiest to fill. It defines a new subclass
of the abstract `Problem` class, imports the verifier and parser and sets
the lowest value for which a battle is to be executed for the specific problem.

The `parser.py` implements methods that are used for cleaning up whatever
instance or solutions the solvers and generators produce, such that the
verifier is able to semantically check them for correctness. Lines of the input
that do not conform to the defined format are discarded, along with a warning.

The `verfier.py`, as already mentioned, checks the input semantically.
At least two functions need to be implemented: One that verifies that a solution
is correct for an instance and one that verifies that a solvers solution is of
a required quality (usually that its size is at least equal to that of
the generator). The verifier should be able to handle the cases that an empty
instance is given (the solution is automatically valid) or that an empty solution
is given (the solution is automatically invalid).

In order to integrate a problem file, an `__init__.py` is required that
contains an import of the class created in the `problem.py` file, renaming it to
`Problem`:
```
from .problem import MyNewProblemClass as Problem 
```
In order to test the functionality of your problem implementation, it is
recommended to create a dummy `solver` and `generator` in the problem directory.
These can return the same instance and solution for each instance size,
assuming the problem definition allows this. The `solver` and `generator`
folders are also the default paths for solvers and generators of both teams
if no other path is given.

If you want to execute a run on your newly created problem, execute
```
./run.py /path/to/newtask
```
There are a few example tasks in the `problems` directory of this repository
with task descriptions, if you want a reference for creating your own tasks.
