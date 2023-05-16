# Configuration

So far we've only discussed the default settings for everything, but Algobattle offers many different ways of
customizing exactly how matches are run.

## Command line options

The command line interface lets you specify a few things directly in the terminal. These mainly just let you specify
how the match should behave as a cli program, the actual match config is done through config files.

///tip
Running `algobattle --help` will bring up a short description of each of these inside your terminal.
///

`problem`

:   This is the only positional argument. It is either the name of the problem you want to use or a path to it.
    A more detailed explanation can be found [here](match.md#selecting-a-problem)

`--silent` / `-s`

:   Setting this will hide the match output in the terminal.

`--result_output`

:   This accepts a path to some directory. If it is set the match will be saved as a json file in that directory. It
    includes a lot of useful info that is not displayed to the terminal during execution such as error messages from
    programs that failed.

`--config`

:   This accepts a path to a config toml file. What exactly it can contain is explained in the next section.

## Config files

Config files are toml files that Algobattle uses to fine tune how a match is run. All settings in it are entirely
optional with commonly used default values. Files that aren't properly formatted toml, or ones that have the wrong
layout of keys/values lead to the match being stopped with an appropriate error message.

///question | Unsure about toml syntax?
Toml syntax can be a bit confusing if you're unfamiliar with it, a full explanation of it can be found on
[the official site](https://toml.io/en/).
///

An example config file filled with default values looks like this:

```toml
{!> config.toml !}
```

///note
The commented out fields are advanced config options that default to `None`. Since toml does not have a None type, you
need to leave out the keys entirely or provide your own values.
///

The top level keys are:

`battle_type`

:   This is the name of the battle type that is used for the match. Read [this](battle_types.md) to get an overview of
    the different possible options.

`points`

:   An integer specifying the maximum number of points a team can achieve during this match. How points are calculated
    is explained in more detail [here](match.md#points-calculation).

`parallel_battles`

:   To speed up battle execution you can let Algobattle run multiple battles in parallel. Note that while programs can 
    not directly interact with each other, they might still end up interfering with other programs that are being run at
    the same time. In particular, they might attempt to use the same cpu, memory, or disk resources as another program
    being run at the same time. You can use the `program.set_cpus` option to mitigate this risk.

`mode`

:   Either `"tournament"` or `"testing"`. When set to tournament the docker containers are not given tags and are
    cleaned up after the match to prevent potential exploits. Using the testing mode often is nicer since it lets Docker
    use the build cache and thus massively speeds up development.

`teams`

:   A list of dictionaries each containing a string `name`, and `generator` and `solver` paths. If you want to run
    a battle between multiple teams, or have placed the programs at different locations you can use this to specify
    where every team's programs are found.

### Program

`build_timeout`

:   Number of seconds each program's Docker image has to complete its build step. Set to 0 to indicate no timeout.

`strict_timeouts`

:   Programs may run into their timeout despite already having generated their output. For example, a solver might try
    to incrementally improve the solution it has found. This setting determines how these cases are handled, if it's set
    to `#!toml true` trying to exceed the time limit is considered a completely unsuccessful program execution and
    is treated similar to if it had crashed completely. If it is `#!toml false`, the program will just be halted after
    the allotted time and any solution it may have generated is treated as is.

`image_size`

:   An integer (in MB) that limits the maximum size a Docker image may be. Set to 0 to allow arbitrarily large programs.
    Note that this limits the disk space each image may take up, not the memory used during program execution.

`set_cpus`

:   Similar to the Docker `--cpuset-cpus` option documented
    [here](https://docs.docker.com/config/containers/resource_constraints/). Many modern cpus have different types of
    physical cores with different performance characteristics. To provide a level playing field it can be good to limit
    Algobattle to only use certain cores. To do this, specify either a comma separated list of cores (the first is
    numbered 0) such as `0,1,3,5` or a range like `0-4`. Note that the formatting is very important here, you can not
    mix the two styles or add any spaces or similar.

    This option accepts either a single such string, or a list of them. If a list is provided each battle that is run
    in parallel will use one of the provided set of cores. For example, if this option is `["0,1", "2-3", "4,5"]` and
    there are two battles executed at the same time, the first would use the first two physical cpus and the second the
    next two.

///danger
`advanced_build_params` / `advanced_run_params`

:   This option lets you modify the exact parameters used to build images and run containers. The possible keys and
    values are essentially the same as the ones the Docker cli accepts. You generally should not need to use this, and
    we highly recommend trying to use the other Algobattle options instead of directly using these. Misconfiguring these
    options may lead to giving other people, including but not limited to students whose programs are being run, access
    to everything on your computer! Only use these options if you are familiar with Docker and its intricacies.
///

`generator` / `solver`

:   Both of these fields accept the same type of dictionary. It can contain `timeout`, `space`, and `cpus` keys that
    limit the corresponding resource access to the generator and solver programs. Timeouts are given in seconds, memory
    space limits in MB, and cpus are natural numbers.

### Battle

Each battle type has different config options it can specify. Here we list the ones used by the included types. Their
full behavior is documented [here](battle_types.md)

#### Iterated

`rounds`

:   Number of rounds that will be run and averaged. A _round_ is one sequence of fights until a size has been found
    where the solver succeeds at all smaller sizes and fails at all bigger ones.

`iteration_cap`

:   Maximum size that will be iterated to.

`exponent`

:   An integer that determines how quickly the size increases. For example, an exponent of 2 results in a size sequence
    of 1, 2, 6, 15, 31, etc. while an exponent of 3 leads to 1, 2, 9, 36, 100, 255, etc.

`approximation_ratio`

:   A float between 0 and 1 (inclusive) that is the minimum score a solver needs to achieve to "successfully" solve
    an instance.

#### Averaged

`instance_size`

:   The instance size every match will be fought at.

`iterations`

:   The number of fights that will be fought in each match.
