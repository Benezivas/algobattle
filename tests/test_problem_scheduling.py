""" Tests for the biclique problem.
"""
import unittest
import logging

from algobattle.problems.scheduling import parser, verifier

logging.disable(logging.CRITICAL)

class Parsertests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = parser.SchedulingParser()

    def test_split_into_instance_and_solution(self):
        raw_input = [('j', '1', '30'), ('j', '2', '120'), ('j', '3', '24'), ('j', '4', '40'), ('j', '5', '60'), ('a', '1', '4'), ('a', '2', '1'), ('a', '3', '5'), ('a', '4', '3'), ('a', '5', '2'), ('foo', 'bar')]
        self.assertEqual(self.parser.split_into_instance_and_solution(raw_input), 
        ([('j', '1', '30'), ('j', '2', '120'), ('j', '3', '24'), ('j', '4', '40'), ('j', '5', '60')], [('a', '1', '4'), ('a', '2', '1'), ('a', '3', '5'), ('a', '4', '3'), ('a', '5', '2')]))

        #empty inputs should be handled
        self.assertEqual(self.parser.split_into_instance_and_solution([]), ([],[]))

    def test_parse_instance(self):
        #lines with too many entries should be removed
        raw_instance = [('j', '1', '30', '20'), ('j', '2', '120')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=3), [('j', '2', '120')])

        #lines with too few entries should be removed
        raw_instance = [('j', '1'), ('j', '2', '120')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=2), [('j', '2', '120')])

        #Lines that use labels higher than instance_size should be removed
        raw_instance = [('j', '1', '30'), ('j', '2', '120')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=1), [('j', '1', '30')])

        #Duplicates should be removed
        raw_instance = [('j', '1', '30'), ('j', '1', '30')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=3), [('j', '1', '30')])

        #Lines with letters should be removed
        raw_instance = [('j', 'a', '30'), ('j', '2', 'a')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=3), [])

        #0 label lines should be removed
        raw_instance = [('j', '0', '30'), ('j', '2', '120')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=3), [('j', '2', '120')])

        #duplicate jobs should be removed
        raw_instance = [('j', '1', '30'), ('j', '1', '120')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=3), [('j', '1', '30')])

        #empty inputs should be handled
        self.assertEqual(self.parser.parse_instance([], instance_size=3), [])

    def test_parse_solution(self):
        #lines with too many entries should be removed
        raw_solution = [('a', '1', '4', '2'), ('a', '2', '1')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [('a', '2', '1')])

        #lines with too few entries should be removed
        raw_solution = [('a', '1'), ('a', '2', '1')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [('a', '2', '1')])

        #Lines that use job labels higher than instance_size should be removed
        raw_solution = [('a', '1', '4'), ('a', '2', '1')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=1), [('a', '1', '4')])

        #Lines that use machine labels higher than 5 should be removed
        raw_solution = [('a', '1', '4'), ('a', '2', '6')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=2), [('a', '1', '4')])

        #Lines with letters should be removed
        raw_solution = [('a', '1', 'a'), ('a', '2', '1')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [('a', '2', '1')])

        #0 label lines should be removed
        raw_solution = [('a', '0', '4'), ('a', '2', '1')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [('a', '2', '1')])

        #jobs should not be scheduled multiple times
        raw_solution = [('a', '1', '4'), ('a', '1', '1')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [('a', '1', '4')])

        #empty inputs should be handled
        self.assertEqual(self.parser.parse_solution([], instance_size=2), [])

    def test_encode(self):
        self.assertEqual(self.parser.encode([('j', '1', '30'), ('j', '2', '120'), ('a', '4', '3'), ('a', '5', '2')]), 
"""j 1 30
j 2 120
a 4 3
a 5 2""".encode())

    def test_decode(self):
        self.assertEqual(self.parser.decode(
"""j 1 30
j 2 120
a 4 3
a 5 2
""".encode()), [('j', '1', '30'), ('j', '2', '120'), ('a', '4', '3'), ('a', '5', '2')])


class Verifiertests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = verifier.SchedulingVerifier()

    def test_verify_semantics_of_instance(self):
        self.assertTrue(self.verifier.verify_semantics_of_instance([('j', '1', '30')], instance_size=10))
        self.assertFalse(self.verifier.verify_semantics_of_instance([], instance_size=10))
        self.assertFalse(self.verifier.verify_semantics_of_instance([('j', '1', '{}'.format(2**64)), ('j', '2', '120')], instance_size=10))

    def test_verify_semantics_of_solution(self):
        self.assertFalse(self.verifier.verify_semantics_of_solution([('j', '1', '30')], [], 10, solution_type=False))
        self.assertTrue(self.verifier.verify_semantics_of_solution([('j', '1', '30')], [('a', '1', '3')], 10, solution_type=False))

    def test_verify_solution_against_instance(self):
        #Valid solutions should be accepted
        instance = [('j', '1', '30'), ('j', '2', '120'), ('j', '3', '24'), ('j', '4', '40'), ('j', '5', '60')]
        solution = [('a', '1', '4'), ('a', '2', '1'), ('a', '3', '5'), ('a', '4', '3'), ('a', '5', '2')]
        self.assertTrue(self.verifier.verify_solution_against_instance(instance, solution, instance_size=10, solution_type=False))

        #Invalid solutions should not be accepted
        instance = [('j', '1', '30')]
        solution = [('a', '4', '3')]
        self.assertFalse(self.verifier.verify_solution_against_instance(instance, solution, instance_size=10, solution_type=False))

        instance = [('j', '1', '30'), ('j', '2', '120'), ('j', '3', '24'), ('j', '4', '40'), ('j', '5', '60')]
        solution = [('a', '1', '4'), ('a', '2', '1'), ('a', '3', '5'), ('a', '4', '3')]
        self.assertFalse(self.verifier.verify_solution_against_instance(instance, solution, instance_size=10, solution_type=False))

    def test_calculate_approximation_ratio(self):
        instance = [('j', '1', '30'), ('j', '2', '120'), ('j', '3', '24'), ('j', '4', '40'), ('j', '5', '60')]
        solution_sufficient = [('a', '1', '4'), ('a', '2', '1'), ('a', '3', '5'), ('a', '4', '3'), ('a', '5', '2')]
        solution_too_much = [('a', '1', '4'), ('a', '2', '2'), ('a', '3', '5'), ('a', '4', '3'), ('a', '5', '1')]
        self.assertEqual(self.verifier.calculate_approximation_ratio(instance, 10, solution_sufficient, solution_too_much), 2.0)
        self.assertEqual(self.verifier.calculate_approximation_ratio(instance, 10, solution_sufficient, solution_sufficient), 1.0)

    def test_calculate_makespan(self):
        instance = [('j', '1', '30'), ('j', '2', '120'), ('j', '3', '24'), ('j', '4', '40'), ('j', '5', '60')]
        solution_sufficient = [('a', '1', '4'), ('a', '2', '1'), ('a', '3', '5'), ('a', '4', '3'), ('a', '5', '2')]
        solution_too_much = [('a', '1', '4'), ('a', '2', '2'), ('a', '3', '5'), ('a', '4', '3'), ('a', '5', '1')]
        self.assertEqual(self.verifier.calculate_makespan(instance, solution_sufficient), 120) 
        self.assertEqual(self.verifier.calculate_makespan(instance, solution_too_much), 240) 

if __name__ == '__main__':
    unittest.main()
