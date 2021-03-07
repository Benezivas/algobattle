# The Path Packing Problem
The *Path Packing* problem is a classical packing problem. In it, we are
interested in identifying as many node-disjoint paths as subgraphs in a given
graph. For this problem, we are interested in very short paths for which the
problem is already NP-complete, i.e. packing paths with two edges (`P_3`).

**Given**: Undirected graph `G = (V,E)` with `|V(G)| = n`  
**Problem**: Find the maximum number of pairwise disjoint, `P_3` in `G`

The generator is given an instance size and outputs an undirected graph of at
most this size. Along with the graph, it outputs a certificate solution
containing the set of paths as described above. A certificate solution is only
valid if there is at least one `P_3` given.

The solver then receives this graph and has to find a set of `P_3` within the
time limit and output it. The solution is valid if its size is at least as big
as the certificate solution of the generator.

# I/O-Formate
We use the following format for this problem:
* **Edges**: These lines are of the form `e i j`
    for an edge `(i,j) in E(G)`. As we are working on an undirected graph, 
    the symmetrical edge `(j,i)` does not need to be supplied.
* **Solution lines**: For each of the `P_3` of the solution with nodes
  `{i,j,k}` add a line `s i j k`. It is important that these nodes
  have to be listed *in order*, i.e. that there is an edge between 
  `i j` and `j k`, otherwise the verifier does not accept them as valid paths.

Isolated nodes are not allowed for this format.

Any malformed lines or lines not following the format above are discarded.
Each of the lines described above are to be written into their own line.
The generator reads the instance size from `stdin` and writes its instance 
and certificate to `stdout`. The order of the lines does not matter. For an
instance size of `n`, vertices may only be given indices in `{1,...,n}`.

The following output is a valid stream to stdout for the generator, given 
`n >= 9` (line breaks inserted for better readability):
```
    We can pack exactly 3 paths with 3 vertices each into the following graph\n
    s 2 3 6\n
    s 2 4 7\n
    s 5 8 9\n
    e 1 2\n
    e 2 3\n
    e 1 4\n
    e 2 5\n
    e 2 6\n
    e 2 4\n
    e 4 7\n
    e 4 8\n
    e 7 8\n
    e 5 8\n
    e 6 8\n
    e 8 9
```

The solver receives all edge lines, seperated by line breaks, just like above,
via `stdin`. It is then supposed to output the paths that it found to
`stdout`. The solution may deviate from that of the generator.

For the instance above, a valid output of the solver may look like this:
```
    s 6 3 2\n
    s 2 4 7\n
    s 9 8 5
```