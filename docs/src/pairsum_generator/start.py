import json
from random import randrange

with open("input/max_size.txt") as file:  # (1)!
    size = int(file.read())

numbers = [randrange(2**63 - 1) for _ in range(size - 4)]  # (2)!

with open("output/instance.json", "x") as file:  # (3)!
    instance = {
        "numbers": numbers,
    }
    json.dump(instance, file)
