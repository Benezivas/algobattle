"""Simple generator that outputs a static string encoding an instance with an artificially wrong certificate."""
with open("output", "w") as output:
    output.write("i 1\ns 1 0")
