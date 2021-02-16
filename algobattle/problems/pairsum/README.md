# The Pairsum Problem
The Pairsum problem is a simple task which proved to be a good primer task for students to get used to the environment.

The task is the following:

**Given**: List `L = [z_1,...,z_n]`, `z_i in [0,2^{63})`  
**Question**: Are there pairwise different `i_1,i_2,i_3,i_4 in [0,...,n-1]` such that `L[i_1] + L[i_2] = L[i_3] + L[i_4]`?  

Given such a list, the task is thus to find four numbers which can be divided up into two pairs such that the sum of one pair is the same as the sum of the other pair.

For a given `n in N` the generator is tasked with creating a *YES*-instance in the form of a list `L` of nonnegative integers of length `n` as described above. 
Additionally, it has to give four indices in the order `i_1,i_2,i_3,i_4` such that they form a valid solution.

The Solver receives this list `L` and is supposed to output four indices in order `i_1,i_2,i_3,i_4` which are also a valid solution. It may always assume that the instance is a *YES*-instance of size at least 4.

The generator should create a hard to solve instance, while the solver should be able to solve any kind of instance that is given in a quick way.

# I/O
The generator receives the number `n` via `stdin`. It outputs the instance `L` by writing the numbers of the list space-seperated to stdout. It then writes a newline(`\n`) to stdout, followed by the solution.
The solution is also written out as space-seperated numbers.

A sample input and output for `n = 6` may look like this:  
Input:
```
6
```
Output:
```
12 30 36 0 6 24\n 1 4 0 5
```
The solver receives the instance via `stdin` as a space-seperated list of nonnegative integers. It then writes out its solution to `stdout` as a list of space-seperated numbers.
Applied the the example above, the input and output may look like this:  
Input: 
```
12 30 36 0 6 24
```
Output:  
```
3 2 0 5
```