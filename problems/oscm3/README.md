# The One-Sided Crossing Minimization-3 Problem
In the area of *graph drawing*, one is interested in the two-dimensional
visualization of graphs. One of the problems from this area is the 
*One-Sided Crossing Minimization* problem, which is concerned with
drawing graphs in layers while minimizing the number of edge crossings
between each layer.

**Given**: Bipartite Graph `G = (V_1 \dot\cup V_2, E)` with `|V_1| = |V_2| = n`, 
with `V_1` and `V_2` each ordered on a virtual line, parallel to one another.
Each node of `V_1` has degree at most 3.  
**Problem**: Find a permutation of `V_1`, that minimizes the number of edge
crossings.

The generator is given an `n` and for each node of `V_1` outputs its adjacent
nodes of `V_2`. Additionally, it outputs a permutation as a certificate
solution, which tries to minimizes the number of edge crossings in the graph.

The solver then receives the nodes of `V_1` and their adjacent nodes and is
tasked with finding a permutation minimizing the number of edge crossings as
well. Its solution is valid if the number of crossings of its permutation is at
most as high as those of the generator.

# I/O
We use the following syntax for this problem:
* **Nodes and Edges of V_1**: A node `i in V_1` can be connected with zero to
    three other nodes `j,k,l in V_2`. Add a line `n i j k l`, where `j,k` and `l`
    are optional.
* **Permutation**: The permutation of the `n` nodes is given by a line of the
    form `s i j k ... l`. Node `i` will then be assisgned to position 1, node `j`
    to position 2 and so on.

Any malformed lines or lines not following the format above are discarded.
Each of the lines described above are to be written into their own line.
The generator reads the instance size from `stdin` and writes its instance 
and certificate to `stdout`. The order of the lines does not matter. For an
instance size of `n`, nodes may only be given indices in `{0,...,n-1}`.

Any node that is not given in the instance after removing the malformed lines of
the input is assumed to have degree 0 and will be added by the parser to the
instance.

The following output is a valid stream to stdout for the generator, given 
`n >= 3` (line breaks inserted for better readability):
```
    n 0 1 2\n
    n 1 0 1 2\n
    n 2 0 1\n
    s 0 1 2
```
The solver receives all node lines, seperated by line breaks, just like above, 
via `stdin`. It is then supposed to output its permutation as
above to `stdout`. The solution may deviate from that of the generator.

For the instance above, a valid output of the solver may look like this:
```
    s 2 1 0
```
The solver thus finds a better solution than the generator in this case.