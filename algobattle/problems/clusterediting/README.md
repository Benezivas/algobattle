# The Cluster Editing Problem
The *Cluster Editing* problem is an NP-complete problem 
concerned with adding and removing edges in
a graph such that it becomes a set of cliques.

**Given**: Undirected graph `G = (V,E)` with `|V(G)| = n`  
**Problem**: Find edge sets `E'` and `E''` such that for each connected
subgraph `C subseteq G` it holds that `(V(C), E cup E' setminus E'') = K_i` for
some `i in {1,...,n}`.

For a given `n`, the generator is to create a graph with at most `n` vertices.
Additionally, as a certificate, sets of edges `E'` and `E''` as specified above
are to be supplied.

The solver is given a graph of size at most `n` and is supposed to find and
output edge sets `E'` and `E''` as described above. The solver wins the round
for a given `n` if its solution is at most as big as the certificate solution
of the generator.

# I/O
We use a format similar to the DIMACS-format for this task:
* **Edges**: These lines are of the form `e i j`
    for an edge `(i,j) in E(G)`. As we are working on an undirected graph, 
    the symmetrical edge `(j,i)` does not need to be supplied.
* **Solution lines**: For each edge `(i,j) in E'` a line of the form `s add i j` 
    is to be supplied. For each edge `(i,j) \in E''` a line of the form 
    `s del i j` is to be supplied.

Isolated nodes can not be part of an instance, as they already form a clique on
their own and can thus always be discarded.

Any malformed lines  or lines not following the format above are discarded.
Each of the lines described above are to be written into their own line.
The generator reads the instance size from `stdin` and writes its instance 
and certificate to `stdout`. The order of the lines does not matter. For an
instance size of `n`, vertices may only be given indices in `{1,...,n}`.

The following output is a valid stream to stdout for the generator, given 
`n >= 7` (line breaks inserted for better readability):
```
    c This is a comment line, just as the one below.\n
    Any line not following the given format is discarded.\n
    c The graph needs two deletions and one addition to become clustered.\n
    s add 1 3\n
    s del 4 5\n
    s del 2 7\n
    e 1 2\n
    e 2 3\n
    e 2 4\n
    e 3 4\n
    e 1 4\n
    e 4 5\n
    e 2 7\n
    e 5 7\n
    e 6 7\n
    e 5 6
```
The solver receives all edge lines, seperated by line breaks, just like above, 
via `stdin`. It is then supposed to output edge sets `E'` and `E''` as described
above to `stdout`. The solution may deviate from that of the generator.

For the instance above, a valid output of the solver may look like this:
```
    s add 1 3\n
    s del 4 5\n
    s del 2 7
```