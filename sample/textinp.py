import sys
import time

print(f"<INP> START", file=sys.stderr)
for i in range(20):    
    #a = sys.stdin.read(5)
    a = input()
    print(f"<INP> input = {a}", file=sys.stderr)
    time.sleep(0.2)