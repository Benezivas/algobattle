import logging

from algobattle.verifier import Verifier

logger = logging.getLogger('algobattle.problems.biclique.verifier')


class BicliqueVerifier(Verifier):
    def verify_semantics_of_solution(self, solution, instance_size: int, solution_type: bool):
        if not solution:
            logger.error('The solution is empty!')
            return False

        solution_set1 = [line[2] for line in solution if line[1] == 'set1']
        solution_set2 = [line[2] for line in solution if line[1] == 'set2']
        if (not solution_set1) or (not solution_set2):
            logger.error('At least one node set of the solution is empty!')
            return False

        if set(solution_set1).intersection(set(solution_set2)) or set(solution_set2).intersection(set(solution_set1)):
            logger.error('At least one node is in both solution sets!')
            return False
        return True

    def verify_solution_against_instance(self, instance, solution, instance_size, solution_type):
        solution_set1 = [line for line in solution if line[1] == 'set1']
        solution_set2 = [line for line in solution if line[1] == 'set2']

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

    def calculate_approximation_ratio(self, instance, instance_size, generator_solution, solver_solution):
        return float(len(generator_solution)) / float(len(solver_solution))
