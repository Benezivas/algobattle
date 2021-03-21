import logging

from algobattle.parser import Parser

logger = logging.getLogger('algobattle.parser')


class SchedulingParser(Parser):
    def split_into_instance_and_solution(self, raw_input):
        raw_instance = []
        raw_solution = []

        for line in raw_input:
            if line[0] == 'j':
                raw_instance.append(line)
            elif line[0] == 'a':
                raw_solution.append(line)

        return raw_instance, raw_solution

    def parse_instance(self, raw_instance, instance_size):
        removable_lines = []

        given_jobs = set()
        for line in raw_instance:
            if len(line) != 3:
                logger.warning('A job descriptors is not well formatted!')
                removable_lines.append(line)
            elif (not line[1].isdigit()) or (not line[2].isdigit()):
                logger.warning('A job descriptor does not consist only of nonnegative ints!')
                removable_lines.append(line)
            elif int(line[1]) > instance_size:
                logger.warning('A job descriptor is not in allowed range size!')
                removable_lines.append(line)
            elif int(line[1]) == 0:
                logger.warning('A job descriptor is zero, but should be at least one!')
                removable_lines.append(line)
            elif int(line[1]) in given_jobs:
                logger.warning('A job is given multiple times, removing the duplicate!')
                removable_lines.append(line)
            else:
                given_jobs.add(int(line[1]))

        for line in removable_lines:
            raw_instance.remove(line)

        return raw_instance

    def parse_solution(self, raw_solution, instance_size):
        removable_lines = []

        scheduled_jobs = set()
        for line in raw_solution:
            if len(line) != 3:
                logger.warning('A solution line is of unexpected length!')
                removable_lines.append(line)
            elif not line[1].isdigit() or not line[2].isdigit():
                logger.warning('A solution line does not consist only of positive ints!')
                removable_lines.append(line)
            elif int(line[1]) > instance_size or int(line[2]) > 5:
                logger.warning('A solution line is not in allowed range size!')
                removable_lines.append(line)
            elif int(line[1]) == 0 or int(line[2]) == 0:
                logger.warning('A solution descriptor is zero, but should be at least one!')
                removable_lines.append(line)
            elif int(line[1]) in scheduled_jobs:
                logger.warning('A job is scheduled multiple times, removing the duplicate!')
                removable_lines.append(line)
            else:
                scheduled_jobs.add(int(line[1]))

        for line in removable_lines:
            raw_solution.remove(line)

        return raw_solution

    def encode(self, input):
        return super().encode(input)

    def decode(self, raw_input):
        return super().decode(raw_input)
