# The Job Shop Scheduling Problem
There are many variants of the *Job Shop Scheduling* Problem. In this variant
our job is to schedule `n` jobs onto 5 machines of differnent execution speed.
Our goal is to minimize the *makespan*, i.e. the latest job completion time over
all machines.

**Given**: `n` jobs and 5 machines of different execution speeds  
**Problem**: Find a distribution of the jobs onto the machines that minimizes 
the *makespan*.

The index of a machine indicates its speed, specifically how much the machine
slows down the execution of a job. Machine 1 runs the jobs normally, while e.g.
machine three slows down execution time by a factor of three.

The generator is given an `n` and for each job outputs its execution time.
Additionally, it outputs an assignment as a certificate solution, which tries to
minimizes the *makespan*.

The solver then receives the jobs and is tasked with finding an assignment
minimizing the *makespan* as well. Its solution is valid if the *makespan* its
assignment produces is at most as high as that of the generator.

# I/O
We use the following format for this problem:
* **Jobs**: These lines have the form `j i l` for job `i` of length `l`.
* **Permutation**: These lines have the form `a i j` to assign job `i` to 
machine `j`.

Any malformed lines or lines not following the format above are discarded. Each
of the lines described above are to be written into their own line. The
generator reads the instance size from `stdin` and writes its instance and
certificate to `stdout`. The order of the lines does not matter. For an instance
size of `n`, jobs may only be given indices in `{1,...,n}` and machines indices
in `{1,...,5}`.

The following output is a valid stream to stdout for the generator, given 
`n >= 5` (line breaks inserted for better readability):
```
    The given 5 jobs are scheduled such that the makespan is 120\n
    a 1 4\n
    a 2 1\n
    a 3 5\n
    a 4 3\n
    a 5 2\n
    j 1 30\n
    j 2 120\n
    j 3 24\n
    j 4 40\n
    j 5 60
```
The solver receives all job lines, seperated by line breaks, just like above, 
via `stdin`. It is then supposed to output its assignment as
above to `stdout`. The solution may deviate from that of the generator.

For the instance above, a valid output of the solver may look like this:
```
    a 1 4\n
    a 2 1\n
    a 3 5\n
    a 4 3\n
    a 5 2
```