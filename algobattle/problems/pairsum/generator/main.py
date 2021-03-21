fin = open("input")
fout = open("output", "w")
n = int(fin.readline())

fout.write(" ".join("1" for i in range(n)))
fout.write("\n")
fout.write("0 1 2 3")
fout.close()
