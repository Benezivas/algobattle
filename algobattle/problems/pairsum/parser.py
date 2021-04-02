import logging

from algobattle.parser import Parser

logger = logging.getLogger('algobattle.problems.pairsum.parser')


class PairsumParser(Parser):
    def split_into_instance_and_solution(self, raw_input):

        raw_instance = ""
        raw_solution = [""]

        if len(raw_input) == 2:
            raw_instance = raw_input[0]
            raw_solution = [raw_input[1]]
        return raw_instance, raw_solution

    def parse_instance(self, raw_instance, instance_size):
        removable_entries = []

        if raw_instance:
            raw_instance = raw_instance.split()

        for entry in raw_instance:
            if not entry.isdigit():
                logger.warning('An entry of the instance is not a nonnegative int!')
                removable_entries.append(entry)
            elif int(entry) >= 2**63:
                logger.warning('An entry exceeds the required size!')
                removable_entries.append(entry)

        for entry in removable_entries:
            raw_instance.remove(entry)

        for i in range(len(raw_instance)):
            raw_instance[i] = int(raw_instance[i])

        return raw_instance[:min(len(raw_instance), instance_size)]

    def parse_solution(self, raw_solution, instance_size):
        removable_entries = []

        if raw_solution:
            raw_solution = raw_solution[0].split()

        for entry in raw_solution:
            if not entry.isdigit():
                logger.warning('An entry of the solution is not a positive int!')
                removable_entries.append(entry)
            elif int(entry) > instance_size:
                logger.warning('An entry of the solution refers to an index out of bounds!')
                removable_entries.append(entry)

        for entry in removable_entries:
            raw_solution.remove(entry)

        for i in range(len(raw_solution)):
            raw_solution[i] = int(raw_solution[i])

        return raw_solution

    def encode(self, input):
        return " ".join(str(element) for element in input).encode()

    def decode(self, raw_input):
        return raw_input.decode().splitlines()
