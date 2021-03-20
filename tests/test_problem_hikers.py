""" Tests for the biclique problem.
"""
import unittest
import logging

from algobattle.problems.hikers import parser, verifier

logging.disable(logging.CRITICAL)

class Parsertests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = parser.HikersParser()

    def test_split_into_instance_and_solution(self):
        raw_input = [('h', '1', '1', '3'), ('h', '2', '10', '12'), ('h', '3', '1', '1'), ('h', '4', '2', '5'), ('h', '5', '3', '3'), ('s', '3', '1'), ('s', '1', '2'), ('s', '4', '2'), ('s', '5', '2'), ('foo', 'bar')]
        self.assertEqual(self.parser.split_into_instance_and_solution(raw_input), 
        ([('h', '1', '1', '3'), ('h', '2', '10', '12'), ('h', '3', '1', '1'), ('h', '4', '2', '5'), ('h', '5', '3', '3')], [('s', '3', '1'), ('s', '1', '2'), ('s', '4', '2'), ('s', '5', '2')]))

        #empty inputs should be handled
        self.assertEqual(self.parser.split_into_instance_and_solution([]), ([],[]))

    def test_parse_instance(self):
        #lines with too many entries should be removed
        raw_instance = [('h', '1', '1', '3', '4'), ('h', '2', '10', '12')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=20), [('h', '2', '10', '12')])

        #lines with too few entries should be removed
        raw_instance = [('h', '3', '4'), ('h', '2', '10', '12')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=20), [('h', '2', '10', '12')])

        #Lines that use labels higher than instance_size should be removed
        raw_instance = [('h', '1', '1', '3'), ('h', '3', '10', '12')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=2), [('h', '1', '1', '3')])

        #Duplicates should be removed
        raw_instance = [('h', '3', '10', '12'), ('h', '3', '10', '12')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=20), [('h', '3', '10', '12')])

        #Lines with letters should be removed
        raw_instance = [('h', '3', '10', '12'), ('h', 'a', '10', '12')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=20), [('h', '3', '10', '12')])

        #0 label lines should be removed
        raw_instance = [('h', '0', '1', '3'), ('h', '3', '10', '12')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=20), [('h', '3', '10', '12')])

        # Empty preference interval lines should be removed
        raw_instance = [('h', '3', '12', '10'), ('h', '1', '1', '3')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=20), [('h', '1', '1', '3')])

        #The same hiker should not be given multiple times
        raw_instance = [('h', '1', '10', '12'), ('h', '1', '1', '3')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=20), [('h', '1', '10', '12')])

        #empty inputs should be handled
        self.assertEqual(self.parser.parse_instance([], instance_size=3), [])

    def test_parse_solution(self):
        #lines with too many entries should be removed
        raw_solution = [('s', '3', '1', '5')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [])

        #lines with too few entries should be removed
        raw_solution = [('s', '3')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [])

        #Lines that use labels higher than instance_size should be removed
        raw_solution = [('s', '11', '1')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=9), [])

        #Lines with letters should be removed
        raw_solution = [('s', 'a', '1')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [])

        #0 label lines should be removed
        raw_solution = [('s', '0', '1')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=10), [])

        #empty inputs should be handled
        self.assertEqual(self.parser.parse_solution([], instance_size=2), [])

    def test_encode(self):
        self.assertEqual(self.parser.encode([('h', '1', '1', '3'), ('h', '2', '10', '12'), ('h', '3', '1', '1'), ('h', '4', '2', '5'), ('h', '5', '3', '3'), ('s', '3', '1'), ('s', '1', '2'), ('s', '4', '2'), ('s', '5', '2')]), 
"""h 1 1 3
h 2 10 12
h 3 1 1
h 4 2 5
h 5 3 3
s 3 1
s 1 2
s 4 2
s 5 2""".encode())

    def test_decode(self):
        self.assertEqual(self.parser.decode(
"""h 1 1 3
h 2 10 12
h 3 1 1
h 4 2 5
h 5 3 3
s 3 1
s 1 2
s 4 2
s 5 2
""".encode()), [('h', '1', '1', '3'), ('h', '2', '10', '12'), ('h', '3', '1', '1'), ('h', '4', '2', '5'), ('h', '5', '3', '3'), ('s', '3', '1'), ('s', '1', '2'), ('s', '4', '2'), ('s', '5', '2')])


class Verifiertests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = verifier.HikersVerifier()

    def test_verify_semantics_of_instance(self):
        self.assertTrue(self.verifier.verify_semantics_of_instance([('h', '1', '1', '3')], instance_size=10))
        self.assertFalse(self.verifier.verify_semantics_of_instance([], instance_size=10))

    def test_verify_semantics_of_solution(self):
        self.assertFalse(self.verifier.verify_semantics_of_solution([], 10, solution_type=False))
        self.assertTrue(self.verifier.verify_semantics_of_solution([('s', '5', '2')], 10, solution_type=False))

    def test_verify_solution_against_instance(self):
        #Valid solutions should be accepted
        instance = [('h', '1', '1', '3'), ('h', '2', '10', '12'), ('h', '3', '1', '1'), ('h', '4', '2', '5'), ('h', '5', '3', '3')]
        solution = [('s', '3', '1'), ('s', '1', '2'), ('s', '4', '2'), ('s', '5', '2')]
        self.assertTrue(self.verifier.verify_solution_against_instance(instance, solution, instance_size=10, solution_type=False))

        #Invalid solutions should not be accepted
        instance = [('h', '4', '2', '5')]
        solution = [('s', '4', '1')]
        self.assertFalse(self.verifier.verify_solution_against_instance(instance, solution, instance_size=10, solution_type=False))

        instance = [('h', '1', '1', '3'), ('h', '3', '1', '1')]
        solution = [('s', '1', '1'), ('s', '3', '1')]
        self.assertFalse(self.verifier.verify_solution_against_instance(instance, solution, instance_size=10, solution_type=False))

    def test_calculate_approximation_ratio(self):
        instance = [('h', '1', '1', '3'), ('h', '2', '10', '12'), ('h', '3', '1', '1'), ('h', '4', '2', '5'), ('h', '5', '3', '3'), ('h', '6', '1', '1')]
        solution_sufficient = [('s', '3', '1'), ('s', '1', '2'), ('s', '4', '2'), ('s', '5', '2'), ('s', '6', '3')]
        solution_too_little = [('s', '3', '1'), ('s', '1', '2'), ('s', '4', '2'), ('s', '5', '2')]
        self.assertEqual(self.verifier.calculate_approximation_ratio(instance, 10, solution_sufficient, solution_too_little), 5/4)
        self.assertEqual(self.verifier.calculate_approximation_ratio(instance, 10, solution_sufficient, solution_sufficient), 1.0)

if __name__ == '__main__':
    unittest.main()
