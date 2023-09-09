"""Main module, will be run as the program."""
import json


# ? if program == "generator"
with open("/input/max_size.txt") as file:
    max_size = int(file.read())

# ! your code here
instance = {}
solution = {}

with open("/output/instance.json", "w+") as file:
    json.dump(instance, file)
# ? else
with open("/input/instance.json") as file:
    instance = json.load(file)

# ! your code here
solution = {}

# ? endif
with open("/output/solution.json", "w+") as file:
    json.dump(solution, file)
