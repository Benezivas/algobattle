import json
from random import randrange, sample

with open("input/size.txt") as file:  # (1)!
    size = int(file.read())

numbers = [randrange(2**63 - 1) for _ in range(size - 4)]  # (2)!

a, b = randrange(2**63 - 1), randrange(2**63 - 1)  # (4)!
c = randrange(min(a + b, 2**63 - 1))
d = a + b - c
solution = [a, b, c, d]
solution_indices = sorted(sample(range(size), 4))
for index, number in zip(solution_indices, solution):
    numbers.insert(index, number)

with open("output/instance.json", "x") as file:  # (3)!
    instance = {
        "numbers": numbers,
    }
    json.dump(instance, file)

with open("output/solution.json", "x") as file:  # (5)!
    solution = {
        "indices": solution_indices,
    }
    json.dump(solution, file)
