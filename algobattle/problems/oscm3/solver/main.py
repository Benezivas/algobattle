with open("input") as fin:
    lines = []
    for line in fin:
        lines.append(line)
n = len(lines)

fout = open("output", "w")
fout.write("s ")
for i in range(n):
    fout.write("{} ".format(i))
fout.close()
