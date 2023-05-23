
# Problem

This module the `Problem`, `Solution`, and other related classes and thus the interface you can use to provide your own
problems.


::: algobattle.problem.Problem
    options:
        members: [
            name,
            min_size,
            with_solution,
            export,
            validate_instance,
            calculate_score,
        ]

::: algobattle.problem.Problem.Solution

::: algobattle.problem.Scored

::: algobattle.problem.ProblemModel
    options:
        filters: ["!Config"]

::: algobattle.problem.SolutionModel
    options:
        filters: ["!Config"]

::: algobattle.problem.UndirectedGraph

::: algobattle.problem.DirectedGraph

::: algobattle.problem.VertexWeights

::: algobattle.problem.EdgeWeights
