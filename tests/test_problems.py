""" Test suite wrapping the tests for all problems
"""
import unittest

import tests.test_problem_biclique as biclique

def suites():
    #suite = unittest.TestSuite()
    suites = []
    suites.append(unittest.defaultTestLoader.loadTestsFromTestCase(biclique.Parsertests))
    suites.append(unittest.defaultTestLoader.loadTestsFromTestCase(biclique.Verifiertests))
    return suites

if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    for suite in suites():
        runner.run(suite)