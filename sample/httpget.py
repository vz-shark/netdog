#!/usr/bin/env python
import sys
print("GET / HTTP/1.1\r\n", end="")
while(True): print(f"response = {input()}", file=sys.stderr)