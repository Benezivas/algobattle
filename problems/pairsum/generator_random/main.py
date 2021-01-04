import random

fin = open("input")
fout = open("output","w")
n = int(fin.readline())

l = [random.randint(0,2**62) for i in range(n)]
sol = random.sample(range(n), 4)
l[sol[0]] = random.randint(2**60,2**62)
l[sol[1]] = random.randint(2**60,2**62)
l[sol[2]] = random.randint(0,2**59)
l[sol[3]] = l[sol[0]] + l[sol[1]] - l[sol[2]]

fout.write(" ".join(str(i) for i in l))
fout.write("\n")
fout.write(" ".join(str(i) for i in sol))
fout.close()
