import logging

from verifier import Verifier

logger = logging.getLogger('algobattle.verifier')

class DsapproxVerifier(Verifier):
    def verify_solution_against_instance(self, instance, solution, instance_size):
        if not instance:
            logger.error('The instance is empty!')
            return True
        if not solution:
            logger.error('The solution is empty!')
            return False

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
            dominated_nodes.update(domination[node[2]])

        if all_nodes != dominated_nodes:
            logger.error('The solution set does not dominate all nodes!')
            return False

        return True

    def verify_solution_quality(self, generator_solution, solver_solution):
        return len(solver_solution) <= 2 * len(generator_solution)