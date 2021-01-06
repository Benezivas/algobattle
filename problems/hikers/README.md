# The Hikers Problem
The *Hikers* problem is a spin on the paper 
[Group Activity Selection Problem With Approval Preferences](https://doi.org/10.1007/s00182-017-0596-4)
which can be described as follows:

There are `n` hikers who would like to go on a hike in groups. Each hiker has a
preference interval of the size of the group she or he wants to hike in, which
includes the hiker themself. Find a distribution of as many hikers into groups
as possible, such that their preferences are met. 
An optimal solution for an instance may be unable to assign every hiker to a 
group.

**Given**: Set `H` of `n` hikers, and for each hiker a minimal and maximal 
preferred group size.  
**Problem**: Find a subset of hikers `S subseteq H` of maximum size and an
assignment of `S` into groups, such that each hiker of `S` is in a group of 
their preferred size.

The generator is given an `n` and should created up to `n` hikers with nonempty
preference intervals. Additionally, it outputs a certificate solution, assigning
as many hikers to groups as it can.

The solver then receives the hikers with their preference intervals and computes
an assignment on its own, trying to legally assign as many hikers to groups as 
it can. Its solution is valid if it is able to assign at least as many hikers
to groups as the generator.

# I/O
We use the following syntax for this problem:
* **Hikers**: For each hiker `i` with a preference interval of `[s,t]`, add a 
    line `h i s t`.
* **Assignments**: For each hiker `i` that you want to assign to group number 
    `j`, add a line `s i j`.

Any malformed lines or lines not following the format above are discarded.
Each of the lines described above are to be written into their own line.
The generator reads the instance size from `stdin` and writes its instance 
and certificate to `stdout`. The order of the lines does not matter. For an
instance size of `n`, hikers may only be given indices in `{1,...,n}`.

The following output is a valid stream to stdout for the generator, given 
`n >= 5` (line breaks inserted for better readability):
```
    c 4 hikers of this instance can be split into two groups.\n
    c Hiker 2 has unsatisfiable preferences.\n
    s 1 1\n
    s 4 1\n
    s 5 1\n
    s 3 2\n
    h 1 1 3\n
    h 2 10 12\n
    h 3 1 1\n
    h 4 2 5\n
    h 5 3 3
```

The solver receives all hiker lines, seperated by line breaks, just like above, 
via `stdin`. It is then supposed to output assignments of hikers to groups like
above to `stdout`. The solution may deviate from that of the generator.

For the instance above, a valid output of the solver may look like this:
```
    s 3 1\n
    s 1 2\n
    s 4 2\n
    s 5 2
```