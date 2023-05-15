# Overview

This is the Algobattle tutorial. It's the best starting place to learn more about what the package does and how you can
use it. It's designed to require as little background knowledge as possible, but it's best if you are familiar with
basic ideas of computer science, object-oriented programming, and Python in particular.

First, we'll take a look at the broad structure of everything and the terms we use. The following pages then build on
each other to delve deeper into each concept. At the end you'll be ready to use the package to either participate in
a lab course or organize one. Not everything is covered in it though, optional topics that not everyone needs to
understand are explained in the [advanced guide](/advanced/index.md).

/// tip
If you prefer a more hands-on approach you can skip directly to the [next page](installation.md) and use this
as a reference page to come back to.
///

## Problems

The Algobattle lab course is about solving algorithmic problems. So what is that exactly? From a theoretical computer
science perspective this doesn't have a clear answer, there are decision problems, function problems, optimization
problems, etc. What all of them share is that a problem is a description of what its instances look like, and what
correct solutions to them are.

Let's look at an example problem,
[Pairsum](https://github.com/Benezivas/algobattle-problems/tree/main/problems/pairsum):  
The abstract definition of it is that given a list of natural numbers, the task is to find two pairs of numbers in it
with the same sum. For example, in the list `1, 2, 3, 4, 5` we find `2 + 5 = 3 + 4`.

Of course, we don't want to just accept any four numbers that sum to the same, they need to be numbers actually present
in the list. The easiest way to ensure this is making the solution actually contain four indices into the instance list
instead of the numbers found there. Then our example solution becomes `l[1] + l[4] = l[2] + l[3]`.

To make it possible for programs to easily interact with this abstract definition, we need to specify what exactly a
problem instance and solution looks like. Since Pairsum only uses simple numerical data, it uses regular json. The
example instance then looks like this:

```json
{!> pairsum_instance.json!}
```

And its solution is:

```json
{!> pairsum_solution.json!}
```

/// note
Most other problems also use json because it's such an easy to use and widely supported format. But some problems need
to encode more exotic data and thus use different formats.
///

We can already see an important property of problem instances: their _size_. You can easily find a correct pairing
in a list of 5 elements by hand, but that becomes much more difficult if there's 5000 numbers instead. Different
problems define the size of their instances differently, but it is usually in line with the natural notion of it. For
example, common graph problems use the number of vertices, numerical problems the size or amount of numbers, etc.
Generally, larger instances are significantly harder to solve and as such we never compare instances of different sizes
directly. Teams compete against each other based on how big the biggest size they can solve is, how quickly they can
solve instances of the same size, etc.

Another thing about Pairsum is that its solutions are scored purely on a pass/fail basis. Either you've found numbers
that add up correctly or you didn't. This is different for other problems such as finding the biggest independent set
in a graph. In that problem we can compare two solutions and say that one is, say, 20% better than the other since it
contains 20% more vertices.

## Programs

Each team of students now is tasked with writing code to actually solve such problems. But not only that, they also need
to generate instances for the other teams to solve. This means that each team needs to not only think about efficient
ways to take arbitrary instances and find solutions for them, they need to also figure out what it is about instances
that makes them particularly challenging.

Each team writes two _programs_ for this, a _solver_ and a _generator_. The generator will take a size as input and
produce a problem instance. The solver takes an instance and creates a solution for it. In tournament matches, teams
will always generate instances that other teams' solvers then attempt to solve, but teams can also run their own solvers
against their generator in order to practice and debug.

We use docker to provide each team with a fair and controlled environment to execute their code in. A program really
just is a docker image that we then run as a new container every time a new instance is to be generated or solved. This
lets students choose their approach and tools incredibly freely, there is no constraint to specific programming
languages, system setups, libraries used, etc. On the other side, we maintain total control over the runtime
environment. Because all student code is executed inside a container there is no danger of it manipulating the host
system maliciously and its resource use and runtime can be easily limited.


/// abstract | Docker basics
Docker is a tool that lets you share code in controlled environments. Say you have some rust code that also requires
C++ external libraries. If I want to run that, I'd need to first install both the rust and a C++ compiler and set up
my environment variables like `$Path` properly. If I don't know exactly what your code needs and how it works that'll be
really annoying and finicky.  
By using Docker you can instead just create an _image_. This is basically a small virtual machine that has whatever you
want installed and configured. I then take that and create a _container_ from it, which runs the code exactly like you
specified.

You can find much more detailed info on how Docker works on [the official site](https://docs.docker.com/get-started/).
If you just want to know how to use it to write your team's programs, [this part](programs.md) of the tutorial will tell
you all the basics.
///

## Matches

Now we can talk about the most exciting part of Algobattle, the actual matches themselves! They're what happens when you
run the project code and will score how well each team's programs are performing. A match pairs up every team against
every other team and then runs a _battle_ with that specific matchup of teams. Once all the battles have run, it
compares all the scores achieved in them to calculate overall scores for every team.

So each battle is between two specific teams. In particular, one team is tasked with generating problem instances, and
the other attempts to solve them. The battle judges how well the teams did against each other calculates a score based
on that. How exactly this happens depends on the particular battle type chosen for the match. The default battle type
sets a static time limit for the generator and solver and then increases the instance size until the solver can no
longer compute a valid solution for the generated instance within that time limit. If, for example, team `dogs` is
very good at generating hard instances and team `cats` can only solve them up til size 50, then the battle would
roughly start with `dogs` creating an instance of size 5, which `cats` can easily solve, this repeats at size 10, then
20, etc., until a size bigger than 50 is reached and the solver of `cats` can no longer provide a correct solution. The
score would then be 50.

Each of these cycles of one team's generator creating an instance of a specific size and the other team's solver trying
to calculate a valid solution is called a _fight_. Each fight is run with some set of parameters determined by the
battle and uses these to control how the programs are run.

The result of a fight is summarized by its _score_. This is a real number between 0 and 1 (inclusive) that indicates how
well the solver did. A score of 0 means it did not provide a valid solution, and 1 that it solved it perfectly.
Fractional scores can happen when for instance the problem is to find the biggest vertex cover and the solver finds one
that is 80% of the size of the optimal one. In this case, the fight would have a score of 0.8.
