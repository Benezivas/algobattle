# The Dominating Set Approximation Problem
The *Dominating Set* problem is a classical NP-complete problem. In it, you are
given a graph and are supposed to find a minimum number of nodes such that
the selected nodes and all their direct neighbors cover the complete vertice set
of the graph.

**Given**: Undirected graph `G = (V,E)` with `|V(G)| = n`  
**Problem**: If `S` is a dominating set for `G`, find a dominating set 
`S' subseteq V(G)`, with `|S| >= |S'|`

The generator is given an integer `n` and tasked with creating a graph and a 
certificate solution which is a dominating set in this graph.

The solver is given this graph and has to find a dominating set in it. The 
solution is valid if its size is at least as big as the
certificate solution.
# I/O
We use a format similar to the DIMACS-format for this task:
* **Edges**: These lines are of the form `e i j`
    for an edge `(i,j) in E(G)`. As we are working on an undirected graph, 
    the symmetrical edge `(j,i)` does not need to be supplied.
* **Solution lines**: For each vertex `i` that is part of the dominating set, add
    a line `s i`.

Since every isolated node needs to be added to every dominating set, they are
unable to be part of an instance with our format.

Any malformed lines or lines not following the format above are discarded.
Each of the lines described above are to be written into their own line.
The generator reads the instance size from `stdin` and writes its instance 
and certificate to `stdout`. The order of the lines does not matter. For an
instance size of `n`, vertices may only be given indices in `{1,...,n}`.


The following output is a valid stream to stdout for the generator, given 
`n >= 6` (line breaks inserted for better readability):
```
    c The graph below has a Dominating Set of size 2\n
    c consisting e.g. of the nodes {1,4}\n
    s 1\n
    s 4\n
    e 1 2\n
    e 2 3\n
    e 3 4\n
    e 4 5\n
    e 5 6\n
    e 6 1\n
    e 2 6\n
    e 3 5
```
The solver receives all edge lines, seperated by line breaks, just like above, 
via `stdin`. It is then supposed to output the set `S'` as described
above to `stdout`. The solution may deviate from that of the generator.

For the instance above, a valid output of the solver may look like this:
```
    s 1\n
    s 4
```