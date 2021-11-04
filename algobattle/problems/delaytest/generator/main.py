"""Dummy solver for the delaytest problem. Outputs n # signs, where n is the read input."""
n = 0
with open("input", "r") as input:
    n = int(input.readline())
with open("output", "w") as output:
    output.write("#" * n)
