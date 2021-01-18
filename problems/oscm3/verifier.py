import logging

from verifier import Verifier

logger = logging.getLogger('algobattle.verifier')

class OSCM3Verifier(Verifier):
    class Graph:
        def __init__(self, size):
            self.size = size
            self.upper_nodes = [None for i in range(size)]
            self.lower_nodes = [[] for i in range(size)]
            self.edges = [[] for i in range(size)]

        def insert_node(self, name, slot, neighbors):
            neighbors = sorted(neighbors)
            self.upper_nodes[slot] = str(name)
            i = 1
            for neighbor in neighbors:
                self.lower_nodes[neighbor].append(str(name) + "_" + str(i))
                i += 1
                self.edges[slot].append(neighbor)


        def calculate_number_crossings(self):
            crossings = 0
            for i in range(self.size):
                if self.upper_nodes[i]:
                    for j in range(i + 1, self.size):
                        if self.upper_nodes[j]:
                            for lower_node_i in self.edges[i]:
                                for lower_node_j in self.edges[j]:
                                    if lower_node_i > lower_node_j:
                                        crossings += 1
            return crossings

    
    def verify_solution_against_instance(self, instance, solution, instance_size, solution_type):
        if not instance:
            logger.error('The instance is empty!')
            return True
        if not solution:
            logger.error('The solution is empty!')
            return False

        # For this problem, no further verification is needed: If the Syntax is
        # correct, a solution string is automatically a valid solution

        return True

    def verify_solution_quality(self, instance, instance_size, generator_solution, solver_solution):
        edges = {}
        for node in instance:
            edges[node[1]] = []
            for entry in node[2:]:
                edges[node[1]].append(int(entry))

        g = self.Graph(instance_size)
        for i in range(1, len(generator_solution)):
            g.insert_node(generator_solution[i], i-1, edges[generator_solution[i]])

        s = self.Graph(instance_size)
        for i in range(1, len(solver_solution)):
            s.insert_node(solver_solution[i], i-1, edges[solver_solution[i]])


        return s.calculate_number_crossings() <= g.calculate_number_crossings()