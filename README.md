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
This project is developed and tested on all major operating systems.
We require `docker` and `python3` in version at least `3.11`.

Please consult the official [documentation](www.algobattle.org/docs/)
for detailed instructions on installation and usage.

# Related projects
This repository only includes the core framework for executing an `Algorithmic
Battle`. For a selection of concrete problems that you can use to play around
with the framework, have a look at the
[algobattle-problems](https://github.com/Benezivas/algobattle-problems)
repository. These are problems that have been posed to students in some form
over the years.

While the framework provides all essential tools to host a tournament, e.g. in
the form of a lab course yourself, you may be interested in the
[algobattle-web](https://github.com/Benezivas/algobattle-problems) project.  The
`algobattle-web` project implements a webframework with which you are able to
comfortably manage your students teams and their code, your problem files and
their documentation as well as schedule matches to be fought between registered
student teams, using the `algobattle` API.

# Contributing
Feel free to open issues and pull requests if you feel the design of the code
could be improved. We have developed this project on the basis of practical
experience inside our lab courses, thus some design elements may be unintuitive
to you. We welcome any input on how to make this project accessible to as many
people as possible.

# Funding
The development of version `4.0.0` was funded by
[`Stiftung Innovation in der Hochschullehre`](https://stiftung-hochschullehre.de/en/) (Project 
`FRFMM-106/2022 Algobattle`) and by the [Department of Computer Science of
RWTH Aachen University](https://www.informatik.rwth-aachen.de/go/id/mxz/?lidx=1).