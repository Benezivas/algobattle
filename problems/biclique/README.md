# The Bipartite Clique Problem
The *Bipartite Clique* problem is closely related to the *Maximum Clique*
problem. In it, we want to find the biggest complete bipartite subgraph in a
given Graph.

**Given**: Undirected graph `G = (V,E)` with `|V(G)| = n`  
**Problem**: Find the biggest subgraph `G' = (V_1 union V_2, E')` of `G` such that
`G' = K_{i,j}`

The generator is given an instance size and outputs an undirected graph of at most this size.
Along with the graph, it outputs a certificate solution for the biggest
bipartite clique of the graph that it knows.

The solver then receives this graph and has to find a bipartite clique of
maximum size within the time limit and output it. The solution is valid if its
size is at least as big as the certificate solution of the generator.

# I/O
We use a format similar to the DIMACS-format for this task:
* **Edges**: These lines are of the form `e i j`
    for an edge `(i,j) in E(G)`. As we are working on an undirected graph, 
    the symmetrical edge `(j,i)` does not need to be supplied.
* **Solution lines**: For each node `i` of `V_1(G')` add a line `s set1 i`,
    accordingly a line `s set2 j` for each node `j` of `V_2(G')`.

Isolated nodes can not be part of a bipartite clique, thus this format does not
allow supplying them in an instance.

Any malformed lines or lines not following the format above are discarded.
Each of the lines described above are to be written into their own line.
The generator reads the instance size from `stdin` and writes its instance 
and certificate to `stdout`. The order of the lines does not matter. For an
instance size of `n`, vertices may only be given indices in `{1,...,n}`.

The following output is a valid stream to stdout for the generator, given 
`n >= 10` (line breaks inserted for better readability):
```
    The described graph contains a K_{2,3} between {7,9} and {6,8,10}\n
    s set1 7\n
    s set1 9\n
    s set2 6\n
    s set2 8\n
    s set2 10\n
    e 1 2\n
    e 2 3\n
    e 2 8\n
    e 8 5\n
    e 8 10\n
    e 8 7\n
    e 6 5\n
    e 6 7\n
    e 6 9\n
    e 10 9\n
    e 10 7
```
The solver receives all edge lines, seperated by line breaks, just like above,
via `stdin`. It is then supposed to output edge sets `E'` and `E''` as described
above to `stdout`. The solution may deviate from that of the generator.

For the instance above, a valid output of the solver may look like this:
```
    s set1 8\n
    s set1 6\n
    s set1 10\n
    s set2 9\n
    s set2 7
```