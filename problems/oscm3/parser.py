import logging
import sys

from parser import Parser
logger = logging.getLogger('algobattle.parser')

class OSCM3Parser(Parser):
    def split_into_instance_and_solution(self, raw_input):
        raw_instance = []
        raw_solution = []

        for line in raw_input:
            if line[0] == 'n':
                raw_instance.append(line)
            elif line[0] == 's':
                raw_solution = [line]

        return raw_instance, raw_solution

    def parse_instance(self, raw_instance, instance_size):
        raw_instance = list(set(raw_instance)) #Remove duplicate lines
        removable_lines = []

        seen_nodes = set()
        for line in raw_instance:
            if len(line) < 3 or len(line) > 5:
                logger.warning('An edge descriptors is not well formatted!')
                removable_lines.append(line)
            elif (not line[1].isdigit()):
                logger.warning('A node descriptor does not consist only of nonnegative ints!')
                removable_lines.append(line)
            elif int(line[1]) >= instance_size:
                logger.warning('A node descriptor is out of bounds!')
                removable_lines.append(line)
            else:
                seen_nodes.add(int(line[1]))
                clean = True
                included_nodes = set()
                for entry in line[2:]:
                    if not entry.isdigit():
                        logger.warning('A node descriptor does not consist only of nonnegative ints!')
                        clean = False
                    elif int(entry) >= instance_size:
                        logger.warning('A node descriptor is not in allowed range size!')
                        clean = False
                    elif entry in included_nodes:
                        logger.warning('A node is given twice!')
                        clean = False
                    else:
                        included_nodes.add(entry)
                if not clean:
                    removable_lines.append(line)

        for line in removable_lines:
            raw_instance.remove(line)

        """ Fill up the removed or missing node slots with trivial nodes to make 
        sure the solver always receives an instance of full length.
        This ensures that a solver can always produce a solver permutation of full
        length, even if some nodes (especially those indexed highest) are missing
        """
        missing_nodes = set([i for i in range(instance_size)]).difference(seen_nodes)
        filler_lines = []
        for node in missing_nodes:
            filler_lines.append(('n', str(node), str(node)))

        for line in filler_lines:
            raw_instance.append(line)


        self.parsed_instance = raw_instance
        return raw_instance

    def parse_solution(self, raw_solution, instance_size):
        removable_lines = []
        if raw_solution:
            raw_solution = raw_solution[0]
        else:
            return []
        if len(raw_solution) != instance_size + 1:
            logger.warning('The solution is of unexpected length!')
            return[]
        
        included_nodes = set()
        for entry in raw_solution[1:]:
            if not entry.isdigit():
                logger.warning('An entry of the solution is not a nonnegative integer!')
                return []
            elif int(entry) >= instance_size:
                logger.warning('An entry of the solution is out of bounds!')
                return []
            elif entry in included_nodes:
                logger.warning('An entry of the solution is given twice!')
                return []
            included_nodes.add(entry)

        for line in removable_lines:
            raw_solution.remove(line)

        return raw_solution

    def encode(self, input):
        return super().encode(input)

    def decode(self, raw_input):
        return super().decode(raw_input)