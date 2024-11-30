#!/usr/bin/env python
import sys
import time
for i in range(0, 10):
    print("[Count {0:04d}]".format(i))
    #sys.stdout.write("[Count {0:04d}]".format(i))
    time.sleep(1)
