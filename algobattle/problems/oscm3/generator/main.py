fin = open("input")
fout = open("output","w")
n = int(fin.readline())

fout.write("n 0 1 2\nn 1 0 1 2\nn 2 0 1\ns 2 1 0")
fout.close()
