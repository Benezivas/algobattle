# The Tests Problem
This problem module is not meant to be run using a regular execution.
It provides a number of different generators and solvers that help 
test different methods of the `match.py`.

These are the behaviours of the different solvers and generators in this folder:
```
Name                                       Test description
high_n                                     Simulates a run that exceeds the cap
build_timeout                              Forces the build process to timeout
build_error                                Corrupted Dockerfile causes the build to fail 

generator_timeout                          Forces the generator to timeout
generator_wrong_certificate                Generator that only outputs instances with a wrong certificate
solver_timeout                             Solver that times out
solver_wrong_solution                      Solver that only outputs wrong solutions to any input
solver_fail_after_first_failure            Solver that runs successful for 5 iterations then only fails
solver_success_after_first_failure         Solver that runs successful for 5 iterations then fails then only succeeds again
solver_fail_after_first_success            Solver that successfully solves one instance then no further
solver_success_after_early_failure         Solver that runs successful for a single round then fails then only succeeds again
solver_fail_sometime_after_first_failure   Solver that runs successful for 5 iterations then fails then succeeds for 2 iterations then fails
```