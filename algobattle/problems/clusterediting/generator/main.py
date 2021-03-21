fin = open("input")
fout = open("output", "w")
n = int(fin.readline())

fout.write("e 1 2\ne 3 2\ne 1 4\ns del 1 4\ns add 1 3")
fout.close()
