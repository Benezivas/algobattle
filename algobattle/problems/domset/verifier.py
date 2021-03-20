import logging

from algobattle.verifier import Verifier

logger = logging.getLogger('algobattle.verifier')

class DomsetVerifier(Verifier):
    def verify_solution_against_instance(self, instance, solution, instance_size, solution_type):
        all_nodes = set()
        domination = {}
        for edge in instance:
            domination[edge[1]] = domination.get(edge[1], set())
            domination[edge[2]] = domination.get(edge[2], set())
            domination[edge[1]].add(edge[1])
            domination[edge[1]].add(edge[2])
            domination[edge[2]].add(edge[1])
            domination[edge[2]].add(edge[2])
            all_nodes.add(edge[1])
            all_nodes.add(edge[2])

        dominated_nodes = set()
        for node in solution:
            dominated_nodes.update(domination[node[1]])

        if all_nodes != dominated_nodes:
            logger.error('The solution set does not dominate all nodes!')
            return False

        return True

    def calculate_approximation_ratio(self, instance, instance_size, generator_solution, solver_solution):
        return float(len(solver_solution)) / float(len(generator_solution))