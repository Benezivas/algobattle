import logging

from algobattle.parser import Parser

logger = logging.getLogger('algobattle.problems.oscm3.parser')


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

    def is_instance_line_clean(self, line, instance_size):
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
        return clean

    def parse_instance(self, raw_instance, instance_size):
        raw_instance = list(set(raw_instance))
        removable_lines = []

        for line in raw_instance:
            if len(line) < 2 or len(line) > 5:
                logger.warning('An edge descriptors is not well formatted!')
                removable_lines.append(line)
            elif (not line[1].isdigit()):
                logger.warning('A node descriptor does not consist only of nonnegative ints!')
                removable_lines.append(line)
            elif int(line[1]) >= instance_size:
                logger.warning('A node descriptor is out of bounds!')
                removable_lines.append(line)
            elif not self.is_instance_line_clean(line, instance_size):
                removable_lines.append(line)

        for line in removable_lines:
            raw_instance.remove(line)

        """ Fill up the removed or missing node slots with nodes of degree 0 to make
        sure the solver always receives an instance of full length.
        """
        present_nodes = set([int(line[1]) for line in raw_instance])
        missing_nodes = set([i for i in range(instance_size)]).difference(present_nodes)
        for node in missing_nodes:
            raw_instance.append(('n', str(node)))

        return raw_instance

    def parse_solution(self, raw_solution, instance_size):
        removable_lines = []
        if raw_solution:
            raw_solution = raw_solution[0]
        else:
            return []
        if len(raw_solution) != instance_size + 1:
            logger.warning('The solution is of unexpected length!')
            return []

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
