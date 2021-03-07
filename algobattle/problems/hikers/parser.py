import logging

from algobattle.parser import Parser
logger = logging.getLogger('algobattle.parser')

class HikersParser(Parser):
    def split_into_instance_and_solution(self, raw_input):
        raw_instance = []
        raw_solution = []
        for line in raw_input:
            if line[0] == 'h':
                raw_instance.append(line)
            elif line[0] == 's':
                raw_solution.append(line)

        return raw_instance, raw_solution

    def parse_instance(self, raw_instance, instance_size):
        duplication_checklist = []
        removable_lines = []
        for line in raw_instance:
            if len(line) != 4:
                logger.warning('A hiker line is of unexpected length!')
                removable_lines.append(line)
            elif not line[1].isdigit() or not line[2].isdigit() or not line[3].isdigit():
                logger.warning('A hiker line has a negative or non-int entry!')
                removable_lines.append(line)
            elif int(line[1]) > instance_size or int(line[1]) == 0:
                logger.warning('A hiker identifier is not in {1,...,n}!')
                removable_lines.append(line)
            elif int(line[3]) < int(line[2]):
                logger.warning('A hiker preference interval is empty!')
                removable_lines.append(line)
            elif int(line[1]) in duplication_checklist:
                logger.warning('A hiker index was used multiple times!')
                removable_lines.append(line)
            else:
                duplication_checklist.append(int(line[1]))

        for line in removable_lines:
            raw_instance.remove(line)

        return raw_instance

    def parse_solution(self, raw_solution, instance_size):
        raw_solution = list(set(raw_solution)) #Remove duplicate lines
        removable_lines = []

        for line in raw_solution:
            if len(line) != 3:
                logger.warning('A solution line is of unexpected length!')
                removable_lines.append(line)
            elif not line[1].isdigit() or not line[2].isdigit():
                logger.warning('A solution line has a negative or non-int entry!')
                removable_lines.append(line)
            elif int(line[1]) > instance_size or int(line[1]) == 0:
                logger.warning('A solution line contains a hiker identifier outside of {1,...,n}!')
                removable_lines.append(line)

        for line in removable_lines:
            raw_solution.remove(line)
        return raw_solution

    def encode(self, input):
        return super().encode(input)

    def decode(self, raw_input):
        return super().decode(raw_input)