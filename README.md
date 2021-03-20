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

Check the [wiki](https://github.com/Benezivas/algobattle/wiki) for further documentation.