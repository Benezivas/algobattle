
# Running a match

With a ready to use install of everything we need, we can jump right into actually running some matches and see how that
works.

/// tip
You can follow along by downloading the [Algobattle Problem](https://github.com/Benezivas/algobattle-problems)
repository. You can also choose different problems than the ones we'll be discussing here, they all are interchangeable.
///

## Selecting a problem

The first step is that we need to tell Algobattle what problem to use. Recall that by _a problem_ we really mean a
certain type of python class. There's two ways of specifying which one Algobattle should use:

1. The path to a file containing it. The path can either be to the file directly, or to the parent folder
as long as the file is called `problem.py`. The file must uniquely identify a problem class, most commonly this is
achieved by it only containing a single one, but more complex use cases are possible too.

2. The name of a problem. For this to work the problem needs to be part of an installed problem package.

/// tab | Path
<div class="termy">

```console
$ algobattle .\algobattle_problems\pairsum
```

</div>

///

/// tab | Name
<div class="termy">

```console
$ algobattle Pairsum
```

</div>
///

/// info
Depending on your exact setup this command may throw an error right now, we'll see why and what to do to fix it in a
bit.
///

## Building program images

Algobattle needs to not only know what problem to use, but also what teams are participating in the match and where it
can find their programs. For now, we'll use the default of a single team that fights against itself. This setup is often
used during development when teams want to test their own code.

When the problem is specified via a path, Algobattle defaults to searching for the programs at the `/generator` and
`/solver` subfolders of the directory the problem is in. If you provide the name of a program, it will look for those
folders in the current instead.

/// note
The problems in the Algobattle Problems repository all have dummy programs at the required paths. If you are using
different problems you will need to write your own programs before you can run a match.

Since these dummy programs are located in the package folders, you will need to specify the program with a path to it to
use them.
///

These folders should contain Dockerfiles that build into the team's programs. The first thing that happens during a
match is that Algobattle builds the containers. During this the terminal will tell you whose programs are being build,
how long this is taking, and what the timeout is set to.

## Match execution

With the programs built, the actual match can start. While this is happening a lot of different things will be
displayed, so let's go through each of them on its own:

### Battle overview

```console hl_lines="2-11"
{!> match_cli.txt!}
```

Right at the top you will see an overview over all battles in this match. Normally this includes every combination of
one team generating and another team solving, but there are some exceptions. The first is that if there is a single
participating team (as is the default), then it will instead be paired up against itself. The other is that teams are
excluded if their Docker containers don't successfully build.

The First two rows contain the names of the teams participating in that match, and the third is the score of that
battle. Note that this is not the same as the points each team gets awarded at the end. Rather, it just represents a
battle specific measure of how well the solving team performed in it. The final points calculation is explained
[here](#points-calculation).

### Battle data

```console hl_lines="14-15"
{!> match_cli.txt!}
```

Each battle also has its own specific data it will display. In our example, we are using the Iterated battle type which
runs fights at increasing instance sizes until the solver can no longer solve the generated instances within the time
limit. This is repeated a few times to be fair to teams that implemented programs with random elements. The `reached`
field indicates what the maximum size reached in each iteration was, here the first repetition got to 12 and the second
has currently not executed any fights. The `cap` field is a bit more intricate and explained in detail in the
[Battle types](battle_types.md) section.

### Current fight

```console hl_lines="17-19"
{!> match_cli.txt!}
```

The fight that is currently being executed displays what size it is being fought at and timing data about each program
execution.

### Most recent fights

```console hl_lines="21-29"
{!> match_cli.txt!}
```

Lastly, the three most recent fights have their score displayed.

## Points calculation

Once all battles have finished running each team will get some number of points based on how well it performed. By
default, each team can get up to 100 points in a match. In the case of a three team matchup like we have here this means
that there are 50 points divided out between each pairing here. How they are divided is determined is based on how well
a team was able to solve another team's instances compared to how well that other team was able to solve the ones it
generated. For example, if the battle scores look like this:

| Generator |  Solver | Result |
|-----------|---------|--------|
|    dogs   |   cats  |     24 |
|    dogs   | otters  |     50 |
|    cats   |   dogs  |     12 |
|    cats   | otters  |    700 |
|  otters   |   dogs  |     50 |
|  otters   |   cats  |      0 |

Then there are three pairings that are considered:

1. Dogs vs Cats. Here the battle scores are 12 to 24, team cats was able to solve the presented instances twice as well
as team dogs. So cats receives 33.3 points and dogs 16.6.

2. Cats vs Otters. This matchup is much more decisive at 700 to 0, obviously the otters will get all 50 points and cats
none. Note that the fact that the total score here was much higher than the ones in the previous matchup is irrelevant,
battle scores are only compared between two particular teams, not over the whole match.

3. Otters vs Dogs. This matchup again is very simple as both teams performed equally well, so both will receive 25
points.

In total, dogs win this match with 41.6 points, cats are second with 33.3, and the otters are third with 25.
