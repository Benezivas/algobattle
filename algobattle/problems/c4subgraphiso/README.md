# The Square Subgraph Isomorphism Problem
In this problem of graph isomorphism we want to identify as many disjoint
induced Circles of length four (`C_4`) in a given graph as possible.

**Given**: Undirected graph `G = (V,E)` with `|V(G)| = n`  
**Problem**: Find the maximum number of pairwise disjoint, induced `C_4` in `G`

The generator is given an instance size and outputs an undirected graph of at
most this size. Along with the graph, it outputs a certificate solution
containing the set of circles as described above. A certificate solution is only
valid if there is at least one `C_4` given.

The solver then receives this graph and has to find a set of `C_4` within the
time limit and output it. The solution is valid if its size is at least as big
as the certificate solution of the generator.

# I/O
We use a format similar to the DIMACS-format for this task:
* **Edges**: These lines are of the form `e i j`
    for an edge `(i,j) in E(G)`. As we are working on an undirected graph, 
    the symmetrical edge `(j,i)` does not need to be supplied.
* **Solution lines**: For each of the `C_4` of the solution with nodes
  `{i,j,k,l}` add a line `s i j k l`. It is important that these nodes
  have to be listed *in order*, i.e. that there is an edge between 
  `i j, j k,..., l i`, otherwise the verifier does not accept them as valid squares.

Isolated nodes are not allowed for this format.

Any malformed lines or lines not following the format above are discarded.
Each of the lines described above are to be written into their own line.
The generator reads the instance size from `stdin` and writes its instance 
and certificate to `stdout`. The order of the lines does not matter. For an
instance size of `n`, vertices may only be given indices in `{1,...,n}`.

The following output is a valid stream to stdout for the generator, given 
`n >= 10` (line breaks inserted for better readability):
```
    The graph below contains no more than 2 induced C_4\n
    s 1 2 9 10\n
    s 5 6 7 8\n
    e 1 2\n
    e 2 3\n
    e 3 4\n
    e 3 5\n
    e 5 6\n
    e 6 7\n
    e 7 8\n
    e 8 9\n
    e 9 10\n
    e 10 1\n
    e 2 9\n
    e 5 9\n
    e 5 8
```

The solver receives all edge lines, seperated by line breaks, just like above,
via `stdin`. It is then supposed to output the squares that it found to
`stdout`. The solution may deviate from that of the generator.

For the instance above, a valid output of the solver may look like this:
```
    s 5 6 7 8\n
    s 9 2 1 10
```