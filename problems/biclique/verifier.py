import logging

from verifier import Verifier

logger = logging.getLogger('algobattle.verifier')

class BicliqueVerifier(Verifier):
    def verify_solution_against_instance(self, instance, solution, instance_size):
        if not instance:
            logger.error('The instance is empty!')
            return True
        if not solution:
            logger.error('The solution is empty!')
            return False

        solution_set1 = [line for line in solution if line[1] == 'set1']
        solution_set2 = [line for line in solution if line[1] == 'set2']
        if (not solution_set1) or (not solution_set2):
            logger.error('At least one node set of the solution is empty!')
            return False

        all_edges = set()
        for edge in instance:
            all_edges.add(edge)
            all_edges.add(('e', edge[2], edge[1]))

        sol_edges = set()
        for sol1_node in solution_set1:
            for sol2_node in solution_set2:
                sol_edges.add(('e', sol1_node[2], sol2_node[2]))
                sol_edges.add(('e', sol2_node[2], sol1_node[2]))

        if not sol_edges.issubset(all_edges):
            logger.error('The given solution is not a complete bipartite subgraph in the given instance!')
            return False

        return True

    def verify_solution_quality(self, generator_solution, solver_solution):
        return super().verify_solution_quality(generator_solution, solver_solution)