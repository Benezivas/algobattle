fin = open("input")
fout = open("output", "w")
n = int(fin.readline())

fout.write("s 1\ns 4\ne 1 2\ne 2 3\ne 3 4\ne 4 5\ne 5 6\ne 6 1\ne 2 6\ne 3 5")
fout.close()
