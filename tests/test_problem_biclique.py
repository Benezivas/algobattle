""" Tests for the biclique problem.
"""
import unittest
import logging

from algobattle.problems.biclique import parser, verifier

logging.disable(logging.CRITICAL)

class Parsertests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = parser.BicliqueParser()

    def test_split_into_instance_and_solution(self):
        raw_input = [('e', '1', '2', '1'),('e', '3', '2'), ('s', 'set1', '1'), ('s', 'set1', '3'), ('s', 'set1', '2'), ('foo', 'bar')]
        self.assertEqual(self.parser.split_into_instance_and_solution(raw_input), 
        ([('e', '1', '2', '1'),('e', '3', '2')], [('s', 'set1', '1'), ('s', 'set1', '3'), ('s', 'set1', '2')]))

        #empty inputs should be handled
        self.assertEqual(self.parser.split_into_instance_and_solution([]), ([],[]))

    def test_parse_instance(self):
        #lines with too many entries should be removed
        raw_instance = [('e', '1', '2', '1'),('e', '3', '2')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=3), [('e', '3', '2')])

        #lines with too few entries should be removed
        raw_instance = [('e', '1'), ('e')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=2), [])

        #Lines that use labels higher than instance_size should be removed
        raw_instance = [('e', '3', '2')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=2), [])

        #Duplicates should be removed
        raw_instance = [('e', '3', '2'), ('e', '3', '2')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=3), [('e', '3', '2')])

        #Lines with letters should be removed
        raw_instance = [('e', '3', 'a'), ('e', 'b', '2')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=3), [])

        #0 label lines should be removed
        raw_instance = [('e', '1', '0'), ('e', '0', '1')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=3), [])

        #selfloop lines should be removed
        raw_instance = [('e', '1', '1')]
        self.assertEqual(self.parser.parse_instance(raw_instance, instance_size=3), [])

        #empty inputs should be handled
        self.assertEqual(self.parser.parse_instance([], instance_size=3), [])

    def test_parse_solution(self):
        #lines with too many entries should be removed
        raw_solution = [('s', 'set1', '0', '1'), ('s', 'set1', '1')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=2), [('s', 'set1', '1')])

        #lines with too few entries should be removed
        raw_solution = [('s', 'set1')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=2), [])

        #Lines that use labels higher than instance_size should be removed
        raw_solution = [('s', 'set1', '3')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=2), [])

        #Lines with letters should be removed
        raw_solution = [('s', 'set1', 'a')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=2), [])

        #0 label lines should be removed
        raw_solution = [('s', 'set1', '0')]
        self.assertEqual(self.parser.parse_solution(raw_solution, instance_size=2), [])

        #empty inputs should be handled
        self.assertEqual(self.parser.parse_solution([], instance_size=2), [])

    def test_encode(self):
        self.assertEqual(self.parser.encode([('e', '1', '2'),('e', '3', '2'), ('s', 'set1', '1'), ('s', 'set1', '3'), ('s', 'set2', '2')]), 
"""e 1 2
e 3 2
s set1 1
s set1 3
s set2 2""".encode())

    def test_decode(self):
        self.assertEqual(self.parser.decode(
"""e 1 2
e 3 2
s set1 1
s set1 3
s set2 2
""".encode()), [('e', '1', '2'),('e', '3', '2'), ('s', 'set1', '1'), ('s', 'set1', '3'), ('s', 'set2', '2')])


class Verifiertests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = verifier.BicliqueVerifier()

    def test_verify_semantics_of_instance(self):
        self.assertTrue(self.verifier.verify_semantics_of_instance([('e', '1', '2')], instance_size=2))
        self.assertFalse(self.verifier.verify_semantics_of_instance([], instance_size=2))

    def test_verify_semantics_of_solution(self):
        self.assertFalse(self.verifier.verify_semantics_of_solution([], 2, solution_type=False))
        self.assertFalse(self.verifier.verify_semantics_of_solution([('s', 'set1', '1')], 2, solution_type=False))
        self.assertFalse(self.verifier.verify_semantics_of_solution([('s', 'set2', '1')], 2, solution_type=False))
        self.assertFalse(self.verifier.verify_semantics_of_solution([('s', 'set1', '1'), ('s', 'set2', '1')], 2, solution_type=False))
        self.assertTrue(self.verifier.verify_semantics_of_solution([('s', 'set1', '1'), ('s', 'set2', '2')], 2, solution_type=False))

    def test_verify_solution_against_instance(self):
        instance = [('e', '1', '3'), ('e', '1', '4'), ('e', '2', '3'), ('e', '2', '4'), ('e', '2', '5')]
        solution = [('s', 'set1', '1'), ('s', 'set1', '2'), ('s', 'set2', '3'), ('s', 'set2', '4')]
        self.assertTrue(self.verifier.verify_solution_against_instance(instance, solution, instance_size=5, solution_type=False))

        solution = [('s', 'set1', '1'), ('s', 'set1', '2'), ('s', 'set2', '3'), ('s', 'set2', '4'), ('s', 'set1', '5')]
        self.assertFalse(self.verifier.verify_solution_against_instance(instance, solution, instance_size=5, solution_type=False))

    def test_calculate_approximation_ratio(self):
        self.assertEqual(self.verifier.calculate_approximation_ratio([('e', '1', '2'), ('e', '1', '3')], 2, [('s', 'set1', '1'), ('s', 'set2', '2'), ('s', 'set2', '3')], [('s', 'set1', '1'), ('s', 'set2', '2')]), 3/2)
        self.assertEqual(self.verifier.calculate_approximation_ratio([('e', '1', '2'), ('e', '1', '3')], 2, [('s', 'set1', '1'), ('s', 'set2', '2'), ('s', 'set2', '3')], [('s', 'set2', '1'), ('s', 'set1', '2'), ('s', 'set1', '3')]), 1.0)

if __name__ == '__main__':
    unittest.main()
