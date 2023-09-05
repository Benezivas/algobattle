# Configuration

So far we've only discussed the default settings for everything, but Algobattle offers many different ways of
customizing exactly how matches are run.

## Command line options

The command line interface lets you specify a few things directly in the terminal. These mainly just let you specify
how the match should behave as a cli program, the actual match config is done through config files.

///tip
Running `algobattle --help` will bring up a short description of each of these inside your terminal.
///

`path`

: This is the only positional argument. It should either be the path to a config file or one to a directory containing
one that is called `config.toml`.

`--silent` / `-s`

: Setting this will hide the match output in the terminal.

`--result` / `-r`

: This accepts a path to some directory. If it is set the match will be saved as a json file in that directory. It
includes a lot of useful info that is not displayed to the terminal during execution such as error messages from
programs that failed.

## Config files

Config files are toml files that Algobattle uses to fine tune how a match is run. All settings in it are entirely
optional with commonly used default values. Files that aren't properly formatted toml, or ones that have the wrong
layout of keys/values lead to the match being stopped with an appropriate error message.

///question | Unsure about toml syntax?
Toml syntax can be a bit confusing if you're unfamiliar with it, a full explanation of it can be found on
[the official site](https://toml.io/en/).
///

An example config file filled with default values looks like this:

/// example

```toml
{!> config.toml !}
```

///

### Teams

The teams table contains keys that are each team's name. Values are tables containing paths to the generators and
solvers.

/// example

```toml
[teams.cats]
generator = "cats/generator"
solver = "cats/solver"

[teams.dogs]
generator = "dogs/generator"
solver = "dogs/solver"
```

///

### Match

The match table contains settings that specify what the match is like. These can drastically change what happens during
execution and what the result looks like. Because of this, students should use the same match settings as are used during
in the tournament.

`problem`

: The problem this match is about. Can either be specified as the name of an installed problem, or a path to a
file containing one.

`build_timeout`

: Time limit each program's image has to build, or `#!toml false` for no limit. Can either be a number of seconds or a
string in `HH:MM:SS` format.

`strict_timeouts`

: Programs may run into their timeout despite already having generated their output. For example, a solver might try
to incrementally improve the solution it has found. This setting determines how these cases are handled, if it's set
to `#!toml true` trying to exceed the time limit is considered a completely unsuccessful program execution and
is treated similar to if it had crashed completely. If it is `#!toml false`, the program will just be halted after
the allotted time and any solution it may have generated is treated as is.

`image_size`

: Limit the maximum size a Docker image may be, or `#!toml false` to allow arbitrarily large programs. Note that this
limits the disk space each image may take up, not the memory used during program execution. Can be specified as
either a number of bytes or a string with a unit such as `#!toml "2.5 GB"`.

`generator` / `solver`

: Both of these fields accept the same type of dictionary. It can contain `timeout`, `space`, and `cpus` keys that
limit the corresponding resource access to the generator and solver programs. Timeouts are specified in the same
format as `build_timeout` and memory space limits the same as `image_size`. Cpus limit the number of physical cpu
cores the program can use and has to be an integer.

### Battle

This contains the setting specifying what battle type to use and further options for each battle type. Each type can
specify its own settings and the available battle types are user extensible. Here we list the settings used by the
included types. Their full behavior is documented at the [battle types page](battle_types.md).

`type`

: Selects the battle type the match uses. Must be the name of an installed battle type, by default these are
`Iterated` and `Averaged` but more can be installed.

#### Iterated

`rounds`

: Number of rounds that will be run and averaged. A _round_ is one sequence of fights until a size has been found
where the solver succeeds at all smaller sizes and fails at all bigger ones.

`maximum_size`

: Maximum size that will be iterated to.

`exponent`

: An integer that determines how quickly the size increases. For example, an exponent of 2 results in a size sequence
of 1, 2, 6, 15, 31, etc. while an exponent of 3 leads to 1, 2, 9, 36, 100, 255, etc.

`minimum_score`

: A float between 0 and 1 (inclusive) that is the minimum score a solver needs to achieve to "successfully" solve
an instance.

#### Averaged

`instance_size`

: The instance size every match will be fought at.

`num_fights`

: The number of fights that will be fought in each match.

### Execution

These are settings that purely determine _how_ a match is fought. Students can freely change these without creating
any differences in how their code runs locally and in tournaments.

`points`

: An integer specifying the maximum number of points a team can achieve during this match. How points are calculated
is explained in more detail [here](match.md#points-calculation). The point total for each team will be displayed in
the terminal after the match.

`parallel_battles`

: To speed up battle execution you can let Algobattle run multiple battles in parallel. Note that while programs can
not directly interact with each other, they might still end up interfering with other programs that are being run at
the same time. In particular, they might attempt to use the same cpu, memory, or disk resources as another program
being run at the same time. You can use the `set_cpus` option to mitigate this risk.

`set_cpus`

: Similar to the Docker `--cpuset-cpus` option documented
[here](https://docs.docker.com/config/containers/resource_constraints/). Many modern cpus have different types of
physical cores with different performance characteristics. To provide a level playing field it can be good to limit
Algobattle to only use certain cores. To do this, specify either a comma separated list of cores (the first is
numbered 0) such as `0,1,3,5` or a range like `0-4`. Note that the formatting is very important here, you can not
mix the two styles or add any spaces or similar.

    This option accepts either a single such string, or a list of them. If a list is provided each battle that is run
    in parallel will use one of the provided set of cores. For example, if this option is `["0,1", "2-3", "4,5"]` and
    there are two battles executed at the same time, the first would use the first two physical cpus and the second the
    next two.

`mode`

: Either `"tournament"` or `"testing"`. When set to tournament the docker containers are not given tags and are
cleaned up after the match to prevent potential exploits. Using the testing mode often is nicer since it lets Docker
use the build cache and thus massively speeds up development.

### Docker

The docker table contains settings that are passed through to the Docker daemon without influencing Algobattle itself.
You generally should not need to use these settings. If you are running into a problem you cannot solve without them,
we recommend first opening a discussion on [our GitHub](https://github.com/Benezivas/algobattle/discussions) to see if
we can add this functionality to Algobattle directly.

///danger
Many of these settings are very complicated and have potentially disasterous consequences. We recommend not using any of
these settings unless you are absolutely sure what the ones you are modifying do. Improper Docker Daemon configuration
may not only break Algobattle but can give attackers root access to your host machine.
///

`build`

: Table containing parameters passed to the docker build command. Further documentation can be found on
[the Docker build site](https://docs.docker.com/engine/reference/commandline/build/).

`run`

: Table containing parameters passed to the docker run command. Further documentation can be found on
[the Docker run site](https://docs.docker.com/engine/reference/commandline/run/).
