""" Test suite wrapping all tests of the project.
"""
import unittest

import tests.test_match as match
import tests.test_problem_biclique as biclique
import tests.test_problem_c4subgprahiso as c4subgraphiso

def suites():
    suites = []
    suites.append(unittest.defaultTestLoader.loadTestsFromTestCase(match.Matchtests))
    suites.append(unittest.defaultTestLoader.loadTestsFromTestCase(biclique.Parsertests))
    suites.append(unittest.defaultTestLoader.loadTestsFromTestCase(biclique.Verifiertests))
    suites.append(unittest.defaultTestLoader.loadTestsFromTestCase(c4subgraphiso.Parsertests))
    suites.append(unittest.defaultTestLoader.loadTestsFromTestCase(c4subgraphiso.Verifiertests))
    return suites

if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    for suite in suites():
        runner.run(suite)