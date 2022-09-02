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

# Installation
This project has been delevoped to run on Linux and may not work on other
platforms. Support for other platforms may be implemented in the future.

`python3` in version at least `3.10` and `docker` are required.

We recommend installing the package as a user using `pip`
```
pip install . --user
```
When installing the package on windows, specify the `windows` optional dependencies
```
pip install .[windows] --user
```

Adjust the parameters set in the `algobattle/configs/config.ini` file to set
which hardware resources you want to assign. You can pass alternative
configuration files to the script using the `--config_file` option.


# Usage
This repository does not include any practical problems. For a selection of problems
that have been posed to students in practice, have a look at the
[algobattle-problems](https://github.com/Benezivas/algobattle-problems) repository.

To start a basic run on a problem, using the `solver` and `generator` that
are part of the problem directory, use
```
algobattle path/to/concrecte/problem/folder
```

The `algobattle` script offers several options, e.g. to give custom paths for
solvers and generators. Run `algobattle --help` for all options.


Check the [wiki](https://github.com/Benezivas/algobattle/wiki) for further documentation.