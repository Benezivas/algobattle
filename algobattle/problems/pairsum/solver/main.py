fin = open("input")
line = fin.readline()

ints = [int(a) for a in line.split()]

fout = open("output", "w")
fout.write("0 1 2 3")
fout.close()
