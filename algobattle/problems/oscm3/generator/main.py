fin = open("input")
fout = open("output", "w")
n = int(fin.readline())

for i in range(n):
    fout.write("n {}\n".format(i))
fout.write("s ")
for i in range(n):
    fout.write("{} ".format(i))
fout.close()
