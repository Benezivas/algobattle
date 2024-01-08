
# Algobattle

Algobattle is a framework that lets you run tournaments where teams compete to solve algorithmic problems.
It is being developed by the [Computer Science Theory group of RWTH Aachen University](https://tcs.rwth-aachen.de/),
which also offers a lab course based on it since 2019. This repository contains the code that instructors and students
need to run the tournament itself. In addition to that, we also develop Algobattle Web, a web server providing an
easy-to-use interface to manage the overall structure of such a course.

The idea of the lab is to pose several, usually NP-complete problems over the course of the semester. Teams of students
then write code that generates hard-to-solve instances for these problems and solvers that solve these problems quickly.
The teams then battle against each other, generating instances for other teams, and solving instances that were
generated for them. Each team then is evaluated on its performance and is awarded points.


## Where to start reading

The Algobattle documentation is aimed at two different groups of people: students participating in lab courses, and
instructors running them. In order to keep everything short and sweet we've structured our documentation so that
everyone can easily focus just on what they need to learn about.

For everyone, the best place to start learning more about Algobattle is by reading through
[the tutorial](tutorial/index.md). It contains everything you need to know to use the framework and start working with
it. Students won't necessarily need anything further to participate in the course, but may later run into things they
can best look up in the [advanced section](advanced/index.md).

After finishing the tutorial we then recommend instructors to go through the topics in the
[instructor's corner](instructor/index.md). This will get you up to speed to run an Algobattle lab course on your own.

!!! tip "Just want a broad overview?"
    If you're not yet interested in reading all the nitty-gritty and just want a basic idea of how such a Lab course
    works to decide if you want to run one yourself, the [teaching concept](instructor/teaching_english.md) is ideal
    for you!

## Requirements

This project is being developed and tested on both Windows and Linux, macOS support is being worked on but still is
tentative. We require python version 3.11 or higher and Docker.

/// note
You can find more detailed information on this, including how to install everything, in
[the tutorial](tutorial/installation.md).
///

## License

This project is freely available under the MIT license.
