import logging

from algobattle.parser import Parser

logger = logging.getLogger('algobattle.parser')


class BicliqueParser(Parser):
    def split_into_instance_and_solution(self, raw_input):
        raw_instance = []
        raw_solution = []

        for line in raw_input:
            if line[0] == 'e':
                raw_instance.append(line)
            elif line[0] == 's' and line[1] in ['set1', 'set2']:
                raw_solution.append(line)

        return raw_instance, raw_solution

    def parse_instance(self, raw_instance, instance_size):
        raw_instance = list(set(raw_instance))
        removable_lines = []

        for line in raw_instance:
            if len(line) != 3:
                logger.warning('An edge descriptors is not well formatted!')
                removable_lines.append(line)
            elif (not line[1].isdigit()) or (not line[2].isdigit()):
                logger.warning('An edge descriptor does not consist only of nonnegative ints!')
                removable_lines.append(line)
            elif int(line[1]) > instance_size or int(line[2]) > instance_size:
                logger.warning('A node descriptor is not in allowed range size!')
                removable_lines.append(line)
            elif int(line[1]) == 0 or int(line[2]) == 0:
                logger.warning('A node descriptor is zero, but should be at least one!')
                removable_lines.append(line)
            elif int(line[1]) == int(line[2]):
                logger.warning('An egde is describing a loop!')
                removable_lines.append(line)

        for line in removable_lines:
            raw_instance.remove(line)

        return raw_instance

    def parse_solution(self, raw_solution, instance_size):
        raw_solution = list(set(raw_solution))
        removable_lines = []
        for line in raw_solution:
            if len(line) != 3:
                logger.warning('A solution line is of unexpected length!')
                removable_lines.append(line)
            elif not line[2].isdigit():
                logger.warning('A solution descriptor is not a positive int!')
                removable_lines.append(line)
            elif int(line[2]) == 0 or int(line[2]) > instance_size:
                logger.warning('One solution descriptor is out of bounds!')
                removable_lines.append(line)

        for line in removable_lines:
            raw_solution.remove(line)
        return raw_solution

    def encode(self, input):
        return super().encode(input)

    def decode(self, raw_input):
        return super().decode(raw_input)
