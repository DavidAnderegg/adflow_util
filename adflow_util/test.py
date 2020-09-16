import os

f = open('regular.txt', 'w')
for key, value in os.environ.items():
            f.write(key + ': ' + value + '\n')
f.close()